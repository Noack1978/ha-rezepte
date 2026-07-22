"""Sensor-Plattform für Rezepte – zeigt den Kochtimer-Status."""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, SIGNAL_TIMER_STATE

_LOGGER = logging.getLogger(__name__)

_STATE_MAP = {
    "idle":   "Inaktiv",
    "active": "Läuft",
    "paused": "Pausiert",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor-Entity für den Kochtimer anlegen."""
    async_add_entities([RezepteTimerSensor(entry)])


class RezepteTimerSensor(Entity):
    """Zeigt den aktuellen Status des Rezepte-Kochtimers."""

    _attr_has_entity_name = True
    _attr_name = "Kochtimer"
    _attr_icon = "mdi:chef-hat"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_kochtimer"
        self._state = "idle"
        self._finishes_at = 0
        self._remaining_secs = 0
        self._step_num = 1

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Rezepte",
            "manufacturer": "Noack1978",
            "model": "Rezepte Integration",
        }

    @property
    def native_value(self) -> str:
        return _STATE_MAP.get(self._state, self._state)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "step_num": self._step_num,
            "remaining_seconds": self._remaining_secs,
        }
        if self._state == "active" and self._finishes_at:
            attrs["finishes_at"] = datetime.fromtimestamp(
                self._finishes_at, tz=timezone.utc
            ).isoformat()
        return attrs

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_TIMER_STATE, self._handle_update)
        )

    @callback
    def _handle_update(self, payload: dict) -> None:
        self._state = payload.get("state", "idle")
        self._finishes_at = payload.get("finishes_at", 0)
        self._remaining_secs = payload.get("remaining_secs", 0)
        self._step_num = payload.get("step_num", 1)
        self.async_write_ha_state()
