# Packaging FPVS Studio

This guide is for developer builds of the Windows executable. End users should only
interact with the built `FPVS Studio.exe`, not the source tree or Python environment.

## Build Environment

FPVS Studio packaging uses the repo-local Python 3.10 environment and PyInstaller.
Create or refresh the environment once:

```powershell
py -3.10 -m venv .venv3.10
.\.venv3.10\Scripts\python -m pip install -U pip
.\.venv3.10\Scripts\python -m pip install -e ".[dev,engine,packaging]"
```

The `engine` extra is included because lab builds should contain PsychoPy and runtime
dependencies. The `packaging` extra installs PyInstaller.

## Version The App

Before building a release candidate, update the package metadata version:

- `pyproject.toml`: `[project] version = "X.Y.Z"`

That is the only developer entry point for changing the app version.
`src/fpvs_studio/__init__.py` derives `__version__` from installed package metadata,
and the PyInstaller spec includes that metadata in the bundled app.
The package distribution name is `fpvs-studio`; the GUI and executable still use the
display name `FPVS Studio`.

Use simple semantic versioning:

- patch version for bug fixes and documentation-only release packaging fixes
- minor version for new user-facing features
- major version only for breaking project/runtime compatibility changes

The package metadata test fails if package metadata and the importable app version drift:

```powershell
.\.venv3.10\Scripts\python -m pip install -e ".[dev,engine,packaging]"
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_package_metadata.py
```

Refreshing the editable install is required after a version change because installed
package metadata can otherwise still report the previous version. A normal
`.\scripts\build_exe.ps1` run also refreshes this metadata; `-SkipInstall` should only
be used after dependencies and package metadata are already current.

For future GitHub Releases, tag the matching commit as `vX.Y.Z` and upload the build
artifact from the same versioned source.

## Build The App

Run the repo script:

```powershell
.\scripts\build_exe.ps1
```

The script verifies Python 3.10, installs `.[engine,packaging]` unless
`-SkipInstall` is passed, cleans only packaging output folders, and runs PyInstaller.

Expected output:

```text
dist\FPVS Studio\FPVS Studio.exe
```

When iterating after dependencies are already installed, use:

```powershell
.\scripts\build_exe.ps1 -SkipInstall
```

## Smoke Test

Open the packaged app:

```powershell
& "dist\FPVS Studio\FPVS Studio.exe"
```

Before sharing a build, manually confirm:

- the app launches on a Windows machine without system Python installed
- create/open project works
- `Tools > Image Resizer` opens and can optimize a small image folder
- custom condition templates remain under the configured FPVS Studio Root Folder
- the PsychoPy test launch path still opens fullscreen playback

The package output is disposable. User settings are stored through Qt settings and user
projects/templates live under the configured FPVS Studio Root Folder, not under `dist\`.

If PyInstaller reports multiple Qt bindings, keep `PySide6` and remove or exclude
unrelated Qt bindings such as `PyQt5` or `PyQt6` from the build environment. The checked
in spec already excludes those bindings for the local build.

## Sharing A Lab Build

For internal testing, zip the entire folder:

```powershell
Compress-Archive -Path "dist\FPVS Studio\*" -DestinationPath "dist\FPVS-Studio.zip" -Force
```

Later release work can wrap `dist\FPVS Studio\` in an installer EXE and upload that
installer to GitHub Releases.

## Future App Icon

The current build uses the default window/icon behavior. When adding a real app icon:

- add the source icon as `packaging/assets/fpvs-studio.ico`
- wire that `.ico` into `packaging/pyinstaller/fpvs_studio.spec`
- update GUI startup to use the same icon for application and window icons
- rebuild with `.\scripts\build_exe.ps1` and confirm the icon appears on the EXE,
  taskbar, and app windows
