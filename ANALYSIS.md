# Vacation Manager — Integration Analysis & Implementation Plan

## Overview

This document analyses how to build a **Vacation Manager** custom integration for Home Assistant that can be distributed via HACS. It describes the chosen architecture, the reasoning behind each decision, and a concrete step-by-step implementation plan.

---

## Requirements Recap

| # | Requirement |
|---|-------------|
| 1 | Define multiple date ranges (start, end, title) where one is away |
| 2 | Configure those ranges through a UI (calendar-like experience) |
| 3 | Select which automations to turn off while away, using a tag/label |
| 4 | Select which automations to turn on while away, using a second tag/label |
| 5 | Turn on presence simulation while away and turn it off when back |
| 6 | Synchronise vacation periods to a Stiebel Eltron boiler (one-way, HA → boiler) |
| 7 | Apply heating presets: Eco during vacations, Comfort 24h before return, Comfort when back |

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Home Assistant                            │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │         Vacation Manager Integration    │                │
│  │                                         │                │
│  │  ┌─────────────┐  ┌──────────────────┐ │                │
│  │  │  Config Flow │  │   Data Storage   │ │                │
│  │  │  (UI setup)  │  │  (.storage/vm)   │ │                │
│  │  └─────────────┘  └──────────────────┘ │                │
│  │                                         │                │
│  │  ┌─────────────┐  ┌──────────────────┐ │                │
│  │  │  Scheduler   │  │  REST API /      │ │                │
│  │  │  (date check)│  │  Services        │ │                │
│  │  └─────────────┘  └──────────────────┘ │                │
│  │                                         │                │
│  │  ┌─────────────────────────────────┐   │                │
│  │  │        Lovelace Panel           │   │                │
│  │  │  (calendar-like vacation UI)    │   │                │
│  │  └─────────────────────────────────┘   │                │
│  └─────────────────────────────────────────┘                │
│          │                    │                              │
│          ▼                    ▼                              │
│  ┌──────────────┐   ┌──────────────────────┐               │
│  │  Automations │   │  Stiebel Eltron ISG  │               │
│  │  / Presence  │   │  Integration         │               │
│  │  Simulation  │   │  (vacation + presets)│               │
│  └──────────────┘   └──────────────────────┘               │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Date Range Management

### 2.1 Data Model

Each vacation period is stored as a plain dictionary:

```python
{
    "id": "uuid4-string",
    "title": "Summer holidays",
    "start": "2024-07-15",   # ISO 8601 date string
    "end":   "2024-07-29",
}
```

A list of these objects is persisted via HA's built-in `homeassistant.helpers.storage.Store` helper (`Store(hass, 1, "vacation_manager_periods")`). This means data survives restarts and does not require a database.

### 2.2 Calendar UI Options

Three approaches were evaluated:

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| **HA local calendar entity** | Native HA calendar UI; no extra code | Read-only in UI; needs HA 2022.12+; limited custom fields | ✅ **Primary** |
| Custom Lovelace panel (React/Lit) | Full control of UI | Much more code, JS build pipeline | ✅ **Complement** |
| Google Calendar / CalDAV sync | Familiar interface | Requires cloud account; complex OAuth | ❌ Out of scope v1 |

**Chosen approach:** The integration creates a **local calendar entity** (platform `calendar`) for each config entry. Users can view and (through HA 2023.4+) create/edit events via the built-in Calendar card. Internally, the integration treats each calendar event as a vacation period. A custom **Lovelace panel** (simple HTML/JS, no build step) is also provided as an optional fallback for older HA versions, accessible via the sidebar.

### 2.3 Calendar Entity

`VacationCalendar(CalendarEntity)` is registered via the `calendar` platform. It implements:

- `async_get_events(hass, start_date, end_date)` — returns `CalendarEvent` objects.
- `create_event` / `delete_event` / `update_event` — write-through to the `Store`.

HA's built-in Calendar card can then render and edit the events without any extra JavaScript.

