# Inno Setup Installer Preparation

Status: Completed

## Summary

Prepared FPVS Studio for a single installer EXE release path by wrapping the existing
PyInstaller `onedir` output with Inno Setup. The developer workflow stays simple: build
the app bundle first, then build the installer from that bundle. End users download one
installer EXE from GitHub Releases, install FPVS Studio, and launch it from normal
Windows shortcuts without installing Python or opening the source tree.

The current PyInstaller build remains the runtime packaging boundary:

```text
.\scripts\build_exe.ps1
dist\FPVS Studio\FPVS Studio.exe
dist\FPVS Studio\_internal\...
```

The installer layer consumes that whole folder and produces a versioned setup EXE.

## User Workflow

Developer release flow:

1. Update `[project] version` in `pyproject.toml`.
2. Run `.\scripts\build_exe.ps1`.
3. Smoke test `dist\FPVS Studio\FPVS Studio.exe`.
4. Run `.\scripts\build_installer.ps1`.
5. Smoke test install, launch, update install, and uninstall behavior.
6. Upload the installer EXE to a matching GitHub Release.

End-user flow:

1. Download `FPVS-Studio-Setup-X.Y.Z.exe`.
2. Run the installer.
3. Launch FPVS Studio from the Start Menu, Desktop shortcut, or installed EXE.
4. Install a newer release later without losing QSettings, configured FPVS Studio Root
   Folder, projects, run history, or custom condition templates.

## Implemented Files

- `packaging/inno/fpvs_studio.iss`
  - checked-in Inno Setup script
  - reads or receives the app version from `pyproject.toml` through the build script
  - installs the complete `dist\FPVS Studio\` folder
  - creates Start Menu and optional Desktop shortcuts
  - defines uninstall metadata and app publisher/name constants
- `scripts/build_installer.ps1`
  - developer entry point after `build_exe.ps1`
  - verifies `dist\FPVS Studio\FPVS Studio.exe` exists
  - verifies Inno Setup compiler availability
  - derives the installer version from `pyproject.toml`
  - writes installer output under ignored `dist\installer\`
  - prints the exact setup EXE path
- `docs/PACKAGING.md`
  - documents the two-step release build: `build_exe.ps1`, then `build_installer.ps1`
  - documents smoke tests for fresh install, update install, and uninstall
- `packaging/AGENTS.md`
  - documents Inno-specific guardrails now that installer files exist

## Installer Contract

- Install the whole PyInstaller onedir bundle, not only `FPVS Studio.exe`.
- Do not install into, delete, migrate, or rewrite user project folders.
- Do not delete or rewrite Qt `QSettings`.
- Do not delete or rewrite `.fpvs-studio/templates/`, `runs/`, or `logs/`.
- Treat installed app files as replaceable release artifacts.
- Treat user projects, settings, templates, and run outputs as external user data.
- Preserve the Python distribution name `fpvs-studio` and the user-facing display name
  `FPVS Studio`.

## Update Behavior

The installer supports installing a newer version over an older version by replacing
installed application files while leaving external user data untouched.

GitHub Releases are the release distribution channel. FPVS Studio now also includes an
in-app update checker that compares the installed version against GitHub Releases,
downloads the matching setup EXE after user approval, launches the Inno installer with
`/RELAUNCH=1`, and exits so the installer can update and relaunch the app.

## Icon Direction

The shared app icon is wired through:

- `packaging/assets/fpvs-studio.ico`
- `packaging/pyinstaller/fpvs_studio.spec`
- `packaging/inno/fpvs_studio.iss`

The `.ico` should continue to include standard Windows sizes: `16x16`, `24x24`,
`32x32`, `48x48`, `64x64`, `128x128`, and `256x256`, using 32-bit color with alpha
transparency.

## Boundaries

- No compiler, runtime, engine, preprocessing, or GUI workflow changes were required for
  installer wrapping.
- No installer logic depends on PsychoPy internals.
- No vendored Inno Setup binaries or third-party installers are committed.
- No GitHub Actions automation is included.
- No true PyInstaller `--onefile` migration is required; the installer wraps the safer
  current `onedir` bundle.

## Verification

Developer-script checks:

```powershell
.\scripts\build_exe.ps1
.\scripts\build_installer.ps1
```

Documentation and harness checks:

```powershell
.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_package_metadata.py tests\unit\test_harness_docs.py
.\scripts\check_docs_hygiene.ps1
```

Manual installer smoke tests:

- install on a Windows machine without system Python
- launch FPVS Studio from the installed shortcut
- create/open a project
- open `Tools > Image Resizer`
- confirm custom condition templates remain under the configured FPVS Studio Root Folder
- install a newer build over the current install and confirm settings/templates/projects
  remain intact
- uninstall and confirm project folders are not removed

## Acceptance Criteria

- A developer can produce a setup EXE without remembering raw Inno Setup compiler
  arguments.
- The setup EXE version matches `[project] version` in `pyproject.toml`.
- Installer output is ignored under `dist\installer\`.
- The installed app launches without system Python.
- Updating the installed app does not overwrite user settings, projects, templates, run
  history, or logs.
- Packaging docs describe the EXE bundle build, installer build, smoke test, and GitHub
  Release upload flow.

## Assumptions

- Inno Setup is installed locally on the developer machine, or the build script can emit
  a clear install-path error.
- The current PyInstaller onedir output is the stable input to installer packaging.
- GitHub Releases remain a manual upload step.
- End users interact with the installed app and shortcuts, not the source repository.
