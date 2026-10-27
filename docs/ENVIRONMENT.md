# Environment Guide

## Supported Runtime

FPVS Studio supports Python `3.10` only.

This is enforced in:

- `pyproject.toml` via `requires-python = ">=3.10,<3.11"`
- Ruff via `target-version = "py310"`
- mypy via `python_version = "3.10"`

## Recommended Local Setup

PowerShell:

```powershell
py -3.10 -m venv .venv3.10
.\.venv3.10\Scripts\python -m pip install -U 'pip>=26.2'
.\.venv3.10\Scripts\python -m pip install -e '.[dev]'
```

Install the optional PsychoPy engine extra when you want to exercise the launch
path:

```powershell
.\.venv3.10\Scripts\python -m pip install -e '.[dev,engine]'
```

Install the packaging extra when you want to build the Windows executable:

```powershell
.\.venv3.10\Scripts\python -m pip install -e ".[dev,engine,packaging]"
```

Notes:

- the default install includes PySide6 because the GUI is now the primary app
  surface
- repo wrapper scripts resolve the local Python from `.venv3.10` first and `.venv`
  second, so agents can use the scripts even when a checkout was prepared with the
  shorter environment name
- PsychoPy remains optional at install time and is still confined to
  `src/fpvs_studio/engines/`
- the dev extra includes `pytest`, `pytest-qt`, and `pytest-timeout` for GUI
  verification, and `pytest-xdist` for parallel non-Qt checks
- the packaging extra includes PyInstaller for local executable builds

The extras declare security minimums for their existing dependencies. Refresh an
existing environment with the relevant editable install before verification or
packaging; `-SkipInstall` does not apply those minimums. See
[Security](SECURITY.md#dependency-advisories-and-compatibility-exceptions) for the
remaining Pillow/MoviePy and setuptools/PsychoPy constraints. Do not override
upstream requirements or treat a scanner package match as proof of a reachable
Studio attack path.

If Windows PowerShell blocks repository scripts because execution is restricted,
launch the specific repository script with a process-only policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Scope repo -Tier precommit
```

This does not change the user or machine execution policy. Repository test helpers
that load `.ps1` files use the same process-only setting.

## Launching The App

Run the authoring GUI with:

```powershell
.\.venv3.10\Scripts\python -m fpvs_studio.app
```

or the installed script:

```powershell
fpvs-studio
```

Build the local Windows executable with:

```powershell
.\scripts\build_exe.ps1
```

See `docs/PACKAGING.md` for the full developer packaging workflow.

## Runtime Honesty

The supported launch path is the fullscreen PsychoPy session runtime.

That means:

- the GUI exposes `Launch Experiment` through the normal session runtime
- launch settings use explicit presentation, trigger, refresh-verification, and
  timing-QC options; there is no runtime production/test Boolean gate
- fullscreen playback is the current default and is not user-configurable in the GUI
- Settings > Recording exposes project BioSemi/TriggerBox serial ports; other serial
  parameters remain backend fields

Source-tree runs on Windows and Linux expose an app-level `Experiment Test Mode`. It
uses the same fullscreen compiled session and timing QC while explicitly disabling
serial output, the Sophia/BioSemi gate, connected-display refresh verification, and
participant collection. Packaged builds do not expose or honor this development mode.

## Test Performance

The verification driver reports the 20 slowest test phases by default. Use
`-Durations 0` to remove the count limit or choose another nonnegative count.
Pytest hides phases shorter than 5 ms in its normal concise output.

Non-Qt checks can run in separate worker processes:

```powershell
./scripts/verify.ps1 -Scope repo -Tier precommit -Workers 4 -Durations 20
```

Install the current `dev` extra first. Parallel execution loads `pytest-xdist`
explicitly, keeps each test file in one worker, and retains a separate temporary
profile for every process. Start with two to four workers; more workers can increase
Windows filesystem contention and memory use. Audits, lint and type checks still run
in order. The default is one worker, which is also useful when diagnosing failures.

The Qt-enabled `full` tier requires one worker. Its existing visible-environment
approval and opt-in requirements still apply.

The remaining sequential history-test bottleneck and its measured limits are tracked
in [TD-004](exec-plans/tech-debt-tracker.md#td-004-sequential-uploaded-history-stress-test).

## GUI Test Environment

Qt and PsychoPy-adjacent tests keep writes inside the workspace. Shared pytest
configuration redirects local test environment paths into `build/test_env` and creates
isolated per-run temporary roots.

Registered Qt modules are excluded before import during ordinary local verification.
Use the safe GUI route for non-Qt checks:

```powershell
./scripts/verify.ps1 -Scope gui -Tier focused
```

Do not set `QT_QPA_PLATFORM=offscreen`. Registered Qt execution is available through
the optional `full` tier with `FPVS_ALLOW_QT_TESTS=1`, but run it only after explicit
user approval in a safe visible GUI environment. GitHub does not run repository tests.
The repo-wide `full` tier also requires the `dev` and `engine` extras shown in the local
setup commands above.

## Manual Verification

For local GUI work:

1. Run the focused `gui` scope.
2. Launch `.\.venv3.10\Scripts\python -m fpvs_studio.app` visibly.
3. Exercise only the changed surface and its important success, empty, busy, and error
   states at the documented minimum/default size.
4. Record the manual path and whether the optional registered pytest-qt suite was not
   run or ran in an approved visible environment.

Do not enter a real PsychoPy participant session, hardware workflow, or destructive
dialog unless the task explicitly requires and authorizes it.
