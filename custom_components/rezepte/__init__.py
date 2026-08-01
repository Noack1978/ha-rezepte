"""Rezepte – Home Assistant Custom Integration."""
from __future__ import annotations

import base64
import json
import logging
import shutil
import time
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN            = "rezepte"
RECIPES_FILE      = "recipes.json"
HA_CONFIG_FILE    = "ha_config.json"
TIMER_STATE_FILE  = "timer_state.json"
SIGNAL_TIMER_STATE = f"{DOMAIN}_timer_state_update"
PLATFORMS         = ["sensor"]

try:
    _VERSION = json.loads(
        (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )["version"]
except Exception:
    _VERSION = "1"

# Laufzustand (pro Instanz / Entry)
_timer_handle:        object | None = None
_timer_finishes_at:   float         = 0.0   # epoch-Sekunden
_timer_remaining_sec: int           = 0     # Sekunden verbleibend (pausiert)
_timer_step_num:      int           = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration über Config Entry einrichten."""
    global _timer_handle, _timer_finishes_at, _timer_remaining_sec, _timer_step_num

    alexa_players = entry.data.get("alexa_players", [])
    tts_players   = entry.data.get("tts_players", [])
    tts_engine    = entry.data.get("tts_engine", "tts.google_translate_de_de")
    airfryer_temp_entity  = entry.data.get("airfryer_temp_entity", "")
    airfryer_time_entity  = entry.data.get("airfryer_time_entity", "")
    airfryer_start_entity = entry.data.get("airfryer_start_entity", "")

    # Rückwärtskompatibilität v1.2.0–v1.2.2
    if not alexa_players and not tts_players:
        _old    = entry.data.get("media_players", [])
        _method = entry.data.get("announce_method", "alexa")
        if _method == "alexa":
            alexa_players = _old
        else:
            tts_players = _old

    all_players = list(dict.fromkeys(alexa_players + tts_players))

    # 1. Web-Dateien bereitstellen
    await hass.async_add_executor_job(_provision_www, hass)

    # 2. ha_config.json schreiben
    cfg_path = Path(hass.config.path("www", DOMAIN, HA_CONFIG_FILE))
    await hass.async_add_executor_job(
        _write_json, cfg_path,
        {"media_players": all_players,
         "alexa_players": alexa_players,
         "tts_players":   tts_players,
         "airfryer_temp_entity":  airfryer_temp_entity,
         "airfryer_time_entity":  airfryer_time_entity,
         "airfryer_start_entity": airfryer_start_entity},
    )

    # 3. timer_state.json initialisieren (nur falls nicht vorhanden)
    ts_path = Path(hass.config.path("www", DOMAIN, TIMER_STATE_FILE))
    if not ts_path.exists():
        await hass.async_add_executor_job(
            _write_json, ts_path, {"state": "idle", "finishes_at": 0, "remaining_secs": 0, "step_num": 1}
        )

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

    # 5. Sensor-Plattform weiterleiten (sensor.rezepte_kochtimer)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Timer-Helfer (intern, kein HA-Helfer nötig) ────────────────────────

    def _write_timer_state(state: str, finishes_at: float = 0, remaining: int = 0, step: int = 1) -> None:
        payload = {
            "state":          state,
            "finishes_at":    finishes_at,
            "remaining_secs": remaining,
            "step_num":       step,
        }
        path = Path(hass.config.path("www", DOMAIN, TIMER_STATE_FILE))
        _write_json(path, payload)
        hass.loop.call_soon_threadsafe(
            async_dispatcher_send, hass, SIGNAL_TIMER_STATE, payload
        )

    async def handle_timer_start(call: ServiceCall) -> None:
        global _timer_handle, _timer_finishes_at, _timer_step_num
        duration_secs = int(call.data.get("duration", 0))
        step_num      = int(call.data.get("step_num", 1))
        if duration_secs <= 0:
            return
        # Laufenden Timer abbrechen
        if _timer_handle:
            _timer_handle()
            _timer_handle = None

        _timer_step_num    = step_num
        _timer_finishes_at = time.time() + duration_secs

        await hass.async_add_executor_job(
            _write_timer_state, "active", _timer_finishes_at, duration_secs, step_num
        )

        @callback
        def _on_finished(_now: object) -> None:
            global _timer_handle
            _timer_handle = None
            hass.async_add_executor_job(
                _write_timer_state, "idle", 0, 0, _timer_step_num
            )
            hass.async_create_background_task(
                _send_announcement(hass, _timer_step_num, alexa_players, tts_players, tts_engine),
                "rezepte_timer_announce",
            )
            _LOGGER.info("Timer beendet – Ansage für Schritt %s", _timer_step_num)

        _timer_handle = async_call_later(hass, duration_secs, _on_finished)
        _LOGGER.info("Timer gestartet: %s Sekunden (Schritt %s)", duration_secs, step_num)

    async def handle_timer_pause(call: ServiceCall) -> None:  # noqa: ARG001
        global _timer_handle, _timer_remaining_sec
        if not _timer_handle:
            return
        _timer_handle()
        _timer_handle = None
        _timer_remaining_sec = max(0, int(_timer_finishes_at - time.time()))
        await hass.async_add_executor_job(
            _write_timer_state, "paused", 0, _timer_remaining_sec, _timer_step_num
        )
        _LOGGER.info("Timer pausiert: %s Sekunden verbleibend", _timer_remaining_sec)

    async def handle_timer_resume(call: ServiceCall) -> None:  # noqa: ARG001
        global _timer_handle, _timer_finishes_at
        if _timer_remaining_sec <= 0:
            return
        _timer_finishes_at = time.time() + _timer_remaining_sec

        await hass.async_add_executor_job(
            _write_timer_state, "active", _timer_finishes_at, _timer_remaining_sec, _timer_step_num
        )

        @callback
        def _on_finished_resume(_now: object) -> None:
            global _timer_handle
            _timer_handle = None
            hass.async_add_executor_job(
                _write_timer_state, "idle", 0, 0, _timer_step_num
            )
            hass.async_create_background_task(
                _send_announcement(hass, _timer_step_num, alexa_players, tts_players, tts_engine),
                "rezepte_timer_announce",
            )

        _timer_handle = async_call_later(hass, _timer_remaining_sec, _on_finished_resume)
        _LOGGER.info("Timer fortgesetzt: %s Sekunden", _timer_remaining_sec)

    async def handle_timer_cancel(call: ServiceCall) -> None:  # noqa: ARG001
        global _timer_handle
        if _timer_handle:
            _timer_handle()
            _timer_handle = None
        await hass.async_add_executor_job(
            _write_timer_state, "idle", 0, 0, _timer_step_num
        )

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

    async def handle_announce_timer(call: ServiceCall) -> None:
        step_num  = call.data.get("step_num", 1)
        a_players = call.data.get("alexa_players", alexa_players)
        t_players = call.data.get("tts_players",   tts_players)
        await _send_announcement(hass, step_num, a_players, t_players, tts_engine)

    hass.services.async_register(DOMAIN, "save_recipes",   handle_save_recipes)
    hass.services.async_register(DOMAIN, "announce_timer", handle_announce_timer)
    hass.services.async_register(DOMAIN, "timer_start",    handle_timer_start)
    hass.services.async_register(DOMAIN, "timer_pause",    handle_timer_pause)
    hass.services.async_register(DOMAIN, "timer_resume",   handle_timer_resume)
    hass.services.async_register(DOMAIN, "timer_cancel",   handle_timer_cancel)

    _LOGGER.info("Rezepte geladen – Alexa: %s, TTS: %s", alexa_players, tts_players)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    global _timer_handle
    if _timer_handle:
        _timer_handle()
        _timer_handle = None
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    for svc in ("save_recipes", "announce_timer", "timer_start", "timer_pause", "timer_resume", "timer_cancel"):
        hass.services.async_remove(DOMAIN, svc)
    return unloaded


async def _send_announcement(
    hass: HomeAssistant,
    step_num: int,
    alexa_players: list,
    tts_players: list,
    tts_engine: str,
) -> None:
    message = f"Der Timer aus Schritt {step_num} ist beendet"
    if not alexa_players and not tts_players:
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
