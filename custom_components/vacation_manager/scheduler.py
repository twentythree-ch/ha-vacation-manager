"""Vacation transition scheduler."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_VACATION_OFF_LABEL,
    CONF_VACATION_ON_LABEL,
    PHASE_AWAY_COMFORT,
    PHASE_AWAY_ECO,
    PHASE_HOME,
    SCAN_INTERVAL_SECONDS,
)
from .heating import HeatingController
from .presence import PresenceController
from .store import VacationStore

_LOGGER = logging.getLogger(__name__)


class VacationScheduler:
    """Apply transitions when vacation phase changes."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: VacationStore,
        config: dict,
        presence: PresenceController,
        heating: HeatingController,
    ) -> None:
        self._hass = hass
        self._store = store
        self._config = config
        self._presence = presence
        self._heating = heating
        self._phase = PHASE_HOME
        self._cancel: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Start periodic checks."""
        self._cancel = async_track_time_interval(
            self._hass, self._async_tick, timedelta(seconds=SCAN_INTERVAL_SECONDS)
        )
        await self.async_sync_now()

    async def async_stop(self) -> None:
        """Stop periodic checks."""
        if self._cancel:
            self._cancel()
            self._cancel = None

    async def async_sync_now(self) -> None:
        """Force one transition evaluation."""
        await self._async_tick()

    async def _async_tick(self, *_: object) -> None:
        period = self._store.get_active_period()
        if period is None:
            new_phase = PHASE_HOME
        elif self._store.is_pre_return_window(period):
            new_phase = PHASE_AWAY_COMFORT
        else:
            new_phase = PHASE_AWAY_ECO

        if new_phase == self._phase:
            return

        old_phase = self._phase
        self._phase = new_phase
        _LOGGER.debug("Vacation phase changed from %s to %s", old_phase, new_phase)

        if old_phase == PHASE_HOME and new_phase in {PHASE_AWAY_ECO, PHASE_AWAY_COMFORT}:
            await self._async_on_away_started()

        if new_phase == PHASE_HOME:
            await self._async_on_home_arrived()
            return

        if new_phase == PHASE_AWAY_ECO:
            await self._heating.async_apply_eco()
        elif new_phase == PHASE_AWAY_COMFORT:
            await self._heating.async_apply_comfort()

    async def _async_on_away_started(self) -> None:
        await self._async_toggle_labelled_automations(
            self._config.get(CONF_VACATION_OFF_LABEL, ""), turn_on=False
        )
        await self._async_toggle_labelled_automations(
            self._config.get(CONF_VACATION_ON_LABEL, ""), turn_on=True
        )
        await self._presence.async_turn_on()

    async def _async_on_home_arrived(self) -> None:
        await self._async_toggle_labelled_automations(
            self._config.get(CONF_VACATION_OFF_LABEL, ""), turn_on=True
        )
        await self._async_toggle_labelled_automations(
            self._config.get(CONF_VACATION_ON_LABEL, ""), turn_on=False
        )
        await self._presence.async_turn_off()
        await self._heating.async_apply_comfort()

    async def _async_toggle_labelled_automations(self, label_name: str, turn_on: bool) -> None:
        if not label_name:
            return

        label_id = self._label_id_from_name(label_name)
        if label_id is None:
            return

        entity_registry = er.async_get(self._hass)
        service = "turn_on" if turn_on else "turn_off"

        for entry in entity_registry.entities.values():
            if entry.domain != "automation":
                continue
            if label_id not in entry.labels:
                continue
            await self._hass.services.async_call(
                "automation",
                service,
                {"entity_id": entry.entity_id},
                blocking=True,
            )

    def _label_id_from_name(self, label_name: str) -> str | None:
        label_registry = lr.async_get(self._hass)
        for label_id, item in label_registry.labels.items():
            if item.name == label_name:
                return label_id
        return None
