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
`src/fpvs_studio/__init__.py` reads `__version__` from source-tree `pyproject.toml`
when present and falls back to installed package metadata for bundled installs.
The PyInstaller spec includes package metadata in the bundled app.
The package distribution name is `fpvs-studio`; the GUI and executable still use the
display name `FPVS Studio`.

For the current release package, use the PEP 440-compatible package version `1.4.0`.
The GitHub Release title can use a friendlier beta label, but the release tag and
installer filename must use the exact package version.

Use simple semantic versioning:

- patch version for bug fixes and documentation-only release packaging fixes
- minor version for new user-facing features
- major version only for breaking project/runtime compatibility changes

The package metadata test fails if the importable app version and `pyproject.toml` drift:

```powershell
.\.venv3.10\Scripts\python -m pip install -e ".[dev,engine,packaging]"
./scripts/verify.ps1 -Scope packaging -Tier focused
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

Before sharing a build, manually confirm on a Windows x64-compatible machine:

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

The spec also removes top-level `icuuc.dll` and `icudt*.dll` files discovered through
the build host's `PATH`. On supported Windows versions, Qt uses the operating system's
unversioned ICU shim. Bundling an unrelated application's version-suffixed ICU runtime
can prevent `PySide6.QtWidgets` from loading even though PyInstaller completes.

PsychoPy loads visual primitives and the runtime window backend dynamically at launch
time. The checked-in PyInstaller spec collects `psychopy.visual` submodules and
explicitly includes `psychopy.visual.backends.pygletbackend`,
`psychopy.visual.backends.glfwbackend`, and `psychopy.visual.line`; keep those hidden
imports in place or installed apps can build successfully but fail when
`Launch Experiment` tries to open the presentation window.

Modular-task Open Sans rendering is self-contained. Keep
`src/fpvs_studio/assets/fonts/OpenSans-Regular.ttf` and its
`OpenSans-OFL.txt` SIL Open Font License together as release-facing package data. The
PyInstaller spec's `collect_data_files("fpvs_studio")` path carries both files into the
bundle, so neither source-tree nor installed playback may depend on a system Open Sans
installation. Packaging verification must continue to check that the font can be
loaded and that its OFL license is present.

## Sharing A Lab Build

For internal testing, zip the entire folder:

```powershell
Compress-Archive -Path "dist\FPVS Studio\*" -DestinationPath "dist\FPVS-Studio.zip" -Force
```

## Build The Installer

Install Inno Setup 6.5 or newer locally before building an installer. Clean-upgrade
verification uses its stream-based SHA-256 support; older compilers are rejected.
The build script looks for
`ISCC.exe` on `PATH`, in the default Inno Setup install folders, through `ISCC_EXE`, or
through the explicit `-InnoCompiler` argument or its Windows uninstall registration.

For the normal release build, run the one-step wrapper:

```powershell
.\scripts\build_release.ps1
```

Or double-click:

```text
scripts\build_release.cmd
```

The wrapper builds the PyInstaller bundle first, then builds the setup EXE from that
fresh bundle. The default release build refreshes editable package dependencies with `pip` before
PyInstaller runs. In Codex or any sandboxed runner, start `.\scripts\build_release.ps1`
with elevated network permissions so dependency resolution can fetch build backend
packages such as `hatchling` instead of failing and needing a second run.

When iterating after dependencies are already installed, use:

```powershell
.\scripts\build_release.ps1 -SkipInstall
```

If Inno Setup is installed somewhere custom:

```powershell
.\scripts\build_release.ps1 -InnoCompiler "C:\Path\To\ISCC.exe"
```

The individual commands remain available when you need to run only one stage. Build the
PyInstaller bundle first:

```powershell
.\scripts\build_exe.ps1
```

Then build the setup EXE:

```powershell
.\scripts\build_installer.ps1
```

Expected output for the current package:

```text
dist\installer\FPVS-Studio-Setup-1.4.0.exe
```

The installer build validates that the PyInstaller bundle has an `_internal` folder and
exactly one bundled `fpvs_studio-*.dist-info` metadata directory, removes stale files
from `dist\installer\`, then runs the packaged-app smoke check unless `-SkipSmoke` is
passed. That check launches the bundled executable in a bounded diagnostic mode and
verifies that the bundled package metadata matches `pyproject.toml`, the update dialog
has the shared theme applied, `Remind Me Later` dismisses an update prompt,
update-dialog action buttons fit their labels, and PsychoPy/runtime dependency imports
needed by packaged launch are present.

To run that smoke check against an existing bundle:

```powershell
.\scripts\smoke_packaged_app.ps1
```

To run it against the installed app:

```powershell
.\scripts\smoke_packaged_app.ps1 -ExePath "$env:LOCALAPPDATA\Programs\FPVS Studio\FPVS Studio.exe"
```

If Inno Setup is installed somewhere custom:

```powershell
.\scripts\build_installer.ps1 -InnoCompiler "C:\Path\To\ISCC.exe"
```

For advanced local iteration only, after you have already run the packaged smoke check
against the exact bundle being wrapped, the installer smoke gate can be skipped:

```powershell
.\scripts\build_installer.ps1 -SkipSmoke
```

For an explicitly requested local beta that the user will test manually, build into
an isolated label so existing unlabelled artifacts remain untouched:

```powershell
.\scripts\build_exe.ps1 -BuildLabel beta-1.3.1b2
.\scripts\build_installer.ps1 -BuildLabel beta-1.3.1b2 -SkipSmoke
```

This produces `dist\beta-1.3.1b2\installer\FPVS-Studio-Setup-1.3.1b2.exe`, with
bundle/build metadata under the matching `dist\beta-1.3.1b2\` and
`build\beta-1.3.1b2\` directories. A build label must be a safe single directory
name, not a path. `build_release.ps1` also forwards `-BuildLabel`, but retains the
ordinary packaged smoke gate. Skipping the smoke for a manual-test candidate does
not constitute a successful packaged launch or authorize release publication. Record
that check as pending and do not launch the app, installer, or uninstaller for the user.

The installer wraps the whole `dist\FPVS Studio\` folder. It installs per-user under
`%LOCALAPPDATA%\Programs\FPVS Studio`, creates Start Menu shortcuts, and offers an
optional Desktop shortcut. User settings, projects, templates, run history, and logs
remain outside the install folder.

### Clean Upgrade Ownership

Before compiling setup, `scripts/build_installer_inventory.py` hashes the final bundle
and generates `current-owned-files.txt` and `legacy-owned-files.txt` under
`build/installer-inventory/`. The latter is validated from the checked-in
`packaging/inventory/published-legacy-inventory.json`. That inventory was extracted
from exact checksum-authenticated public installers through 1.3.0; it covers older
files carried forward by multiple upgrades, not just a fresh 1.3.0 installation.
See `packaging/inventory/README.md` for provenance and safe regeneration instructions.
No historical installers or extractor tools are downloaded on end-user machines.

The installed ownership record is `fpvs-owned-files-v1.txt`. Inno captures previous
ownership before replacing files and reconciles obsolete entries only after successful
installation. Deletion requires a validated install-relative path and a matching known
content hash. Unknown/modified files and project-data names remain untouched; symlinks,
junctions, rooted paths, traversal, and unsafe Windows aliases do not establish ownership.
Upgrade reconciliation removes files only and retains directories, including explicitly
shipped empty directories. Inno retains its ordinary logged-directory uninstall behavior.
The profile-root guard resolves `CSIDL_PROFILE` through Inno's
`GetShellFolderByCSIDL(..., False)` without creating directories; an empty or invalid
result stops preparation. Runtime `ExpandConstant` names are checked separately from
native compilation, which does not validate constant names inside Pascal strings.
Failed obsolete deletions remain recorded in
`fpvs-pending-owned-files-v1.txt` so later upgrades can retry them. A cleanup warning is
not evidence that the installation reached fresh-install parity.

Do not use a wildcard deletion of `{app}` or `_internal`, and do not set
`UninstallLogMode=overwrite`. The installer is self-contained: reconciliation does not
require installed Python, PowerShell, or a separate maintenance application.

Upload the setup EXE to the matching GitHub Release after smoke testing fresh install,
launch, update-over-old-version install, and uninstall behavior. The clean-PC or clean-VM
release check is:

- install on a Windows x64-compatible machine without system Python
- launch FPVS Studio from the Start Menu or Desktop shortcut
- run `.\scripts\smoke_packaged_app.ps1 -ExePath "$env:LOCALAPPDATA\Programs\FPVS Studio\FPVS Studio.exe"`
- create/open a project
- open `Tools > Image Resizer`
- run the PsychoPy test launch path
- install a newer setup EXE over the older installed app and confirm settings, projects,
  condition templates, `runs/`, and `logs/` remain intact

## In-App Update Flow

Installed users can use `File > Check for Updates`. FPVS Studio also runs one silent
startup check after the Welcome window appears. The app checks GitHub Releases, compares
the installed `fpvs_studio.__version__` with the latest eligible release tag, shows the
current and latest versions plus a short release-notes summary, and downloads the
matching `FPVS-Studio-Setup-*.exe` asset only after the user chooses `Download Update`.
Manual update-check failures show a clear try-again-later message. Startup checks stay
silent unless an update is available.

Release requirements for the updater:

- release tags must be parseable package versions, such as `v0.9.0b2` or `v1.0.0`
- each release should include exactly one Windows installer asset named
  `FPVS-Studio-Setup-<version>.exe`
- beta/prerelease users can see prerelease updates; stable users ignore prereleases by
  default
- draft releases are ignored
- the selected asset must expose valid `sha256:<64 hex digits>` digest metadata and a
  positive byte size; GitHub's [release asset API](https://docs.github.com/en/rest/releases/assets)
  supplies the digest for published assets
- installer URLs must belong to this repository's HTTPS GitHub release-download path,
  and names must match the selected version; the published `v0.9.9.10` / `0.9.10`
  filename mismatch is the sole explicit legacy alias

A newer release lacking trustworthy installer metadata remains visible as an available
release, with its release-page link, but in-app download/install is unavailable. Do not
silently accept size-only validation or report that the installed app is up to date.
SHA-256 checks are required before reuse and again immediately before launch; release
signing infrastructure is not introduced by this feature.

The updater stores downloaded installers in a user-writable update cache, never in the
install folder or project folders. On Windows the normal cache is
`%LOCALAPPDATA%\FPVS Studio\updates`. Startup housekeeping is independent of the
configured FPVS Studio Root Folder and of network update-check success. Under one
exclusive inter-process lock it removes recognized installers at or below the running
version, retains at most the highest verified newer installer, and removes abandoned
recognized partials. Small verification receipts allow offline cache validation; legacy
size-only cached files cannot be reused without trusted verification metadata.

The cache payload bound after successful housekeeping is one complete installer and
one actively locked unique staging file, excluding small lock/receipt metadata. Unknown
files and links are never cleanup targets. Startup cleanup errors are logged and do not
prevent launch; an explicit download refuses to add payloads if required pruning fails.
An active download holds the same lock through cleanup, transfer, checksum verification,
and promotion. Competing attempts report that the cache is busy. Canceled or interrupted
downloads are discarded; a retry starts from zero. Uninstall cleans only recognized
app-owned cache files under the same lock, and removes the cache directory only if empty.

On `Install and Restart`, FPVS Studio asks for final confirmation, saves the open project
through its existing GUI callback, verifies the downloaded file in a background worker,
launches the Inno installer with `/RELAUNCH=1`, and exits after that worker has finished. The
installer remains responsible for replacing app files and relaunching FPVS Studio. User
projects, app settings, condition templates, run history, and logs remain outside the
install folder during updates. Normal first-time installer runs still show the standard
launch checkbox on the final page.

Closing an update dialog through its button, Escape, or the window close control requests
cancellation and defers teardown until updater work finishes. Application quit similarly
cancels/finishes app-owned updater jobs without destroying running Qt threads or blocking
the GUI thread. Metadata checks, hashing, cache housekeeping, and download I/O all stay
off the GUI thread. Startup never downloads an installer or launches setup automatically.

### Updater And Upgrade Acceptance

Run the focused `updates`, `gui`, and `packaging` verification scopes, then repo
precommit. Ordinary local verification uses temporary files and mocked network/process
operations; it does not run an installer, uninstall an application, or execute Qt.
Registered Qt coverage requires a separately approved safe visible environment.

A safe native syntax check compiles the actual Inno script against a tiny,
non-executable synthetic bundle, without running the resulting setup:

```powershell
python scripts/check_installer_compile.py --inno-compiler "C:\Path\To\ISCC.exe"
```

The temporary fixture and compiled output are removed automatically. The explicit
[Windows lifecycle checklist](../packaging/inno/LIFECYCLE_TESTS.md) covers the
remaining real-install acceptance and the read-only installed-file parity checker.

Before release, use a disposable Windows VM or separate test account to verify:

- fresh install and visible updater layout in ready, busy, cancellation, error, and
  downloaded states; Close, Escape, the window close control, and app quit during work
- fresh 1.3.0 to the new version, plus an earlier published release to 1.3.0 to the new
  version; compare owned payload files/hashes against a fresh new-version installation
- a genuinely historical obsolete-file sentinel is removed, while an unrelated file
  and project/settings/templates/run/log sentinels survive
- same-size installer corruption is rejected, simultaneous processes cannot share a
  download, interrupted transfers leave no reusable partial, and post-update startup
  prunes the old installer without deleting a still-running setup executable
- a locked obsolete file, failed cleanup, retry on the next upgrade, malformed ownership
  metadata, path/junction escapes, and canceled/failed setup preserve safe recovery
- final uninstall removes owned application/cache payloads but not unrelated files or
  project/settings data

For this feature's initial implementation, no disposable environment was available.
On 2026-08-31 the user accepted the visible updater GUI and requested a local
`1.3.1b1` installer to run manually on their own machine. That approval permits
building and handing off the candidate, not agent-run installation or failure tests.
The user then reported that beta 1 stopped during preparation on the unsupported
`{userprofile}` constant, before application-file replacement. Beta `1.3.1b2` replaces
that lookup with the supported shell-folder API and includes regression coverage;
the replacement installer still requires the user's manual test.
Safe local tests and compiler checks are evidence only for the code they exercise;
real Windows install/upgrade/uninstall acceptance remains pending in the active plan.
Do not use the working installation for destructive failure/recovery tests or publish
a release as though the remaining lifecycle checks passed.

## App Icon And Branding

The build uses one generated FPVS Studio icon for application windows, the PyInstaller
EXE, and the Inno Setup installer. When replacing the icon later:

- update the canonical source PNG at `packaging/assets/fpvs-studio-icon-1024.png`
- run `.\scripts\sync_branding_assets.ps1`
- keep `packaging/pyinstaller/fpvs_studio.spec`, `packaging/inno/fpvs_studio.iss`,
  and GUI startup pointed at `src/fpvs_studio/assets/fpvs-studio.ico`
- rebuild with `.\scripts\build_exe.ps1` and confirm the icon appears on the EXE,
  taskbar, and app windows

Current branding assets:

- `packaging/assets/fpvs-studio-icon-1024.png`: canonical high-resolution source PNG
- `src/fpvs_studio/assets/fpvs-studio.ico`: generated GUI, PyInstaller, and Inno icon
- `docs-site/assets/fpvs-studio-icon.png`: generated documentation-site logo/favicon
- `docs/assets/fpvs-studio-readme-header.png`: README header image
- `docs/assets/fpvs-studio-social-preview.png`: GitHub social preview image
