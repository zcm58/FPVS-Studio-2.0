# FPVS Studio

FPVS Studio is a Python 3.10 desktop application for authoring fast periodic
visual stimulation experiments with a PySide6 GUI and a PsychoPy-backed runtime
hidden behind the engine boundary.

Phase 5 introduces the first usable authoring GUI. Users can now create or open
projects, edit conditions and session settings, import and materialize assets,
save and reopen `project.json`, preflight the compiled session, and launch the
currently supported test-mode runtime path.

## Architecture

The repository keeps editable authoring state, compiled plans, preprocessing,
runtime, and engine concerns separate:

- `src/fpvs_studio/core/models.py`
  - editable project state stored in `project.json`
- `src/fpvs_studio/core/run_spec.py`
  - one compiled execution contract for one condition run
- `src/fpvs_studio/core/session_plan.py`
  - one compiled ordered multi-condition session plan
- `src/fpvs_studio/core/execution.py`
  - engine-neutral execution/export contracts
- `src/fpvs_studio/preprocessing/`
  - source inspection, manifests, and derived-asset materialization
- `src/fpvs_studio/runtime/`
  - compile preflight, launch settings, session flow, and export writers
- `src/fpvs_studio/engines/`
  - swappable presentation engines; only this package may import PsychoPy
- `src/fpvs_studio/gui/`
  - the PySide6 authoring application

The compile and launch flow is:

```text
project.json -> ProjectFile -> compile_run_spec(...) -> RunSpec
project.json + session settings -> compile_session_plan(...) -> SessionPlan
GUI -> runtime launcher/preflight -> runtime session flow -> engine
engine run/session results -> runtime exporters -> runs/...
```

`RunSpec` remains single-condition. `SessionPlan` remains the ordered
multi-condition contract above it. The GUI reuses backend services and does not
duplicate compiler, preprocessing, or runtime logic.

## Supported Environment

FPVS Studio currently supports Python `3.10` only.

PowerShell setup:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\python -m pip install -e '.[dev]'
```

Install the optional PsychoPy runtime extra when you want to launch sessions:

```powershell
.\.venv\Scripts\python -m pip install -e '.[dev,engine]'
```

Notes:

- PySide6 is a required application dependency in the default install.
- PsychoPy stays optional at install time and remains isolated to
  `src/fpvs_studio/engines/`.
- The current honest launch path is still `test_mode=True`, but launched
  PsychoPy playback now opens fullscreen on the selected display.
- Non-test validation and lab-grade trigger validation remain deferred.

See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for environment details and
[docs/GUI_WORKFLOW.md](docs/GUI_WORKFLOW.md) for the GUI authoring workflow.

## Launching The GUI

Developer entry points:

```powershell
.\.venv\Scripts\python -m fpvs_studio.app
```

or, after install:

```powershell
fpvs-studio
```

The welcome window supports:

- Create New Project
- Open Existing Project

The main authoring window provides pages for:

- Project
- Conditions
- Fixation & Session
- Assets / Preprocessing
- Run / Runtime

## Current GUI Workflow

Phase 5 currently supports:

- creating a new project scaffold in a chosen parent folder
- opening an existing project directory through the GUI; the backend document
  layer also accepts a direct `project.json` path
- editing project name, description, and display background color
- adding, removing, reordering, and editing conditions
- assigning base and oddball source folders per condition
- configuring duty cycle, instructions, trigger code, and stimulus variant
- editing session settings, stored session seed, transition mode, and fixation
  settings
- configuring an optional fixation accuracy task (Space response within 1.0 s
  after each fixation color change) with end-of-condition feedback
- configuring fixed or randomized fixation target counts per compiled condition
  run, including deterministic no-immediate-repeat behavior across consecutive
  runs
- configuring serial port and baud rate in the runtime settings page
- importing source folders, refreshing inspection, and materializing supported
  variants
- validating, compiling, preflighting, and launching the supported test-mode
  runtime path
- saving and reopening projects with state preserved

Runtime honesty matters here: the GUI labels the launch action as
`Launch Test Session` because the supported path still uses the test-mode
runtime seam, even though launched PsychoPy playback now presents fullscreen
and inserts a manual continue screen between non-final blocks. The fixation
accuracy task remains an engagement layer and does not alter the FPVS
base/oddball schedule.

## Tests

Use the repo-local scripts when you want the smallest useful gate for a task:

| Task | Command |
| --- | --- |
| Full quality gate | `.\scripts\check_quality.ps1` |
| GUI workflows | `.\scripts\check_gui.ps1` |
| Runtime/session behavior | `.\scripts\check_runtime.ps1` |
| Compiler/session contracts | `.\scripts\check_compiler.ps1` |
| Preprocessing assets/inspection | `.\scripts\check_preprocessing.ps1` |
| Remove generated output and caches | `.\scripts\clean_workspace.ps1` |

Run the non-GUI/backend-focused checks:

```powershell
.\.venv\Scripts\python -m pytest -q
```

When iterating on GUI tests, run one node at a time and keep the run hermetic:

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

The GUI tests are written to stay headless and should not open real modal
dialogs or launch the real PsychoPy runtime.

## Deferred Items

The following remain intentionally deferred after Phase 5:

- non-test launch validation
- lab-validated serial trigger hardware behavior
- alternate non-PsychoPy presentation engines
- broader theming/polish beyond the first usable authoring GUI
