# Python 3.10 Compatibility Audit

Date: 2026-03-08

## Scope

This audit pass checked the pre-Phase-5 FPVS Studio backend for:

- remaining Python 3.10 incompatibilities
- packaging/install metadata consistency
- hidden environment assumptions
- optional PsychoPy and future PySide6 dependency boundaries
- test-suite reliability in the supported Python 3.10 environment

## What Was Checked

Code and metadata review covered:

- `pyproject.toml`
- `README.md`
- backend source under `src/fpvs_studio/`
- unit and integration tests under `tests/`
- runtime/export path behavior exercised through pytest

The Python compatibility sweep explicitly looked for common 3.11+ hazards,
including:

- `datetime.UTC`
- `tomllib`
- stdlib `StrEnum`
- `typing.Self`
- `ExceptionGroup` / `except*`
- `Path.walk`
- `itertools.batched`
- `asyncio.TaskGroup`
- other obvious 3.11+/3.12+ stdlib assumptions

## Findings

### 1. Python 3.10 compatibility

No remaining Python 3.11+ stdlib dependencies were found in the repository
after the earlier `datetime.UTC` replacements.

Confirmed by inspection:

- the repo already uses a local `StrEnum` compatibility base in
  `src/fpvs_studio/core/enums.py`
- no `tomllib`, `typing.Self`, `ExceptionGroup`, or `except*` usage remains
- the code compiles cleanly under Python 3.10

### 2. Packaging/install hazards

Two install/runtime clarity issues were present:

- the package description still undersold the current backend/runtime scope
- the packaged `fpvs-studio` entry point silently returned success even though
  there is still no supported GUI or end-user CLI workflow

### 3. Environment assumptions

The repository itself does not require shared site-packages reuse for backend
imports or the default test suite.

However, the active `.venv3.10` environment currently resolves PsychoPy from a
standalone PsychoPy installation. During audit, importing PsychoPy without
redirected user directories attempted to write into `%APPDATA%\psychopy3` and
failed with a `PermissionError` while copying theme files.

That means:

- shared-base PsychoPy reuse is a convenience workflow, not a repository
  requirement
- writable PsychoPy preference directories matter in restricted environments
- tests need to isolate PsychoPy prefs/config directories explicitly

### 4. Windows path-length sensitivity

While verifying the full Python 3.10 suite, session export paths hit the
Windows `MAX_PATH` boundary because generated identifiers repeated the project
id inside `session_id` and then repeated `session_id` again inside each session
`run_id`.

This was a real test reliability and environment-hygiene issue, not just a
pytest invocation quirk.

## Fixes Made

### Code

- updated `src/fpvs_studio/app/main.py` so the packaged console entry point
  reports the real pre-GUI state and exits non-zero instead of silently
  succeeding
- shortened compiler-generated `session_id` and per-session `run_id` values in
  `src/fpvs_studio/core/compiler.py` to remove redundant prefixes and reduce
  Windows path pressure

### Tests

- expanded `tests/unit/test_import_boundaries.py` so backend imports are guarded
  against both PsychoPy and PySide6 leakage
- added `tests/unit/test_app_main.py` for the placeholder entry point behavior
- added `tests/unit/test_package_metadata.py` to guard the Python 3.10-only
  metadata and keep PsychoPy/PySide6 optional in the default dependency set
- strengthened `tests/integration/test_psychopy_engine.py` by redirecting
  `APPDATA`, `HOME`, `LOCALAPPDATA`, and `USERPROFILE` into pytest temp dirs
- added `tests/unit/test_session_plan.py` coverage to keep generated session and
  run ids free of redundant prefixes

### Documentation and metadata

- updated `pyproject.toml` description and classifiers to reflect the current
  backend/runtime scope and Python-3-only support
- updated `README.md` to document:
  - Python 3.10 only
  - quoted extras for PowerShell installs
  - default install vs optional PsychoPy engine install
  - the fact that the `gui` extra is reserved for Phase 5
  - the placeholder status of the packaged console entry point
- added `docs/ENVIRONMENT.md` to document:
  - clean isolated venv setup
  - convenience shared-base PsychoPy setup
  - PsychoPy preference-directory write behavior
  - what the current test suite does and does not require

## Verification Results

Verified in the active local environment:

- `.\\.venv3.10\\Scripts\\python --version` -> `Python 3.10.11`
- `.\\.venv3.10\\Scripts\\python -m compileall src tests` -> passed
- `.\\.venv3.10\\Scripts\\python -m pip check` -> passed
- `.\\.venv3.10\\Scripts\\python -m pytest -q --basetemp=build\\pytest_tmp_py310_audit -o cache_dir=build\\pytest_cache_py310_audit` -> `50 passed`

Additional observed environment detail:

- redirected-env PsychoPy import reported version `2025.1.1`
- in this shared-base setup, PsychoPy resolves from the standalone PsychoPy
  install rather than from the project venv itself

## Remaining Environment-Dependent or Deferred Items

Still intentionally deferred or environment-specific:

- Phase 5 PySide6 GUI work has not started
- real serial trigger hardware I/O remains deferred
- fullscreen/non-test runtime validation remains deferred
- lab-grade display timing validation on actual hardware remains unverified
- a shared-base environment may still load unrelated pytest plugins from the
  standalone PsychoPy install; this does not currently fail the suite, but it is
  external to this repository

## Recommendation

The repository is ready for Phase 5 GUI work.

Reasoning:

- no remaining Python 3.10 compatibility blockers were found in the repo
- default backend imports remain independent of PsychoPy and PySide6
- packaging/docs now describe the supported environment honestly
- PsychoPy-specific environment assumptions are documented and isolated in tests
- the Windows path-length issue uncovered during audit was fixed at the source

The remaining unknowns are hardware/runtime-environment concerns, not backend
contract stability concerns.
