"""Constants for the Vacation Manager integration."""

from __future__ import annotations

DOMAIN = "vacation_manager"

PLATFORMS: list[str] = ["calendar"]

CONF_VACATION_OFF_LABEL = "vacation_off_label"
CONF_VACATION_ON_LABEL = "vacation_on_label"
CONF_PRESENCE_ENTITY_ID = "presence_entity_id"
CONF_HEATING_ENTITY_ID = "heating_entity_id"
CONF_ECO_PRESET = "eco_preset"
CONF_COMFORT_PRESET = "comfort_preset"

DEFAULT_NAME = "Vacation Manager"
DEFAULT_VACATION_OFF_LABEL = "vacation_off"
DEFAULT_VACATION_ON_LABEL = "vacation_on"
DEFAULT_ECO_PRESET = "Eco"
DEFAULT_COMFORT_PRESET = "Comfort"

SERVICE_ADD_PERIOD = "add_period"
SERVICE_REMOVE_PERIOD = "remove_period"
SERVICE_SYNC = "sync"

ATTR_PERIOD_ID = "period_id"
ATTR_TITLE = "title"
ATTR_START = "start"
ATTR_END = "end"

STORAGE_VERSION = 1
SCAN_INTERVAL_SECONDS = 60

PHASE_HOME = "home"
PHASE_AWAY_ECO = "away_eco"
PHASE_AWAY_COMFORT = "away_comfort"
