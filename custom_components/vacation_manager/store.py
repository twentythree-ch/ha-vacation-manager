"""Storage handling for vacation periods."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from .const import ATTR_END, ATTR_PERIOD_ID, ATTR_START, ATTR_TITLE, DOMAIN, STORAGE_VERSION


class VacationStore:
    """Persist and query vacation periods."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store = Store[dict](hass, STORAGE_VERSION, f"{DOMAIN}_{entry_id}_periods")
        self._periods: list[dict] = []

    @property
    def periods(self) -> list[dict]:
        """Return a copy of periods."""
        return list(self._periods)

    async def async_load(self) -> None:
        """Load periods from storage."""
        data = await self._store.async_load() or {}
        self._periods = data.get("periods", [])

    async def async_save(self) -> None:
        """Persist periods."""
        await self._store.async_save({"periods": self._periods})

    async def async_add_period(self, title: str, start: str, end: str) -> dict:
        """Add a new period."""
        start_date = _parse_date(start)
        end_date = _parse_date(end)
        if end_date <= start_date:
            raise ValueError(
                "End date must be after start date. End is the return date (exclusive)."
            )

        period = {
            ATTR_PERIOD_ID: str(uuid4()),
            ATTR_TITLE: title.strip() or "Vacation",
            ATTR_START: start_date.isoformat(),
            ATTR_END: end_date.isoformat(),
        }
        self._periods.append(period)
        self._periods.sort(key=lambda item: item[ATTR_START])
        await self.async_save()
        return period

    async def async_remove_period(self, period_id: str) -> bool:
        """Remove a period by id."""
        before = len(self._periods)
        self._periods = [period for period in self._periods if period.get(ATTR_PERIOD_ID) != period_id]
        if len(self._periods) == before:
            return False
        await self.async_save()
        return True

    def get_active_period(self) -> dict | None:
        """Return currently active period based on local date."""
        local_date = dt_util.now().date()
        for period in self._periods:
            start = _parse_date(period[ATTR_START])
            end = _parse_date(period[ATTR_END])
            if start <= local_date < end:
                return period
        return None

    @staticmethod
    def is_pre_return_window(period: dict) -> bool:
        """Return True when in the 24h pre-return window."""
        local_date = dt_util.now().date()
        end = _parse_date(period[ATTR_END])
        return local_date >= end - timedelta(days=1)


def _parse_date(value: str) -> date:
    """Parse ISO date value."""
    return date.fromisoformat(value)
