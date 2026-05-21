"""Vacation Manager integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_END,
    ATTR_PERIOD_ID,
    ATTR_START,
    ATTR_TITLE,
    CONF_COMFORT_PRESET,
    CONF_ECO_PRESET,
    CONF_HEATING_ENTITY_ID,
    CONF_PRESENCE_ENTITY_ID,
    DEFAULT_COMFORT_PRESET,
    DEFAULT_ECO_PRESET,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_PERIOD,
    SERVICE_REMOVE_PERIOD,
    SERVICE_SYNC,
)
from .heating import HeatingController
from .presence import PresenceController
from .scheduler import VacationScheduler
from .store import VacationStore

_LOGGER = logging.getLogger(__name__)


@dataclass
class VacationRuntimeData:
    """Runtime state for one config entry."""

    store: VacationStore
    scheduler: VacationScheduler


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration from yaml (unused)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Vacation Manager from a config entry."""
    config = {**entry.data, **entry.options}
    store = VacationStore(hass, entry.entry_id)
    await store.async_load()

    presence = PresenceController(hass, config.get(CONF_PRESENCE_ENTITY_ID))
    heating = HeatingController(
        hass,
        config.get(CONF_HEATING_ENTITY_ID),
        config.get(CONF_ECO_PRESET, DEFAULT_ECO_PRESET),
        config.get(CONF_COMFORT_PRESET, DEFAULT_COMFORT_PRESET),
    )
    scheduler = VacationScheduler(hass, store, config, presence, heating)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = VacationRuntimeData(store=store, scheduler=scheduler)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_PERIOD):
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_PERIOD,
            _service_add_period(hass),
            schema=vol.Schema(
                {
                    vol.Required(ATTR_TITLE): cv.string,
                    vol.Required(ATTR_START): cv.string,
                    vol.Required(ATTR_END): cv.string,
                }
            ),
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_REMOVE_PERIOD,
            _service_remove_period(hass),
            schema=vol.Schema({vol.Required(ATTR_PERIOD_ID): cv.string}),
        )
        hass.services.async_register(DOMAIN, SERVICE_SYNC, _service_sync(hass))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await scheduler.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    runtime = async_get_runtime_data(hass, entry.entry_id)
    await runtime.scheduler.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def async_get_runtime_data(hass: HomeAssistant, entry_id: str) -> VacationRuntimeData:
    """Return runtime data for config entry."""
    return hass.data[DOMAIN][entry_id]


def _service_add_period(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> None:
        period_added = False
        for runtime in hass.data.get(DOMAIN, {}).values():
            try:
                await runtime.store.async_add_period(
                    call.data[ATTR_TITLE],
                    call.data[ATTR_START],
                    call.data[ATTR_END],
                )
            except ValueError as exc:
                _LOGGER.error("Failed adding vacation period: %s", exc)
                continue
            period_added = True
            await runtime.scheduler.async_sync_now()

        if not period_added:
            _LOGGER.warning("No Vacation Manager entries available for add_period service")

    return handler


def _service_remove_period(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> None:
        for runtime in hass.data.get(DOMAIN, {}).values():
            removed = await runtime.store.async_remove_period(call.data[ATTR_PERIOD_ID])
            if removed:
                await runtime.scheduler.async_sync_now()
                return
        _LOGGER.warning("Vacation period %s was not found", call.data[ATTR_PERIOD_ID])

    return handler


def _service_sync(hass: HomeAssistant):
    async def handler(call: ServiceCall) -> None:
        for runtime in hass.data.get(DOMAIN, {}).values():
            await runtime.scheduler.async_sync_now()

    return handler
