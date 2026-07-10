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
.\.venv3.10\Scripts\python -m pip install -U pip
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
  verification
- the packaging extra includes PyInstaller for local executable builds

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

The currently supported launch path is still the fullscreen PsychoPy test-mode runtime.

That means:

- the GUI exposes `Launch Experiment` on the beta test-mode runtime path
- runtime launch still requires `test_mode=True`
- fullscreen playback is the current default and is not user-configurable in the GUI
- serial trigger settings remain backend fields, but they are not exposed in the
  current GUI until the hardware workflow is ready

## GUI Test Environment

Qt and PsychoPy-adjacent tests keep writes inside the workspace. Shared pytest
configuration redirects local test environment paths into `build/test_env` and creates
isolated per-run temporary roots.

Registered Qt modules are excluded before import during ordinary local verification.
Use the safe GUI route for non-Qt checks:

```powershell
./scripts/verify.ps1 -Scope gui -Tier focused
```

Do not set `QT_QPA_PLATFORM=offscreen` for local work. CI owns offscreen configuration,
plugin opt-in, and registered Qt execution through the `full-ci` tier. Run Qt locally
only after explicit user approval in a safe visible GUI environment.

## Manual Verification

For local GUI work:

1. Run the focused `gui` scope.
2. Launch `.\.venv3.10\Scripts\python -m fpvs_studio.app` visibly.
3. Exercise only the changed surface and its important success, empty, busy, and error
   states at the documented minimum/default size.
4. Record the manual path and leave registered pytest-qt execution to CI.

Do not enter a real PsychoPy participant session, hardware workflow, or destructive
dialog unless the task explicitly requires and authorizes it.
