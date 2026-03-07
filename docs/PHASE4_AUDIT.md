# Phase 4 Audit

## Purpose

This document records the Phase 4 audit/stabilization pass completed before
Phase 5 GUI work.

The goal of the pass was to verify that the backend layers are internally
consistent, that runtime/export behavior matches the compiled plans, and that
the PsychoPy boundary remains isolated.

## What Was Audited

- architecture boundaries across `core`, `preprocessing`, `runtime`,
  `engines`, and `triggers`
- `RunSpec` and `SessionPlan` compilation/consumption alignment
- runtime preflight behavior and failure modes
- fixation scoring and response logging
- trigger logging seam behavior
- run/session export fidelity
- optional PsychoPy integration coverage
- install/testing/runtime docs for non-expert contributors

## Boundary Audit Result

Passed:

- no PsychoPy imports were found under `core` or `preprocessing`
- `RunSpec` remains a single-condition contract
- `SessionPlan` remains the multi-condition session contract
- runtime still owns session sequencing and transition flow
- engines still consume one `RunSpec` at a time
- export/result schemas remain core-owned
- `runtime/session_export.py` remains a runtime writer module rather than an
  engine implementation surface

Fixed:

- `RuntimeMetadata` exposed a `psychopy_version` field in the core layer
  contract. This was an engine-specific leak into a core-owned schema.
  The field was removed and the PsychoPy engine now populates the existing
  generic `engine_version` field instead.

## Compiler/Runtime Alignment Result

Verified:

- session block order remains deterministic for a fixed session seed
- runtime iterates `SessionPlan.ordered_entries()` in order
- condition instructions are passed into transition screens
- fixed-break and manual-continue transition settings are preserved into
  runtime flow
- trigger events compiled into `RunSpec` flow through runtime to the logged
  trigger backend
- fixation responses are scored against compiled fixation frame windows

Hardened:

- runtime preflight now rejects malformed compiled timing earlier:
  - non-contiguous stimulus timing
  - fixation events extending beyond run duration
  - trigger events outside the compiled frame range
  - stimulus sequence counts/timing drift relative to `DisplayRunSpec`

## Export Audit Result

Verified:

- per-session `run_results` order matches `SessionPlan.ordered_entries()`
- exported session seed and realized block orders match the compiled
  `SessionPlan`
- aggregated fixation/response/trigger CSV counts line up with run summaries
- exported fixation rows preserve compiled event timing

Fixed:

- per-run `display_report.json` previously contained `DisplayRunSpec`, not a
  real compatibility report. It now exports a display validation report derived
  from the compiled run timing.
- the undocumented session-level `display_report.json` export was removed
  because it was ambiguous and did not correspond to a stable session contract.

## Runtime/Test-Mode Audit Result

Fixed:

- the launch path did not enforce the current locked v1 behavior that
  `test_mode` is required. Launch entry points now reject `test_mode=False`
  with a clear runtime error.
- launch settings now fail early on invalid `display_index` values and blank
  `serial_port` values.

## PsychoPy Audit Result

Verified by code inspection:

- PsychoPy imports remain lazy inside `engines/psychopy_engine.py`
- one window is reused across a launched session
- playback remains frame-driven from compiled `RunSpec` events
- trigger emission still has a clear on-flip seam

Improved coverage:

- optional PsychoPy integration tests still skip cleanly when PsychoPy is not
  installed
- when PsychoPy is installed, the integration suite now includes a tiny
  windowed `run_condition(...)` smoke test in addition to session open/close

Unverified in this environment:

- real PsychoPy execution, because PsychoPy was not installed during this pass
- real serial trigger hardware I/O
- lab-grade timing validation on actual display hardware

## Docs/Install Audit Result

Improved:

- README now states the current usable scope more explicitly
- installation guidance now distinguishes backend/dev installs from the
  optional PsychoPy engine install
- testing guidance now explains the default PsychoPy-independent suite and the
  optional integration skip behavior
- docs now state that Phase 4 launch is currently test-mode only
- contract docs now explain export relationships more explicitly

## Tests Added/Updated

- `tests/unit/test_import_boundaries.py`
  - added a static AST-based guard that confines PsychoPy imports to
    `src/fpvs_studio/engines/`
- `tests/unit/test_runtime_launcher.py`
  - added export fidelity assertions
  - added session order/export aggregation assertions
  - added launch-setting failure-mode assertions
- `tests/unit/test_runtime_preflight.py`
  - added malformed timing coverage for stimulus/fixation/trigger schedules
- `tests/unit/test_runtime_fixation.py`
  - added no-response and out-of-window response edge cases
- `tests/integration/test_psychopy_engine.py`
  - added an optional tiny playback smoke test

## Remaining Deferred Items

- PySide6 GUI work (Phase 5)
- real serial-port trigger output
- fullscreen/non-test runtime mode
- hardware-backed display timing verification
- non-PsychoPy engine implementations

## Residual Risks Before Phase 5

- The backend is not blocked on architecture or contract instability, but the
  real PsychoPy path still lacks validation in this environment because the
  dependency was absent.
- Trigger behavior is trustworthy as a logging seam, not as verified hardware
  I/O.
- The runtime still uses a single generic transition screen path for
  per-condition instructions and inter-condition flow; Phase 5 GUI work should
  preserve the current contract semantics even if the UX presentation improves.

## Recommendation

The repository is ready for Phase 5 GUI work.

Reasoning:

- the core/runtime/engine boundaries remain intact
- compilation and runtime sequencing are covered by tests
- export artifacts are more trustworthy after the display-report correction
- invalid launch/timing cases now fail earlier and more clearly
- remaining unknowns are mainly environment/hardware validation items, not
  backend contract instability
