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
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e '.[dev]'
```

Install the optional PsychoPy engine extra when you want to exercise the launch
path:

```powershell
.\.venv\Scripts\python -m pip install -e '.[dev,engine]'
```

Notes:

- the default install includes PySide6 because the GUI is now the primary app
  surface
- PsychoPy remains optional at install time and is still confined to
  `src/fpvs_studio/engines/`
- the dev extra includes `pytest`, `pytest-qt`, and `pytest-timeout` for GUI
  verification

## Launching The App

Run the authoring GUI with:

```powershell
.\.venv\Scripts\python -m fpvs_studio.app
```

or the installed script:

```powershell
fpvs-studio
```

## Runtime Honesty

The currently supported launch path is still the fullscreen PsychoPy test-mode runtime.

That means:

- the GUI exposes `Launch Test Session`
- runtime launch still requires `test_mode=True`
- fullscreen playback is the current default and is not user-configurable in the GUI
- serial trigger settings remain backend fields, but they are not exposed in the
  current GUI until the hardware workflow is ready

## GUI Test Environment

Qt and PsychoPy-adjacent tests should keep writes inside the workspace. The
shared pytest configuration now redirects these variables into `build/test_env`:

- `TMP`
- `TEMP`
- `TMPDIR`
- `APPDATA`
- `LOCALAPPDATA`
- `HOME`
- `USERPROFILE`

GUI tests should also run with:

- `QT_QPA_PLATFORM=offscreen`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
- explicit `pytestqt.plugin`
- explicit `pytest_timeout`
- `--basetemp` inside `build/`
- single-node invocation while iterating

Example:

```powershell
$env:PYTHONPATH = "src"
$env:TMP = "$PWD\build\tmp"
$env:TEMP = "$PWD\build\tmp"
$env:TMPDIR = "$PWD\build\tmp"
$env:APPDATA = "$PWD\build\appdata"
$env:LOCALAPPDATA = "$PWD\build\localappdata"
$env:USERPROFILE = "$PWD\build\userprofile"
$env:HOME = "$PWD\build\home"
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"

New-Item -ItemType Directory -Force build\tmp, build\appdata, build\localappdata, build\userprofile, build\home | Out-Null

.\.venv\Scripts\python -m pytest `
  --disable-plugin-autoload `
  -p pytestqt.plugin `
  -p pytest_timeout `
  --basetemp=build\pytest_tmp `
  --maxfail=1 `
  --timeout=45 `
  -vv -s `
  tests\gui\test_welcome_settings_flow.py::test_welcome_window_smoke
```

## Manual Verification

If you are iterating on the GUI and do not want the full GUI suite to gate
progress, it is reasonable to:

1. run backend/unit tests
2. launch `python -m fpvs_studio.app`
3. manually verify create/open, save/reopen, asset import/materialization,
   preflight, and test-mode launch wiring

That is preferable to letting a GUI run hang on a real modal dialog or runtime
launch path during development.
