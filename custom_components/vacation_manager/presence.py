"""Presence simulation adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


class PresenceController:
    """Control a configured presence simulation entity."""

    def __init__(self, hass: HomeAssistant, entity_id: str | None) -> None:
        self._hass = hass
        self._entity_id = entity_id

    async def async_turn_on(self) -> None:
        """Enable presence simulation."""
        await self._async_turn(True)

    async def async_turn_off(self) -> None:
        """Disable presence simulation."""
        await self._async_turn(False)

    async def _async_turn(self, on: bool) -> None:
        if not self._entity_id:
            return

        domain = self._entity_id.split(".", 1)[0]
        service = "turn_on" if on else "turn_off"
        await self._hass.services.async_call(
            domain,
            service,
            {"entity_id": self._entity_id},
            blocking=True,
        )
