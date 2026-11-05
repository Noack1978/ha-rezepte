"""Config Flow für die Rezepte-Integration."""
from __future__ import annotations
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import DOMAIN


def _suggest(defaults: dict, key: str) -> dict:
    """Vorbelegung nur bei vorhandenem Wert.

    Ein leerer String als `default` ist fuer einen EntitySelector ungueltig
    und macht das Feld faktisch zum Pflichtfeld – deshalb nur suggested_value.
    """
    value = defaults.get(key)
    return {"suggested_value": value} if value else {}


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Leere optionale Entity-Felder entfernen."""
    return {k: v for k, v in user_input.items() if v not in ("", None)}


def _schema(defaults: dict) -> vol.Schema:
    return vol.Schema({
        vol.Optional(
            "alexa_players",
            default=defaults.get("alexa_players", []),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=True)
        ),
        vol.Optional(
            "tts_players",
            default=defaults.get("tts_players", []),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="media_player", multiple=True)
        ),
        vol.Optional(
            "tts_engine",
            default=defaults.get("tts_engine", "tts.google_translate_de_de"),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="tts")
        ),
        vol.Optional(
            "airfryer_temp_entity",
            description=_suggest(defaults, "airfryer_temp_entity"),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        ),
        vol.Optional(
            "airfryer_time_entity",
            description=_suggest(defaults, "airfryer_time_entity"),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        ),
        vol.Optional(
            "airfryer_start_entity",
            description=_suggest(defaults, "airfryer_start_entity"),
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="button")
        ),
    })


class RezepteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Rezepte", data=_clean(user_input))
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = _clean(user_input)
            # automatisch angelegten Zugriffstoken beim Neukonfigurieren behalten
            if entry.data.get("api_token"):
                data["api_token"] = entry.data["api_token"]
            return self.async_update_reload_and_abort(
                entry, data=data, reason="reconfigure_successful"
            )
        return self.async_show_form(
            step_id="reconfigure", data_schema=_schema(entry.data)
        )
