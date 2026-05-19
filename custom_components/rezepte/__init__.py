"""Rezepte – Home Assistant Custom Integration.

Registriert automatisch:
  - Seitenleisten-Panel (iframe → /local/rezepte/index.html)
  - Service rezepte.save_recipes zum Speichern der recipes.json
  - Kopiert Web-Dateien nach /config/www/rezepte/ beim Start
"""
from __future__ import annotations

import base64
import json
import logging
import shutil
from pathlib import Path

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.components.frontend import async_register_built_in_panel

_LOGGER = logging.getLogger(__name__)

DOMAIN = "rezepte"
RECIPES_FILE = "recipes.json"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Integration einrichten."""

    # 1. Web-Dateien nach /config/www/rezepte/ bereitstellen
    await hass.async_add_executor_job(_provision_www, hass)

    # 2. Seitenleisten-Panel registrieren
    try:
        async_register_built_in_panel(
            hass,
            component_name="iframe",
            sidebar_title="Rezepte",
            sidebar_icon="mdi:chef-hat",
            frontend_url_path=DOMAIN,
            config={"url": f"/local/{DOMAIN}/index.html"},
            require_admin=False,
        )
        _LOGGER.debug("Panel 'Rezepte' registriert.")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Panel konnte nicht registriert werden: %s", err)

    # 3. Service rezepte.save_recipes registrieren
    async def handle_save_recipes(call: ServiceCall) -> None:
        """Rezepte-JSON aus Base64-kodierter Payload schreiben."""
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

    hass.services.async_register(DOMAIN, "save_recipes", handle_save_recipes)

    _LOGGER.info("Rezepte-Integration geladen.")
    return True


# ── Hilfsfunktionen (synchron, laufen im Executor-Thread) ─────────────────────

def _provision_www(hass: HomeAssistant) -> None:
    """Web-Dateien aus dem Integrationsverzeichnis nach /config/www/rezepte/ kopieren."""
    src_dir = Path(__file__).parent / "www"
    dst_dir = Path(hass.config.path("www", DOMAIN))
    dst_dir.mkdir(parents=True, exist_ok=True)

    for src_file in src_dir.iterdir():
        if not src_file.is_file():
            continue
        dst_file = dst_dir / src_file.name
        # Benutzerdaten (recipes.json) nicht überschreiben
        if src_file.name == RECIPES_FILE and dst_file.exists():
            _LOGGER.debug("%s bereits vorhanden – wird nicht überschrieben.", RECIPES_FILE)
            continue
        shutil.copy2(src_file, dst_file)
        _LOGGER.debug("Kopiert: %s → %s", src_file.name, dst_dir)

    _LOGGER.info("Web-Dateien bereit in: %s", dst_dir)


def _write_json(path: Path, data: list) -> None:
    """Rezeptliste als formatierte JSON-Datei schreiben."""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _LOGGER.debug("%d Rezept(e) gespeichert → %s", len(data), path)
