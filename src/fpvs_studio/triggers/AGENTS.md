# AGENTS.md

## Scope of this directory

`src/fpvs_studio/triggers/` contains trigger backend interfaces and optional hardware
adapter scaffolding.

## Requirements

- Keep trigger backends runtime-facing and hardware-adapter focused.
- Keep trigger planning in compiled core contracts and trigger logging/export behavior
  in runtime.
- Do not push serial-port or hardware-only settings into `RunSpec` or `SessionPlan`.
- Keep unavailable hardware behavior explicit; do not add silent fallbacks that hide
  failed trigger emission.

## Restrictions

- No PySide6 imports here.
- No PsychoPy imports here.
- Do not couple trigger backends to project JSON models or GUI widgets.

## Verification

- Run `python -m pytest -q tests\unit\test_import_boundaries.py` after changing imports.
- Run runtime checks when trigger behavior changes: `.\scripts\check_runtime.ps1`.
