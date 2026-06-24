"""Rezepte – Home Assistant Custom Integration (Custom Element Panel)."""
from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall, callback

_LOGGER = logging.getLogger(__name__)

DOMAIN        = "rezepte"
RECIPES_FILE  = "recipes.json"
HA_CONFIG_FILE = "ha_config.json"
PANEL_ELEMENT = "rezepte-panel"
PANEL_JS      = "rezepte-panel.js"
STATIC_URL    = f"/{DOMAIN}_static"

try:
    _VERSION = json.loads(
        (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )["version"]
except Exception:
    _VERSION = "1"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Statischen Pfad für das Panel-JS registrieren."""
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            STATIC_URL,
            str(Path(__file__).parent / "frontend"),
            cache_headers=False,
        )
    ])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Panel und Services einrichten."""

    alexa_players = entry.data.get("alexa_players", [])
    tts_players   = entry.data.get("tts_players", [])
    tts_engine    = entry.data.get("tts_engine", "tts.google_translate_de_de")
    all_players   = list(dict.fromkeys(alexa_players + tts_players))

    # Datendateien bereitstellen (recipes.json + ha_config.json)
    await hass.async_add_executor_job(_provision_data, hass, all_players,
                                      alexa_players, tts_players)

    # Panel registrieren
    @callback
    def _register_panel(_event=None) -> None:
        try:
            async_register_built_in_panel(
                hass,
                component_name="custom",
                sidebar_title="Rezepte",
                sidebar_icon="mdi:chef-hat",
                frontend_url_path=DOMAIN,
                config={
                    "_panel_custom": {
                        "name":         PANEL_ELEMENT,
                        "embed_iframe": False,
                        "trust_external": False,
                        "module_url":   f"{STATIC_URL}/{PANEL_JS}?v={_VERSION}",
                    }
                },
                require_admin=False,
            )
        except Exception:  # noqa: BLE001
            pass  # Panel bereits registriert (Reload)

    if hass.state is CoreState.running:
        _register_panel()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register_panel)

    # Service: save_recipes
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

    # Service: announce_timer
    async def handle_announce_timer(call: ServiceCall) -> None:
        step_num  = call.data.get("step_num", 1)
        a_players = call.data.get("alexa_players", alexa_players)
        t_players = call.data.get("tts_players",   tts_players)
        message   = f"Der Timer aus Schritt {step_num} ist beendet"

        if not a_players and not t_players:
            return

        _LOGGER.info("Timer-Ansage: '%s' → Alexa=%s, TTS=%s", message, a_players, t_players)

        if a_players:
            try:
                await hass.services.async_call(
                    "notify", "alexa_media",
                    {"message": message, "target": a_players,
                     "data": {"type": "announce"}},
                    blocking=True,
                )
                # Fallback: einzeln
            except Exception as err:
                _LOGGER.warning("Alexa-Announce fehlgeschlagen: %s", err)
                for player in a_players:
                    svc = "alexa_media_" + player.replace("media_player.", "").replace(".", "_")
                    try:
                        await hass.services.async_call(
                            "notify", svc,
                            {"message": message, "data": {"type": "announce"}},
                            blocking=True,
                        )
                    except Exception as err2:
                        _LOGGER.error("Fallback (%s): %s", svc, err2)

        if t_players:
            try:
                await hass.services.async_call(
                    "tts", "speak",
                    {"media_player_entity_id": t_players, "message": message,
                     "cache": False},
                    target={"entity_id": tts_engine},
                    blocking=True,
                )
            except Exception as err:
                _LOGGER.error("TTS-Ansage fehlgeschlagen: %s", err)

    hass.services.async_register(DOMAIN, "save_recipes",   handle_save_recipes)
    hass.services.async_register(DOMAIN, "announce_timer", handle_announce_timer)

    _LOGGER.info("Rezepte v%s geladen", _VERSION)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "save_recipes")
    hass.services.async_remove(DOMAIN, "announce_timer")
    return True


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _provision_data(hass: HomeAssistant, all_players: list,
                    alexa_players: list, tts_players: list) -> None:
    """Datendateien anlegen (recipes.json + ha_config.json)."""
    data_dir = Path(hass.config.path("www", DOMAIN))
    data_dir.mkdir(parents=True, exist_ok=True)

    # recipes.json nur anlegen wenn noch nicht vorhanden
    recipes_path = data_dir / RECIPES_FILE
    if not recipes_path.exists():
        _write_json(recipes_path, [])

    # ha_config.json immer aktualisieren
    _write_json(
        data_dir / HA_CONFIG_FILE,
        {"media_players": all_players,
         "alexa_players": alexa_players,
         "tts_players":   tts_players},
    )


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