---

## 3. Automation Management

### 3.1 Tagging Automations

Home Assistant has supported **labels** on automations since version 2023.9. The user assigns:

- a label such as `vacation_off` to automations that should be disabled during vacation
- a label such as `vacation_on` to automations that should be enabled during vacation

Both label names are configurable inside the integration's config flow so they can be customised per installation.

Using labels is preferred over a custom registry because:
- Labels are a first-class HA concept visible in the UI.
- They survive integration reloads.
- They can be applied to multiple entity types (automations, scripts, etc.).

### 3.2 Enable / Disable Logic

A `VacationScheduler` component checks every minute (using `async_track_time_interval`) whether the current time falls inside any stored vacation period and whether the system is within the **24-hour pre-return window** before the end of the active vacation. If a transition occurs:

1. **Vacation starts** → call `automation.turn_off` for every automation with the configured `vacation_off` label.
2. **Vacation starts** → call `automation.turn_on` for every automation with the configured `vacation_on` label.
3. **24h before return** → switch heating preset from Eco to Comfort so the house can warm up before arrival.
4. **Vacation ends** → restore normal state: turn `vacation_off` automations back on, turn `vacation_on` automations back off, and ensure the heating preset is Comfort.

To avoid flapping, state is cached in memory and only real transitions (off→on, on→off) trigger service calls.

### 3.3 Label Registration

At config-entry setup, the integration reads `hass.data["entity_registry"]` to find automations labelled with the configured label names. These lists are refreshed whenever the entity registry changes.

### 3.4 Presence Simulation

The integration also manages the **Presence Simulation** integration as part of the vacation lifecycle. The preferred approach is to let the user select the relevant entity in the config flow:

- a `switch` entity if Presence Simulation exposes a switch
- otherwise a script or service target if that integration is controlled via service calls

Lifecycle:

1. **Vacation starts** → turn Presence Simulation on
2. **Vacation ends** → turn Presence Simulation off

This should be modeled as a dedicated adapter so the core scheduler only emits high-level state transitions (`away_started`, `pre_return`, `away_ended`).

---

## 4. Stiebel Eltron Boiler Synchronisation

### 4.1 Stiebel Eltron ISG Integration

The official **Stiebel Eltron ISG** integration (`stiebel_eltron`) exposes entities such as:

- `number.stiebel_eltron_vacation_start_date` (or similar)
- `number.stiebel_eltron_vacation_end_date`
- `switch.stiebel_eltron_vacation_mode`
- climate / select / number entities related to heating presets or operation modes

> **Note:** Entity names differ by firmware/ISG model. The integration must allow the user to **map** the correct entities from their Stiebel Eltron device during configuration (entity picker in the config flow).

### 4.2 Sync Strategy

Sync is **one-way: Vacation Manager → boiler**. No sync back.

When a vacation period is created or updated:

1. Find the *next upcoming* vacation period (or the currently active one).
2. Write start and end dates to the configured Stiebel Eltron entities using `hass.services.async_call("number", "set_value", ...)` and `hass.services.async_call("switch", "turn_on", ...)`.
3. If the vacation is active, apply the configured **Eco** preset to the heating.
4. If the current time is within 24 hours of the vacation end, apply the configured **Comfort** preset instead.
5. If no vacation period is active or upcoming, write a safe default (e.g. reset dates, turn off vacation switch, apply Comfort).

The sync is triggered by:
- Any CRUD operation on vacation periods (create / update / delete).
- HA startup (to restore state after restart).
- A manual service call `vacation_manager.sync_boiler`.

### 4.3 Boiler Date Format

Stiebel Eltron ISG typically expects dates as individual day/month/year number entities. The sync layer converts ISO date strings to the required format. Exact entity names and format are detected at runtime; if entities are not found, a warning is logged and sync is skipped gracefully.

### 4.4 Heating Preset Handling

