"""Heating preset adapter."""

from __future__ import annotations

from homeassistant.core import HomeAssistant


class HeatingController:
    """Control heating presets for configured entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str | None,
        eco_preset: str,
        comfort_preset: str,
    ) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._eco_preset = eco_preset
        self._comfort_preset = comfort_preset

    async def async_apply_eco(self) -> None:
        """Apply eco preset."""
        await self._async_apply_preset(self._eco_preset)

    async def async_apply_comfort(self) -> None:
        """Apply comfort preset."""
        await self._async_apply_preset(self._comfort_preset)

    async def _async_apply_preset(self, preset: str) -> None:
        if not self._entity_id:
            return

        domain = self._entity_id.split(".", 1)[0]
        state = self._hass.states.get(self._entity_id)
        if state is None:
            return
        if state.state in {"off", "unavailable", "unknown"}:
            return

        if domain == "climate":
            await self._hass.services.async_call(
                "climate",
                "set_preset_mode",
                {"entity_id": self._entity_id, "preset_mode": preset},
                blocking=True,
            )
            return

        if domain == "select":
            await self._hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": self._entity_id, "option": preset},
                blocking=True,
            )
            return

        if domain == "input_select":
            await self._hass.services.async_call(
                "input_select",
                "select_option",
                {"entity_id": self._entity_id, "option": preset},
                blocking=True,
            )
