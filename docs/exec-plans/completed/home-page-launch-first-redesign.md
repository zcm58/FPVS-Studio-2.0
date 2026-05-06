# Home Page Launch-First Redesign

Status: Completed

Completed: 2026-05-06

## Summary

Redesign Home as a simple returning-user launch surface. Keep project title,
description, essential session metadata, readiness status, project utility actions, and a
dominant centered `Launch Experiment` action.

## Key Changes

- Preserve existing Home workflow and action object names.
- Replace the card-heavy Home layout with:
  - project title and description
  - evenly arranged utility actions
  - centered launch panel with readiness, condition count, block count, fixation task,
    accuracy task, and launch button
- Add a reusable home-launch action helper in `gui.components` with a play icon.
- Remove root path, template, order strategy, alpha runtime note, and detailed readiness
  checklist from Home.

## Test Plan

- Focused pytest-qt Home layout tests.
- `python -m ruff check src tests`
- `.\scripts\check_gui.ps1`
- `.\scripts\check_quality.ps1`

## Assumptions

- Home is optimized for returning experiment operators.
- Detailed readiness remains available outside Home.
- The launch button remains blue and uses a green play icon affordance.
