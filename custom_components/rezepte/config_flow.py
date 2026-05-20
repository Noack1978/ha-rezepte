"""Config Flow für die Rezepte-Integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN


class RezepteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Einrichtungs-Dialog für Rezepte."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Einrichtungsschritt – keine Eingaben nötig, nur bestätigen."""
        if user_input is not None:
            # Nur eine Instanz erlauben
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Rezepte", data={})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )
