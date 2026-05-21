"""Config flow for Vacation Manager."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_COMFORT_PRESET,
    CONF_ECO_PRESET,
    CONF_HEATING_ENTITY_ID,
    CONF_PRESENCE_ENTITY_ID,
    CONF_VACATION_OFF_LABEL,
    CONF_VACATION_ON_LABEL,
    DEFAULT_COMFORT_PRESET,
    DEFAULT_ECO_PRESET,
    DEFAULT_NAME,
    DEFAULT_VACATION_OFF_LABEL,
    DEFAULT_VACATION_ON_LABEL,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): cv.string,
            vol.Required(
                CONF_VACATION_OFF_LABEL,
                default=defaults.get(CONF_VACATION_OFF_LABEL, DEFAULT_VACATION_OFF_LABEL),
            ): cv.string,
            vol.Required(
                CONF_VACATION_ON_LABEL,
                default=defaults.get(CONF_VACATION_ON_LABEL, DEFAULT_VACATION_ON_LABEL),
            ): cv.string,
            vol.Optional(
                CONF_PRESENCE_ENTITY_ID, default=defaults.get(CONF_PRESENCE_ENTITY_ID, "")
            ): cv.string,
            vol.Optional(
                CONF_HEATING_ENTITY_ID, default=defaults.get(CONF_HEATING_ENTITY_ID, "")
            ): cv.string,
            vol.Required(
                CONF_ECO_PRESET, default=defaults.get(CONF_ECO_PRESET, DEFAULT_ECO_PRESET)
            ): cv.string,
            vol.Required(
                CONF_COMFORT_PRESET,
                default=defaults.get(CONF_COMFORT_PRESET, DEFAULT_COMFORT_PRESET),
            ): cv.string,
        }
    )


class VacationManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Vacation Manager config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle first step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow handler."""
        return VacationManagerOptionsFlow(config_entry)


class VacationManagerOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self._config_entry.data, **self._config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
