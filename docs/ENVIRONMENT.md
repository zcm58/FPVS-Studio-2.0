# Environment Guide

## Supported Runtime

FPVS Studio supports Python `3.10` only.

This is enforced in:

- `pyproject.toml` via `requires-python = ">=3.10,<3.11"`
- Ruff via `target-version = "py310"`
- mypy via `python_version = "3.10"`

## Recommended Local Setup

### Windows source setup

In the full checkout on x64 Windows, close PyCharm and double-click **Setup Windows.cmd**.
Setup reuses a compatible `.venv3.10` or `.venv`. If neither is usable and `.venv3.10`
is available, it creates `.venv3.10` with 64-bit Python 3.10. It uses an installed 3.10
interpreter when found by the Python launcher, or downloads one into `.python310`
using a pinned, checksum-verified uv release. An incompatible `.venv` is preserved.
If `.venv3.10` is incompatible or incomplete, rename it and rerun setup.

`requirements.txt` installs packages into the selected Python 3.10 environment.
It includes the Studio app, PsychoPy and development tools. Setup runs `pip check`
and leaves PowerShell open with that environment active. Run `fpvs-studio` there
to open Studio.

For PyCharm, open the checkout and run **FPVS Studio (Windows)**. Setup configures
the project interpreter and points this run configuration at
`src/fpvs_studio/app/main.py`. When multiple standard profiles are available, setup
uses the newest installed one it detects. Set `FPVS_PYCHARM_CONFIG` to an existing
settings folder to select a different or custom profile. Changed IDE files are backed
up in `.idea/fpvs-setup-backups/`. If PyCharm was open during setup or is installed
later, close it and rerun setup to bind the interpreter.

`Setup Windows.cmd` calls `scripts/setup_windows.ps1` to install dependencies and
activate the environment. `scripts/windows_pycharm.py` prepares the IDE files.

### Mac source setup

For experimental macOS source setup, double-click `Setup Mac.command`, then
`Run Mac.command` in the complete checkout. The existing shell adapter creates or
reuses a native Python 3.10 environment, installs `requirements-macos.txt` and checks
consistency/imports. If Python is missing, a pinned, checksum-verified uv binary
installs it under `.fpvs-macos/`; system Python and shell profiles are not modified.
`FPVS_PYTHON` can select an existing native interpreter. Intel setup handles Rust
1.83+/OpenSSL 3 through Homebrew and requests Apple's build tools when absent. See
[Mac installation prerequisites](MACOS_SUPPORT.md#install-run-and-update-from-source)
for required Apple/admin prompts, the CI matrix, test-only scope, local calibration and
portable Windows handoff. No Developer ID is needed for source.

`pyproject.toml` owns dependency versions. `requirements.txt` and
`requirements-macos.txt` both select `dev,engine`, including PsychoPy, without copying
versions. The optional `Open in PyCharm Mac.command` registers/reuses one SDK in the
selected IDE's standard Mac profile while PyCharm is closed, binds this project and
prepares its run configuration. Changed XML is backed up under `.fpvs-macos/`; other
SDK entries and project components are preserved. The same actions are available through
`bash scripts/macos-source.sh {setup|run|pycharm|verify}`.

### Manual Windows setup

With 64-bit Python 3.10 already installed, run these commands in PowerShell:

```powershell
py -3.10-64 -m venv .venv3.10
.\.venv3.10\Scripts\python -m pip install -U 'pip>=26.2'
.\.venv3.10\Scripts\python -m pip install -r requirements.txt
```

For development that does not run experiments, install only the dev extra:

```powershell
.\.venv3.10\Scripts\python -m pip install -e '.[dev]'
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
- PsychoPy is included by both requirements files; it remains optional for direct
  installs without the engine extra and is confined to `src/fpvs_studio/engines/`
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

Windows/Linux expose app-level `Experiment Test Mode` using the same fullscreen
compiled session and timing QC with explicit null output and no participant collection.
Their local-test policy skips connected-display verification. macOS source exposes
Test/Pilot only, retains native plus PsychoPy refresh verification, and uses a child
process's main thread with nonexclusive desktop-sized presentation and explicit
foreground-window keyboard input. Its calibration dialog keeps physical values local;
an explicitly accepted resolution mismatch saves the project's target pixels before
launch. Refresh and EEG settings are preserved. macOS first-run authoring requires no EEG choice; acquisition
launches are blocked. Source updates use Git and the setup helper, not a Windows installer.

## Test Performance

Windows remains the primary platform. Repo `precommit` and `full` run mypy over
all source with `--platform win32`, followed by a Darwin check of the Mac adapter
owners. The `macos` focused route also runs that adapter type check. Imported
Windows-only owners stay covered by the primary pass.

Tests use `tests/platform_adapters.py` to replace the owning module's view of
`sys`, preserving the real process platform. Windows acquisition tests retain their
hardware/display assertions through existing fakes; Mac tests explicitly exercise
source-only guards, Retina backing pixels and child-process boundaries. Synthetic
helper IPC tests resolve linked POSIX interpreters while retaining the parent's
import paths; production executable validation stays unchanged.

Verification chooses `.venv3.10`, then `.venv`, using the current host's executable
layout and preserving POSIX venv symlinks. Full repository audits require PowerShell;
install `pwsh` on Mac before running the repo route. Mac source setup reuses an
existing `.venv` when `.venv3.10` is absent.

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
Pytest nests fixture paths under the system temporary directory.

The Qt-enabled `full` tier requires one worker. Its existing visible-environment
approval and opt-in requirements still apply.

The remaining sequential history-test bottleneck and its measured limits are tracked
in [TD-004](exec-plans/tech-debt-tracker.md#td-004-sequential-uploaded-history-stress-test).

## GUI Test Environment

The shared pytest configuration redirects temporary files, user profile paths, and
Qt settings into private `fpvs-test-*` directories under the system temp location
(`%TEMP%` on Windows). Each pytest process removes its directory at teardown.

Registered Qt modules are excluded before import during ordinary local verification.
Use the safe GUI route for non-Qt checks:

```powershell
./scripts/verify.ps1 -Scope gui -Tier focused
```

Do not set `QT_QPA_PLATFORM=offscreen`. Registered Qt execution is available through
the optional `full` tier with `FPVS_ALLOW_QT_TESTS=1`, but run it only after explicit
user approval in a safe visible GUI environment. GitHub's macOS source workflow runs
clean installs, safe non-Qt checks, opt-in native adapters and cross-OS bundle handoffs.
It uploads exact host/dependency/test evidence; it never qualifies a physical display.
The repo-wide `full` tier also requires the `dev` and `engine` extras shown in the local
setup commands above.

Popup widget tests use `tests/gui/helpers.py` to prevent Cocoa alert substitution
when checking Windows widget behavior on Mac; separate coverage exercises native
Cocoa reporting. Windows keeps title/minimum-width assertions, while Mac checks
content sizing and full text/button bounds. Wait for exposure and asynchronous
closure when testing Return/Escape; drain deferred fixture deletion between cases.

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
