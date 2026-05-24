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


def _get_version(init_file: str) -> str:
    """Versionsnummer aus manifest.json lesen."""
    import json as _json
    from pathlib import Path as _Path
    try:
        return _json.loads((_Path(init_file).parent / "manifest.json").read_text())["version"]
    except Exception:
        return "1"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration über Config Entry einrichten."""

    alexa_players = entry.data.get("alexa_players", [])
    tts_players   = entry.data.get("tts_players", [])
    tts_engine    = entry.data.get("tts_engine", "tts.google_translate_de_de")
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
            config={"url": f"/local/{DOMAIN}/index.html?v={_get_version(__file__)}"},
            require_admin=False,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Panel konnte nicht registriert werden: %s", err)

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
            _LOGGER.debug("Keine Ausgabegeraete – Ansage uebersprungen")
            return

        _LOGGER.debug("Timer-Ansage: '%s'", message)

        # Alexa-Geräte: announce
        if a_players:
            try:
                await hass.services.async_call(
                    "notify", "alexa_media",
                    {"message": message,
                     "target":  a_players,
                     "data":    {"type": "announce"}},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.warning("Alexa-Ansage fehlgeschlagen: %s", err)

        # TTS-Geräte: tts.speak
        if t_players:
            try:
                await hass.services.async_call(
                    "tts", "speak",
                    {"media_player_entity_id": t_players,
                     "message": message,
                     "cache":   False},
                    target={"entity_id": tts_engine},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.warning("TTS-Ansage fehlgeschlagen: %s", err)

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
