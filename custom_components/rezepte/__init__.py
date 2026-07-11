"""Rezepte – Home Assistant Custom Integration."""
from __future__ import annotations

import base64
import json
import logging
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

DOMAIN         = "rezepte"
RECIPES_FILE   = "recipes.json"
HA_CONFIG_FILE = "ha_config.json"
TIMER_ENTITY   = "timer.rezepte_kochtimer"
STEP_ENTITY    = "input_number.rezepte_timer_schritt"

try:
    _VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]
except Exception:
    _VERSION = "1"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration über Config Entry einrichten."""

    alexa_players = entry.data.get("alexa_players", [])
    tts_players   = entry.data.get("tts_players", [])
    tts_engine    = entry.data.get("tts_engine", "tts.google_translate_de_de")

    # Rückwärtskompatibilität v1.2.0–v1.2.2
    if not alexa_players and not tts_players:
        _old = entry.data.get("media_players", [])
        if entry.data.get("announce_method", "alexa") == "alexa":
            alexa_players = _old
        else:
            tts_players = _old

    all_players = list(dict.fromkeys(alexa_players + tts_players))

    # 1. Web-Dateien bereitstellen
    await hass.async_add_executor_job(_provision_www, hass)

    # 2. ha_config.json für Frontend schreiben (inkl. Timer-Entities)
    cfg_path = Path(hass.config.path("www", DOMAIN, HA_CONFIG_FILE))
    await hass.async_add_executor_job(
        _write_json, cfg_path,
        {
            "media_players":  all_players,
            "alexa_players":  alexa_players,
            "tts_players":    tts_players,
            "timer_entity":   TIMER_ENTITY,
            "step_entity":    STEP_ENTITY,
        },
    )

    # 3. Helfer anlegen (Timer + Schritt-Nummer)
    await _ensure_helpers(hass)

    # 4. Panel registrieren
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
        pass

    # 5. timer.finished → Ansage
    @callback
    def _on_timer_finished(event: Event) -> None:
        if event.data.get("entity_id") != TIMER_ENTITY:
            return
        step_state = hass.states.get(STEP_ENTITY)
        try:
            step_num = int(float(step_state.state)) if step_state else 1
        except (ValueError, AttributeError):
            step_num = 1
        hass.async_create_background_task(
            _send_announcement(hass, step_num, alexa_players, tts_players, tts_engine),
            "rezepte_timer_announce",
        )

    entry.async_on_unload(hass.bus.async_listen("timer.finished", _on_timer_finished))

    # 6. Services
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

    # announce_timer bleibt als manueller Service erhalten
    async def handle_announce_timer(call: ServiceCall) -> None:
        step_num  = call.data.get("step_num", 1)
        a_players = call.data.get("alexa_players", alexa_players)
        t_players = call.data.get("tts_players",   tts_players)
        await _send_announcement(hass, step_num, a_players, t_players, tts_engine)

    hass.services.async_register(DOMAIN, "save_recipes",   handle_save_recipes)
    hass.services.async_register(DOMAIN, "announce_timer", handle_announce_timer)
    _LOGGER.info("Rezepte geladen – Alexa: %s, TTS: %s", alexa_players, tts_players)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "save_recipes")
    hass.services.async_remove(DOMAIN, "announce_timer")
    return True


async def _ensure_helpers(hass: HomeAssistant) -> None:
    """Timer- und Schritt-Helfer automatisch anlegen falls nicht vorhanden."""
    from homeassistant.components.timer import DOMAIN as TIMER_DOMAIN
    from homeassistant.components.input_number import DOMAIN as INPUT_NUMBER_DOMAIN

    registry = er.async_get(hass)

    # ── Timer ──────────────────────────────────────────────────────────────
    if not registry.async_get(TIMER_ENTITY):
        try:
            coll = hass.data.get(TIMER_DOMAIN)
            if coll and hasattr(coll, "async_create_item"):
                await coll.async_create_item({
                    "name":     "Rezepte Kochtimer",
                    "icon":     "mdi:chef-hat",
                    "duration": "00:05:00",
                    "restore":  True,
                })
                _LOGGER.info("Timer-Helfer '%s' angelegt", TIMER_ENTITY)
            else:
                _LOGGER.warning(
                    "Timer-Helfer konnte nicht automatisch angelegt werden. "
                    "Bitte '%s' manuell unter Einstellungen → Helfer anlegen.",
                    TIMER_ENTITY,
                )
        except Exception as err:
            _LOGGER.warning("Fehler beim Anlegen des Timer-Helfers: %s", err)

    # ── Schritt-Nummer ─────────────────────────────────────────────────────
    if not registry.async_get(STEP_ENTITY):
        try:
            coll = hass.data.get(INPUT_NUMBER_DOMAIN)
            if coll and hasattr(coll, "async_create_item"):
                await coll.async_create_item({
                    "name":    "Rezepte Timer Schritt",
                    "icon":    "mdi:counter",
                    "min":     1,
                    "max":     99,
                    "step":    1,
                    "initial": 1,
                    "mode":    "box",
                })
                _LOGGER.info("Schritt-Helfer '%s' angelegt", STEP_ENTITY)
        except Exception as err:
            _LOGGER.warning("Fehler beim Anlegen des Schritt-Helfers: %s", err)


async def _send_announcement(
    hass: HomeAssistant,
    step_num: int,
    alexa_players: list,
    tts_players: list,
    tts_engine: str,
) -> None:
    """Timer-Ansage an Alexa- und TTS-Geräte senden."""
    message = f"Der Timer aus Schritt {step_num} ist beendet"

    if not alexa_players and not tts_players:
        _LOGGER.info("Timer-Ansage: Keine Ausgabegeräte konfiguriert")
        return

    _LOGGER.info("Timer-Ansage: '%s' → Alexa=%s, TTS=%s", message, alexa_players, tts_players)

    if alexa_players:
        try:
            await hass.services.async_call(
                "notify", "alexa_media",
                {"message": message, "target": alexa_players, "data": {"type": "announce"}},
                blocking=True,
            )
        except Exception as err:
            _LOGGER.error("Alexa-Ansage fehlgeschlagen: %s", err)
            for player in alexa_players:
                svc = "alexa_media_" + player.replace("media_player.", "").replace(".", "_")
                try:
                    await hass.services.async_call(
                        "notify", svc,
                        {"message": message, "data": {"type": "announce"}},
                        blocking=True,
                    )
                except Exception as err2:
                    _LOGGER.error("Fallback fehlgeschlagen (%s): %s", svc, err2)

    if tts_players:
        try:
            await hass.services.async_call(
                "tts", "speak",
                {"media_player_entity_id": tts_players, "message": message, "cache": False},
                target={"entity_id": tts_engine},
                blocking=True,
            )
        except Exception as err:
            _LOGGER.error("TTS-Ansage fehlgeschlagen: %s", err)


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
