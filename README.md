# FPVS Studio

FPVS Studio is an open-source desktop application for building and running fast
periodic visual stimulation (FPVS) experiments without requiring end users to
work directly in PsychoPy.

Phase 4 is a backend/runtime stabilization milestone. The PySide6 GUI is not
built yet; the currently usable surface is the engine-neutral compiler,
preprocessing pipeline, runtime/export path, and the optional PsychoPy-backed
presentation engine.

## Architecture

The repository is intentionally split into four neutral layers plus the trigger
boundary:

- `src/fpvs_studio/core/models.py`
  - editable project state persisted in `project.json`
- `src/fpvs_studio/core/run_spec.py`
  - one compiled, frame-explicit execution contract for one condition run
- `src/fpvs_studio/core/session_plan.py`
  - one ordered multi-condition session plan containing many `RunSpec` entries
- `src/fpvs_studio/core/execution.py`
  - engine-neutral run/session execution results, runtime metadata, response
    logs, frame-interval logs, and trigger logs
- `src/fpvs_studio/preprocessing/`
  - manifest-backed source and derived stimuli materialization
- `src/fpvs_studio/runtime/`
  - session preflight, session flow, trigger plumbing, and export writers
- `src/fpvs_studio/engines/`
  - swappable presentation engines; only this layer may import PsychoPy

The compile and launch flow is:

```text
project.json -> ProjectFile -> compile_run_spec(...) -> RunSpec
project.json + session settings -> compile_session_plan(...) -> SessionPlan
runtime launcher -> session preflight -> runtime session flow -> engine
engine run results -> runtime exporters -> session artifacts
```

## Current usable scope

Today, the repository supports:

- project and session modeling in the neutral core layer
- deterministic preprocessing/materialization of source and derived stimuli
- compilation from `ProjectFile` into one-condition `RunSpec` values
- compilation from `ProjectFile` plus session settings into multi-condition
  `SessionPlan` values
- runtime preflight, session execution orchestration, and rich exports
- an optional PsychoPy engine behind the engine adapter boundary

Not built yet:

- the PySide6 GUI editor/shell
- a supported end-user CLI workflow
- fullscreen/non-test launch mode
- real serial-trigger hardware I/O

## Phase 4 runtime

Phase 4 provides the first real execution vertical slice:

- runtime launches a full `SessionPlan`
- one PsychoPy window is reused across the whole session
- runtime shows per-condition instruction/transition screens
- fixed-break and manual-continue transitions are handled above the engine
- the PsychoPy engine plays each `RunSpec` directly from its compiled frame
  schedule
- fixation-task responses, frame intervals, and trigger attempts are logged
- runtime writes richer per-run and per-session exports

`RunSpec` remains strictly single-condition. `SessionPlan` remains the compiled
multi-condition session contract above it. Runtime still owns session order and
transitions; the engine still owns rendering and frame presentation.

## PsychoPy dependency

Core, preprocessing, compiler, `RunSpec`, `SessionPlan`, and runtime imports do
not require PsychoPy.

Use Python `3.10` to `3.12` for supported installs. The project metadata
currently enforces `>=3.10,<3.13`.

Install the backend/dev environment without PsychoPy:

```powershell
python -m pip install -e .[dev]
```

Install the PsychoPy engine extras when you want to exercise the optional
runtime path:

```powershell
python -m pip install -e .[dev,engine]
```

PsychoPy imports remain lazy inside `src/fpvs_studio/engines/psychopy_engine.py`.

## Tests

Run the default test suite:

```powershell
python -m pytest -q
```

The default suite does not require PsychoPy. The optional integration smoke
tests under `tests/integration/` skip automatically when PsychoPy is not
installed.

## Test mode

`test_mode` is a runtime-only launch setting and is currently required for the
supported Phase 4 launch path.

In this milestone, `test_mode=True` means:

- PsychoPy opens a windowed session instead of fullscreen
- trigger output stays on the logged null backend
- the rest of the runtime path still executes the compiled `RunSpec` /
  `SessionPlan` contracts
- fullscreen/non-test launches are intentionally rejected until later phases

## Exports

Runtime writes neutral artifacts under `runs/...`, including:

- `session_plan.json`
- `session_summary.json`
- `run_summary.json`
- `runtime_metadata.json`
- `runspec.json`
- `events.csv`
- `fixation_events.csv`
- `responses.csv`
- `frame_intervals.csv`
- `trigger_log.csv`

See [docs/RUNSPEC.md](docs/RUNSPEC.md),
[docs/SESSION_PLAN.md](docs/SESSION_PLAN.md), and
[docs/RUNTIME_EXECUTION.md](docs/RUNTIME_EXECUTION.md) for the current contract
split.

## Core Concepts

- `ProjectFile`
  - editable project state stored in `project.json`
- `RunSpec`
  - one compiled, frame-explicit plan for one condition run
- `SessionPlan`
  - one ordered multi-condition session made of many `RunSpec` entries
- `RunExecutionSummary` / `SessionExecutionSummary`
  - neutral execution/export records written by the runtime after playback

## Deferred v1 items

The following remain intentionally deferred after the Phase 4 audit pass:

- the Phase 5 GUI work
- real serial-port trigger output
- non-PsychoPy presentation backends
- additional task variants beyond fixation-cross response logging
