"""Rezepte – Home Assistant Custom Integration."""
from __future__ import annotations

import base64
import json
import logging
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.frontend import async_register_built_in_panel

_LOGGER = logging.getLogger(__name__)

DOMAIN         = "rezepte"
RECIPES_FILE   = "recipes.json"
HA_CONFIG_FILE = "ha_config.json"


# Version beim Modulimport lesen – verhindert Blocking im Event-Loop
try:
    _VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]
except Exception:
    _VERSION = "1"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration über Config Entry einrichten."""

    # Neue Felder (v1.2.3+)
    alexa_players = entry.data.get("alexa_players", [])
    tts_players   = entry.data.get("tts_players", [])
    tts_engine    = entry.data.get("tts_engine", "tts.google_translate_de_de")

    # Rueckwaertskompatibilitaet mit v1.2.0–v1.2.2
    if not alexa_players and not tts_players:
        _old = entry.data.get("media_players", [])
        _method = entry.data.get("announce_method", "alexa")
        if _method == "alexa":
            alexa_players = _old
        else:
            tts_players = _old

    all_players   = list(dict.fromkeys(alexa_players + tts_players))

    # 1. Web-Dateien bereitstellen
    await hass.async_add_executor_job(_provision_www, hass)

    # 2. ha_config.json für Frontend schreiben
    cfg_path = Path(hass.config.path("www", DOMAIN, HA_CONFIG_FILE))
    await hass.async_add_executor_job(
        _write_json, cfg_path,
        {"media_players": all_players,
         "alexa_players": alexa_players,
         "tts_players":   tts_players}
    )

    # 3. Panel registrieren
    try:
        async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="Rezepte",
            sidebar_icon="mdi:chef-hat",
            frontend_url_path=DOMAIN,
            config={"url": f"/local/{DOMAIN}/index.html?v={_VERSION}"},
            require_admin=False,
        )
    except Exception:  # noqa: BLE001
        pass  # Panel bereits registriert (z.B. nach Reload) – kein Fehler

    # 4. Service: save_recipes
    async def handle_save_recipes(call: ServiceCall) -> None:
        encoded = call.data.get("encoded", "")
        missing = len(encoded) % 4
        if missing:
            encoded += "=" * (4 - missing)
        try:
            recipes = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception as err:
            _LOGGER.error("Fehler beim Dekodieren: %s", err)
            return
        target = Path(hass.config.path("www", DOMAIN, RECIPES_FILE))
        await hass.async_add_executor_job(_write_json, target, recipes)

    # 5. Service: announce_timer
    async def handle_announce_timer(call: ServiceCall) -> None:
        step_num  = call.data.get("step_num", 1)
        a_players = call.data.get("alexa_players", alexa_players)
        t_players = call.data.get("tts_players",   tts_players)
        message   = f"Der Timer aus Schritt {step_num} ist beendet"

        if not a_players and not t_players:
            _LOGGER.info("Timer-Ansage: Keine Ausgabegeraete konfiguriert")
            return

        _LOGGER.info("Timer-Ansage: '%s' → Alexa=%s, TTS=%s", message, a_players, t_players)

        # Alexa-Geräte: announce
        if a_players:
            try:
                # notify.alexa_media: target = Liste von entity_ids, type=announce
                await hass.services.async_call(
                    "notify", "alexa_media",
                    {
                        "message": message,
                        "target":  a_players,
                        "data":    {"type": "announce"},
                    },
                    blocking=True,
                )
                _LOGGER.info("Alexa-Ansage OK: %s", a_players)
            except Exception as err:
                _LOGGER.error("Alexa-Ansage fehlgeschlagen (players=%s): %s", a_players, err)
                # Fallback: jeden Echo einzeln ansprechen
                for player in a_players:
                    svc = "alexa_media_" + player.replace("media_player.", "").replace(".", "_")
                    try:
                        await hass.services.async_call(
                            "notify", svc,
                            {"message": message, "data": {"type": "announce"}},
                            blocking=True,
                        )
                        _LOGGER.info("Fallback Alexa OK: notify.%s", svc)
                    except Exception as err2:
                        _LOGGER.error("Fallback fehlgeschlagen (%s): %s", svc, err2)

        # TTS-Geräte: tts.speak
        if t_players:
            try:
                await hass.services.async_call(
                    "tts", "speak",
                    {
                        "media_player_entity_id": t_players,
                        "message": message,
                        "cache":   False,
                    },
                    target={"entity_id": tts_engine},
                    blocking=True,
                )
                _LOGGER.info("TTS-Ansage OK: %s", t_players)
            except Exception as err:
                _LOGGER.error("TTS-Ansage fehlgeschlagen (players=%s, engine=%s): %s", t_players, tts_engine, err)

    hass.services.async_register(DOMAIN, "save_recipes",   handle_save_recipes)
    hass.services.async_register(DOMAIN, "announce_timer", handle_announce_timer)
    _LOGGER.info("Rezepte geladen – Alexa: %s, TTS: %s", alexa_players, tts_players)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "save_recipes")
    hass.services.async_remove(DOMAIN, "announce_timer")
    return True


def _provision_www(hass: HomeAssistant) -> None:
    src_dir = Path(__file__).parent / "www"
    dst_dir = Path(hass.config.path("www", DOMAIN))
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src_file in src_dir.iterdir():
        if not src_file.is_file():
            continue
        dst_file = dst_dir / src_file.name
        if src_file.name == RECIPES_FILE and dst_file.exists():
            continue
        shutil.copy2(src_file, dst_file)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
