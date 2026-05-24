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
from homeassistant.loader import async_get_integration

_LOGGER = logging.getLogger(__name__)

DOMAIN        = "rezepte"
RECIPES_FILE  = "recipes.json"
HA_CONFIG_FILE = "ha_config.json"



def _get_version(init_file: str) -> str:
    """Versionsnummer aus manifest.json lesen."""
    import json as _json
    from pathlib import Path as _Path
    try:
        manifest = _Path(init_file).parent / "manifest.json"
        return _json.loads(manifest.read_text())["version"]
    except Exception:
        return "1"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Integration über Config Entry einrichten."""

    # 1. Web-Dateien nach /config/www/rezepte/ bereitstellen
    await hass.async_add_executor_job(_provision_www, hass)

    # 2. ha_config.json für Frontend schreiben (Standardgeräte)
    media_players    = entry.data.get("media_players", [])
    announce_method  = entry.data.get("announce_method", "tts")
    tts_engine       = entry.data.get("tts_engine", "tts.google_translate_de_de")
    cfg_path = Path(hass.config.path("www", DOMAIN, HA_CONFIG_FILE))
    await hass.async_add_executor_job(
        _write_json, cfg_path,
        {"media_players": media_players, "announce_method": announce_method}
    )

    # 3. Seitenleisten-Panel registrieren
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

    # 4. Service rezepte.save_recipes
    async def handle_save_recipes(call: ServiceCall) -> None:
        encoded = call.data.get("encoded", "")
        missing = len(encoded) % 4
        if missing:
            encoded += "=" * (4 - missing)
        try:
            recipes = json.loads(base64.b64decode(encoded).decode("utf-8"))
        except Exception as err:
            _LOGGER.error("Fehler beim Dekodieren der Rezeptdaten: %s", err)
            return
        target = Path(hass.config.path("www", DOMAIN, RECIPES_FILE))
        await hass.async_add_executor_job(_write_json, target, recipes)

    # 5. Service rezepte.announce_timer
    async def handle_announce_timer(call: ServiceCall) -> None:
        """Timer-Ende auf Alexa-Geräten ankündigen."""
        step_name  = call.data.get("step_name", "Timer")
        entity_ids = call.data.get("entity_ids", media_players)

        if not entity_ids:
            _LOGGER.debug("Keine Ausgabegeraete konfiguriert – Ansage uebersprungen")
            return

        message = f"Der Timer für {step_name} ist beendet"
        _LOGGER.debug("Timer-Ansage: '%s' → %s", message, entity_ids)

        try:
            if announce_method == "alexa":
                # Alexa Media Player: notify.alexa_media
                await hass.services.async_call(
                    "notify", "alexa_media",
                    {
                        "message": message,
                        "target":  entity_ids,
                        "data":    {"type": "tts"},
                    },
                    blocking=False,
                )
            else:
                # HA TTS: universell fuer alle media_player
                await hass.services.async_call(
                    "tts", "speak",
                    {
                        "media_player_entity_id": entity_ids,
                        "message": message,
                        "cache":   False,
                    },
                    target={"entity_id": tts_engine},
                    blocking=False,
                )
            _LOGGER.debug("Timer-Ansage (%s): '%s' → %s", announce_method, message, entity_ids)
        except Exception as err:
            _LOGGER.warning("Timer-Ansage fehlgeschlagen: %s", err)

    hass.services.async_register(DOMAIN, "save_recipes",    handle_save_recipes)
    hass.services.async_register(DOMAIN, "announce_timer",  handle_announce_timer)

    _LOGGER.info("Rezepte-Integration geladen (Methode: %s, Geraete: %s)", announce_method, media_players)
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
