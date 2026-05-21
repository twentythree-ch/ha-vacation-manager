# Vacation Manager for Home Assistant

Vacation Manager is a planned custom Home Assistant integration intended for distribution through HACS.

Its goal is to centralize vacation scheduling so Home Assistant can react automatically when you are away and when you are about to return.

## Intended features

- Manage multiple vacation date ranges with a UI-driven, calendar-like experience
- Turn selected automations **off** during vacations via a configurable `vacation_off` label
- Turn selected automations **on** during vacations via a configurable `vacation_on` label
- Enable Presence Simulation while away and disable it when back
- Synchronize vacation schedules to a Stiebel Eltron boiler integration
- Apply heating presets automatically:
  - `Eco` while away
  - `Comfort` starting 24 hours before returning
  - `Comfort` again once back home

## Current repository status

This repository now includes an initial implementation under `custom_components/vacation_manager`.

Implemented in this first version:

- Config flow and options flow
- Vacation period storage and services (`add_period`, `remove_period`, `sync`)
- Scheduler-based transitions for:
  - automations with `vacation_off`
  - automations with `vacation_on`
  - presence simulation on/off
  - heating presets (`Eco` during away, `Comfort` 24h before return and when back)
- Calendar entity exposing stored vacation periods

For the broader design and roadmap, see `ANALYSIS.md`.
