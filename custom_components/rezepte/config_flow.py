"""Config Flow für die Rezepte-Integration."""
from __future__ import annotations
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from . import DOMAIN


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
    })


class RezepteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Rezepte", data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry, data=user_input, reason="reconfigure_successful"
            )
        return self.async_show_form(
            step_id="reconfigure", data_schema=_schema(entry.data)
        )
