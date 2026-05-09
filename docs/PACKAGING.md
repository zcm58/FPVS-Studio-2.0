# Packaging FPVS Studio

This guide is for developer builds of the Windows executable bundle and installer. End
users should only interact with the installed `FPVS Studio.exe`, not the source tree or
Python environment.

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

For the current beta package, use the PEP 440-compatible package version `0.9.1b2`.
The GitHub Release title can still use the friendlier label `v0.9.1-beta`.

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

For future GitHub Releases, tag the matching commit with a PEP 440-compatible version
such as `v0.9.0b2` or `v1.0.0` and upload the build artifact from the same versioned
source. The in-app updater uses the release tag for version comparison; the release
title can use friendlier wording such as `v0.9.0-beta`.

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

The PsychoPy runtime window backend is loaded dynamically at launch time. The checked-in
PyInstaller spec explicitly includes `psychopy.visual.backends.pygletbackend` and
`psychopy.visual.backends.glfwbackend`; keep those hidden imports in place or installed
apps can build successfully but fail when `Launch Experiment` tries to open the
presentation window.

## Sharing A Lab Build

For internal testing, zip the entire folder:

```powershell
Compress-Archive -Path "dist\FPVS Studio\*" -DestinationPath "dist\FPVS-Studio.zip" -Force
```

## Build The Installer

Install Inno Setup 6 locally before building an installer. The build script looks for
`ISCC.exe` on `PATH`, in the default Inno Setup install folders, through `ISCC_EXE`, or
through the explicit `-InnoCompiler` argument.

Build the PyInstaller bundle first:

```powershell
.\scripts\build_exe.ps1
```

Then build the setup EXE:

```powershell
.\scripts\build_installer.ps1
```

Expected output for the current beta package:

```text
dist\installer\FPVS-Studio-Setup-0.9.1b2.exe
```

If Inno Setup is installed somewhere custom:

```powershell
.\scripts\build_installer.ps1 -InnoCompiler "C:\Path\To\ISCC.exe"
```

The installer wraps the whole `dist\FPVS Studio\` folder. It installs per-user under
`%LOCALAPPDATA%\Programs\FPVS Studio`, creates Start Menu shortcuts, and offers an
optional Desktop shortcut. User settings, projects, templates, run history, and logs
remain outside the install folder.

Upload the setup EXE to the matching GitHub Release after smoke testing install,
launch, update install, and uninstall behavior.

## In-App Update Flow

Installed users can use `File > Check for Updates`. The app checks GitHub Releases,
compares the installed `fpvs_studio.__version__` with the latest eligible release tag,
and downloads the matching `FPVS-Studio-Setup-*.exe` asset only after the user chooses
`Download Update`.

Release requirements for the updater:

- release tags must be parseable package versions, such as `v0.9.0b2` or `v1.0.0`
- each release should include exactly one Windows installer asset named
  `FPVS-Studio-Setup-<version>.exe`
- beta/prerelease users can see prerelease updates; stable users ignore prereleases by
  default
- draft releases are ignored

The updater stores downloaded installers in a user-writable update cache, never in the
install folder or project folders. On `Install and Restart`, FPVS Studio asks for final
confirmation, launches the downloaded Inno installer with `/RELAUNCH=1`, and exits. The
installer remains responsible for replacing app files and relaunching FPVS Studio. Normal
first-time installer runs still show the standard launch checkbox on the final page.

## App Icon And Branding

The build uses a shared FPVS Studio icon for application windows, the PyInstaller EXE,
and the Inno Setup installer. When replacing the icon later:

- add the source icon as `packaging/assets/fpvs-studio.ico`
- include the standard Windows icon sizes in the `.ico`: `16x16`, `24x24`, `32x32`,
  `48x48`, `64x64`, `128x128`, and `256x256`; use 32-bit color with alpha transparency
- wire that `.ico` into `packaging/pyinstaller/fpvs_studio.spec`
- wire that `.ico` into `packaging/inno/fpvs_studio.iss`
- update GUI startup to use the same icon for application and window icons
- rebuild with `.\scripts\build_exe.ps1` and confirm the icon appears on the EXE,
  taskbar, and app windows

Current branding assets:

- `packaging/assets/fpvs-studio-icon-1024.png`: high-resolution source PNG
- `packaging/assets/fpvs-studio.ico`: release icon for PyInstaller and Inno Setup
- `docs/assets/fpvs-studio-icon.png`: README/GitHub icon image
- `docs/assets/fpvs-studio-readme-header.png`: README header image
- `docs/assets/fpvs-studio-social-preview.png`: GitHub social preview image
