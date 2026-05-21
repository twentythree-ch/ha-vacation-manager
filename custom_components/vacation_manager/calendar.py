"""Calendar platform for vacation periods."""

from __future__ import annotations

from datetime import date

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import async_get_runtime_data
from .const import ATTR_END, ATTR_START, ATTR_TITLE
from .store import VacationStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up vacation calendar for one entry."""
    runtime = async_get_runtime_data(hass, entry.entry_id)
    async_add_entities([VacationCalendar(entry.entry_id, runtime.store)])


class VacationCalendar(CalendarEntity):
    """Expose stored periods as all-day calendar events."""

    _attr_has_entity_name = True
    _attr_name = "Vacations"

    def __init__(self, entry_id: str, store: VacationStore) -> None:
        self._entry_id = entry_id
        self._store = store
        self._event: CalendarEvent | None = None
        self._attr_unique_id = f"vacation_manager_{entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return next upcoming event."""
        return self._event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: date,
        end_date: date,
    ) -> list[CalendarEvent]:
        """Return calendar events in date range."""
        events: list[CalendarEvent] = []
        for period in self._store.periods:
            event_start = date.fromisoformat(period[ATTR_START])
            event_end = date.fromisoformat(period[ATTR_END])
            if event_end <= start_date or event_start >= end_date:
                continue
            events.append(
                CalendarEvent(
                    start=event_start,
                    end=event_end,
                    summary=period[ATTR_TITLE],
                )
            )
        return events

    async def async_update(self) -> None:
        """Update next event."""
        today = date.today()
        upcoming = [
            period for period in self._store.periods if date.fromisoformat(period[ATTR_END]) > today
        ]
        if not upcoming:
            self._event = None
            return

        period = min(upcoming, key=lambda item: item[ATTR_START])
        self._event = CalendarEvent(
            start=date.fromisoformat(period[ATTR_START]),
            end=date.fromisoformat(period[ATTR_END]),
            summary=period[ATTR_TITLE],
        )