Heating support should be configuration-driven because the exact Stiebel entities vary by model. The config flow should therefore allow the user to map either:

- a climate entity that supports `climate.set_preset_mode`
- a select entity for operating mode
- or an alternative service/entity combination exposed by the Stiebel integration

The integration stores two preset values:

- **Away preset**: typically `Eco`
- **Return preset**: typically `Comfort`

The scheduler then applies:

- `Eco` from vacation start until 24h before return
- `Comfort` from 24h before return onward
- `Comfort` after vacation end

---

## 5. HACS Distribution

HACS requires the following structure inside the repository:

```
ha-vacation-manager/
├── hacs.json                        # HACS metadata
├── README.md
├── ANALYSIS.md                      # This document
├── custom_components/
│   └── vacation_manager/
│       ├── manifest.json            # HA integration manifest
│       ├── __init__.py              # Entry point / setup
│       ├── config_flow.py           # UI config flow
│       ├── const.py                 # Constants
│       ├── calendar.py              # CalendarEntity platform
│       ├── scheduler.py             # Vacation scheduler
│       ├── boiler_sync.py           # Stiebel Eltron sync
│       ├── services.yaml            # Service descriptions
│       ├── strings.json             # UI strings (English)
│       └── translations/
│           └── en.json
└── www/                             # Optional custom panel assets
    └── vacation_manager_panel.js
```

`hacs.json` example:
```json
{
  "name": "Vacation Manager",
  "content_in_root": false,
  "homeassistant": "2023.9.0"
}
```

---

## 6. Step-by-Step Implementation Plan

### Phase 1 — Project Skeleton

- [ ] Create `hacs.json`
- [ ] Create `custom_components/vacation_manager/` directory
- [ ] Create `manifest.json` with domain, version, dependencies (`homeassistant`)
- [ ] Create empty `__init__.py`, `const.py`
- [ ] Add placeholder `strings.json` and `translations/en.json`

### Phase 2 — Core Data Layer

- [ ] Define `VacationPeriod` dataclass in `models.py`
- [ ] Implement `VacationStore` (wrapper around `Store`) in `store.py`:
  - `async_load()`, `async_save()`, `async_add()`, `async_update()`, `async_remove()`
- [ ] Write unit tests for `VacationStore`

### Phase 3 — Config Flow & Options Flow

- [ ] Implement `VacationManagerConfigFlow` in `config_flow.py`:
  - Step 1: Integration name / label names for `vacation_off` and `vacation_on`
  - Step 2: Presence Simulation entity / service mapping
  - Step 3: Optional Stiebel Eltron entity mapping and preset values (`Eco`, `Comfort`)
- [ ] Implement `VacationManagerOptionsFlow` for changing settings post-setup
- [ ] Add corresponding strings to `strings.json` / `translations/en.json`

### Phase 4 — Calendar Platform

- [ ] Implement `VacationCalendar(CalendarEntity)` in `calendar.py`:
  - `async_get_events()`
  - `create_event()`, `update_event()`, `delete_event()`
- [ ] Register platform in `__init__.py` via `async_setup_entry()`
- [ ] Write tests for calendar entity

### Phase 5 — Automation Scheduler

- [ ] Implement `VacationScheduler` in `scheduler.py`:
  - Periodic check using `async_track_time_interval` (every 60 s)
  - `_get_labeled_automations()` using entity registry
  - `_start_vacation()` / `_enter_pre_return_window()` / `_end_vacation()` transitions
- [ ] Integrate scheduler lifecycle with config entry (start on load, stop on unload)
- [ ] Write tests for scheduler logic

### Phase 6 — Stiebel Eltron Boiler Sync

- [ ] Implement `BoilerSync` in `boiler_sync.py`:
  - `async_sync(hass, vacation_period)` — write to mapped entities
  - `async_clear(hass)` — reset boiler vacation
  - Date format conversion utilities
