# AGENTS.md

## Scope of this directory

`src/fpvs_studio/triggers/` contains trigger backend interfaces and optional hardware
adapter scaffolding.

## Requirements

- Keep trigger backends runtime-facing and hardware-adapter focused.
- Keep trigger planning in compiled core contracts and trigger logging/export behavior
  in runtime.
- Do not push serial-port or hardware-only settings into `RunSpec` or `SessionPlan`.
- Accept normal event marker codes only in the `1`-`255` range. Code `0` is reserved
  for explicit manual reset and must not be emitted for condition or oddball events.
- Keep unavailable hardware behavior explicit; do not add silent fallbacks that hide
  failed trigger emission.
- Let backend open/write failures propagate to runtime so they can abort and export a
  clear error record. Runtime owns the pre-run serial-open check and trigger logs.

## Restrictions

- No PySide6 imports here.
- No PsychoPy imports here.
- Do not couple trigger backends to project JSON models or GUI widgets.

## Verification

- Run `python -m pytest -q tests\unit\test_import_boundaries.py` after changing imports.
- Run runtime checks when trigger behavior changes: `.\scripts\check_runtime.ps1`.
