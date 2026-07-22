"""Sensor-Plattform für Rezepte – zeigt Kochtimer-Status und Restlaufzeit."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

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
    """Sensor-Entities für den Kochtimer anlegen."""
    async_add_entities([
        RezepteTimerSensor(entry),
        RezepteTimerRemainingSensor(entry),
    ])


def _device_info(entry: ConfigEntry) -> dict:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": "Rezepte",
        "manufacturer": "Noack1978",
        "model": "Rezepte Integration",
    }


class RezepteTimerSensor(SensorEntity):
    """Zeigt den aktuellen Status des Rezepte-Kochtimers."""

    _attr_has_entity_name = True
    _attr_name = "Kochtimer"
    _attr_icon = "mdi:chef-hat"
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_kochtimer"
        self._attr_device_info = _device_info(entry)
        self._state = "idle"
        self._finishes_at = 0
        self._remaining_secs = 0
        self._step_num = 1

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


class RezepteTimerRemainingSensor(SensorEntity):
    """Zeigt die verbleibende Zeit des Kochtimers – zählt live runter."""

    _attr_has_entity_name = True
    _attr_name = "Kochtimer Restlaufzeit"
    _attr_icon = "mdi:timer-sand"
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_kochtimer_restlaufzeit"
        self._attr_device_info = _device_info(entry)
        self._state = "idle"
        self._finishes_at = 0.0
        self._paused_remaining = 0
        self._value = 0
        self._unsub_tick = None

    @property
    def native_value(self) -> int:
        return self._value

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_TIMER_STATE, self._handle_update)
        )

    async def async_will_remove_from_hass(self) -> None:
        self._stop_ticker()

    @callback
    def _handle_update(self, payload: dict) -> None:
        self._state = payload.get("state", "idle")
        self._finishes_at = payload.get("finishes_at", 0) or 0
        self._paused_remaining = payload.get("remaining_secs", 0)

        if self._state == "active":
            self._recompute()
            self._start_ticker()
        else:
            self._stop_ticker()
            self._value = self._paused_remaining if self._state == "paused" else 0

        self.async_write_ha_state()

    def _start_ticker(self) -> None:
        if self._unsub_tick is not None:
            return
        self._unsub_tick = async_track_time_interval(
            self.hass, self._tick, timedelta(seconds=1)
        )

    def _stop_ticker(self) -> None:
        if self._unsub_tick is not None:
            self._unsub_tick()
            self._unsub_tick = None

    @callback
    def _tick(self, _now) -> None:
        self._recompute()
        if self._value <= 0:
            self._stop_ticker()
        self.async_write_ha_state()

    def _recompute(self) -> None:
        if self._state == "active" and self._finishes_at:
            self._value = max(0, round(self._finishes_at - time.time()))
        else:
            self._value = 0