- [ ] Implement heating preset handling inside boiler sync / climate adapter:
  - apply away preset during vacation
  - apply return preset 24h before vacation end
  - apply return preset after vacation end
- [ ] Call `BoilerSync.async_sync` after every store write
- [ ] Expose `vacation_manager.sync_boiler` service
- [ ] Write tests (with mocked `hass.services.async_call`)

### Phase 7 — Services

- [ ] Define services in `services.yaml`:
  - `vacation_manager.add_period` (title, start, end)
  - `vacation_manager.remove_period` (id)
  - `vacation_manager.sync_boiler`
- [ ] Implement service handlers in `__init__.py`
- [ ] Register services in `async_setup_entry()`

### Phase 8 — Presence Simulation Adapter

- [ ] Implement `presence.py` adapter:
  - `async_turn_on()`
  - `async_turn_off()`
- [ ] Trigger it from scheduler transitions
- [ ] Write tests for presence simulation activation/deactivation

### Phase 9 — Optional Lovelace Panel

- [ ] Create `www/vacation_manager_panel.js` (vanilla JS / Lit):
  - List upcoming vacation periods
  - Add / edit / delete periods via service calls
  - Display current vacation status
  - Display whether pre-return heating mode is active
- [ ] Register panel in `__init__.py` via `hass.components.frontend.async_register_built_in_panel` or `async_register_extra_html_url`

### Phase 10 — Testing & CI

- [ ] Configure `pytest` with `pytest-homeassistant-custom-component` fixture
- [ ] Write integration tests for config flow
- [ ] Write integration tests for calendar + store interaction
- [ ] Write integration tests for:
  - `vacation_off` and `vacation_on` labels
  - Presence Simulation transitions
  - heating preset transitions at vacation start / 24h before return / return home
- [ ] Add GitHub Actions workflow for lint (`ruff`), type check (`mypy`), and test (`pytest`)

### Phase 11 — Documentation & Release

- [ ] Update `README.md` with installation instructions, configuration guide, usage examples
- [ ] Add `CHANGELOG.md`
- [ ] Tag first release (`v0.1.0`) and submit to HACS default repository list

---

## 7. Key Design Decisions & Trade-offs

| Decision | Rationale |
|---|---|
| Use HA `Store` (not SQLite) | Simple, no external dependencies, backed up with HA config |
| Labels instead of custom tags | Native HA feature; visible in HA UI without extra code |
| Separate `vacation_off` and `vacation_on` labels | Supports both suppression and activation use-cases without hard-coded entity lists |
| Calendar entity (not custom panel) | Re-uses built-in HA Calendar card; less code, better UX |
| Custom panel as fallback | Supports older HA versions and provides richer vacation-specific UX |
| One-way boiler sync | Avoids conflict resolution complexity; boiler schedule is treated as a write-only sink |
| Entity picker for boiler mapping | Boiler entity names differ by ISG firmware — hard-coding would break installations |
| Presence Simulation as an adapter | Keeps scheduler generic and allows switch/service-based implementations |
| 24h pre-return state | Matches heating lead time requirement without changing calendar data model |
| `async_track_time_interval` (60 s) | Low overhead; acceptable latency for vacation start/end transitions |

---

## 8. Dependencies

| Dependency | Version Constraint | Reason |
|---|---|---|
| `homeassistant` | ≥ 2023.9.0 | Label support on automations |
| `pytest-homeassistant-custom-component` | dev only | Integration testing |
| `ruff` | dev only | Linting |
| `mypy` | dev only | Type checking |

No additional Python packages (beyond what HA ships) are required at runtime.

---

## 9. Security & Privacy Considerations

- All vacation data is stored locally in HA's `.storage/` directory. No data leaves the local network.
- The Stiebel Eltron sync writes to entities already accessible within the HA instance; no new network connections are opened.
- Service calls (`add_period`, `remove_period`) should be restricted to HA admin users by default using `context.user_id` checks.

---

*Analysis written: 2026-05-21. Ready for implementation.*
