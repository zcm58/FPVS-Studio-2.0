# Packaging FPVS Studio

This guide is for developer builds of the Windows executable bundle and installer. End
users use the installed `FPVS Studio.exe` and its bundled Update & Repair tool; neither
requires the source tree or a system Python environment.

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

Experiment Library access uses Windows Credential Manager without a Python keyring
dependency. On Linux, the declared `keyring` and `SecretStorage` dependencies provide
the explicitly selected Secret Service backend. The Studio spec includes that backend
and its package metadata only on Linux. A supported installed Linux environment must
provide an unlocked desktop keyring; verify enrollment/disconnect in the packaged app.
No plaintext credential fallback is allowed. See [Experiment Library](EXPERIMENT_LIBRARY.md).

Standard builds include `fpvs_studio.developer` and the publishing GUI modules.
Settings > Advanced controls the default-off developer preference; a password is
required to enable it and both enabling/disabling require restart. Updates retain the
existing per-user QSettings store. The bundled publisher uses app-owned workers and
needs no external Python or service checkout. Publishing still requires the owner's
noninteractive Git credentials (or explicit GH_TOKEN); credentials are never bundled.
See [developer publishing](EXPERIMENT_LIBRARY.md#developer-publishing-in-studio).

For release builds, compare native-library source paths in PyInstaller's
`Analysis-00.toc` with the authenticated published baseline. Exclude unrelated
application directories from the build process's `PATH`, while retaining verified
native dependency paths. Package-version pins alone do not prevent PyInstaller from
collecting support DLLs from another installed application.

## Version The App

Before building a release candidate, update the package metadata version:

- `pyproject.toml`: `[project] version = "X.Y.Z"`

That is the only developer entry point for changing the app version.
`src/fpvs_studio/__init__.py` reads `__version__` from source-tree `pyproject.toml`
when present and falls back to installed package metadata for bundled installs.
The PyInstaller spec includes package metadata in the bundled app.
The package distribution name is `fpvs-studio`; the GUI and executable still use the
display name `FPVS Studio`.

For the current release package, use the PEP 440-compatible package version `1.9.1`.
The GitHub Release title can use a friendlier beta label, but the release tag and
installer filename must use the exact package version.

The [v1.9.0 release record](exec-plans/completed/release-1.9.0.md) records the published
installer, direct 1.8.1 patch, payload audits and verification boundaries.

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

## Independent Updater Build And Installation

`scripts/build_installer.ps1` builds the independent updater before generating the final
ownership inventory. The existing `build_release.ps1` wrapper inherits this step through
the installer stage; `build_exe.ps1` alone continues to build Studio. The helper is included
in both the complete installer and any patch payload whose target changes it:

```text
dist\<BuildLabel>\FPVS Studio\Updater\FPVS Studio Updater.exe
```

For lightweight updater iteration without rebuilding Studio or executing an installer:

```powershell
.\scripts\build_updater.ps1 -BuildLabel independent-updater-dev
```

This uses the existing packaging environment, requires source and installed package
metadata to agree, and isolates output under `build/independent-updater-dev/` and
`dist/independent-updater-dev/`. The automatic `--packaging-check` diagnostic writes its
report under `build/<BuildLabel>/pyinstaller-updater/`; it checks the frozen version,
protocol, and absence of GUI imports without a window, network request, or installation.
It does not replace visible GUI or installed update acceptance. Restricted Windows
sandboxes may prevent the one-file bootloader from extracting its own temporary runtime;
run this bounded diagnostic in the approved ordinary Windows execution context when needed.
In a user-approved safe visible session, `-AllowVisibleGui` additionally runs the bounded
`--gui-smoke` mode; the installer build forwards that opt-in to the helper stage.

`packaging/pyinstaller/fpvs_updater.spec` builds a one-file helper with its own Python,
PySide6, and package metadata. It excludes authoring, runtime, PsychoPy, and scientific
dependencies, so damage to Studio's `_internal` directory does not prevent the helper
from starting. It does not compile Studio on the user's machine. The ordinary Inno
installer supplies the **FPVS Studio Update & Repair** Start Menu shortcut when the
helper is present and shortcuts have not been disabled.

Studio's `HelperClient` and the Start Menu entry stage the helper outside the installation
before running it. `%LOCALAPPDATA%\FPVS Studio\updater-helper` contains a flat set of
content-addressed executables, with no more than two recognized completed helper payloads.
Old locked helpers may remain within that bound; abandoned partials must be removed before
another copy is added. Staged bytes are rehashed under a no-write/delete guard through
process creation. This lets setup replace `Updater/FPVS Studio Updater.exe` while the
independent staged process continues to monitor it. Staging cleanup remains separate from
the installer-download cache and never visits project directories. Inno uninstall uses
the same guarded lock/file protocol to remove only recognized inactive helper payloads
and partials; active, linked, or unknown files remain untouched. It removes the helper
directory only if empty and cleans the installation-lock directory only when unlocked
and empty, without enumerating or deleting arbitrary contents.

Independent launches use PyInstaller's public environment-reset flag, giving each helper
its own temporary runtime even when it starts another copy of the same staged executable.
`updates/process_launch.py` removes inherited bundle paths from the child's runtime
environment and resets/restores Windows DLL search around process creation. This keeps
native setup and restarted Studio independent of the retiring helper's bundled libraries.

The implementation's acceptance record is the completed
[independent updater plan](exec-plans/completed/independent-updater.md). The completed
[v1.7.0 release record](exec-plans/completed/release-1.7.0.md) documents published assets,
direct patches from 1.5.3/1.6.0/1.6.1, packaged smoke checks, and payload/hash audits.
Clean-PC acceptance and installation over a user's working copy remain unperformed.
Preserve previously published artifacts and use isolated build labels for later candidates.

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
.\scripts\build_release.ps1 -AllowVisibleGui
```

Or double-click:

```text
scripts\build_release.cmd -AllowVisibleGui
```

The wrapper builds the PyInstaller bundle first, then builds the setup EXE from that
fresh bundle. The default release build refreshes editable package dependencies with `pip` before
PyInstaller runs. In Codex or any sandboxed runner, start `.\scripts\build_release.ps1`
with elevated network permissions so dependency resolution can fetch build backend
packages such as `hatchling` instead of failing and needing a second run.

When iterating after dependencies are already installed, use:

```powershell
.\scripts\build_release.ps1 -SkipInstall -AllowVisibleGui
```

If Inno Setup is installed somewhere custom:

```powershell
.\scripts\build_release.ps1 -AllowVisibleGui -InnoCompiler "C:\Path\To\ISCC.exe"
```

The individual commands remain available when you need to run only one stage. Build the
PyInstaller bundle first:

```powershell
.\scripts\build_exe.ps1
```

Then build the setup EXE:

```powershell
.\scripts\build_installer.ps1 -AllowVisibleGui
```

Expected output for the current package:

```text
dist\installer\FPVS-Studio-Setup-1.7.0.exe
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
.\scripts\smoke_packaged_app.ps1 -AllowVisibleGui
```

To run it against the installed app:

```powershell
.\scripts\smoke_packaged_app.ps1 -AllowVisibleGui -ExePath "$env:LOCALAPPDATA\Programs\FPVS Studio\FPVS Studio.exe"
```

If Inno Setup is installed somewhere custom:

```powershell
.\scripts\build_installer.ps1 -AllowVisibleGui -InnoCompiler "C:\Path\To\ISCC.exe"
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

The installed ownership record is `fpvs-owned-files-v1.txt`.
Empty historical `.dist-info` directories may remain;
frozen app version lookup ignores entries without FPVS Studio metadata and requires
exactly one complete distribution in the bundle. Missing, invalid, or ambiguous
version metadata is an explicit startup error rather than a `None` app version.
Inno captures previous ownership before replacing files and reconciles obsolete entries only after successful
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
- run `.\scripts\smoke_packaged_app.ps1 -AllowVisibleGui -ExePath "$env:LOCALAPPDATA\Programs\FPVS Studio\FPVS Studio.exe"`
- create/open a project
- open `Tools > Image Resizer`
- run the PsychoPy test launch path
- install a newer setup EXE over the older installed app and confirm settings, projects,
  condition templates, `runs/`, and `logs/` remain intact

## Direct Patch Releases

v1.5.1 adds patch-aware updating. Earlier app versions still select the full installer;
therefore every release retains `FPVS-Studio-Setup-<version>.exe`. A manually downloaded
patch can bootstrap an exact earlier installation. Patches use the same Inno application
identity and installation folder, without reinstalling unchanged dependencies.

`build_release.ps1` builds one complete target bundle, its full installer, optional
patch installers, and `FPVS-Studio-Update-<version>.json`. Set the version in
`pyproject.toml` first. For each supported baseline provide the exact ownership manifest
extracted from its authenticated published installer and the manifest's SHA-256. Preserve
published bundles/installers and dependency versions; rebuilding an old source tag does
not establish an identical baseline. Runtime dependencies should remain pinned to the
preserved build environment when producing a small application fix.

```powershell
.\scripts\build_release.ps1 -SkipInstall -AllowVisibleGui `
  -BuildLabel release-1.5.2 `
  -BaselineInventory build/release-1.5.2-baseline/published-v1.5.1-current-owned-files.txt `
  -BaselineInventorySha256 9961840684982e9c4ff1f1cce253a6a50250ed40777da77babf46b9e84f85073
```

`-SkipInstall` preserves the current environment and requires its installed FPVS Studio
metadata to match the release version. Refresh the editable app metadata separately with
`python -m pip install --no-deps -e .` when needed. Multiple baselines use matching ordered
arrays of manifest paths and hashes. `-AllowVisibleGui` requires an approved native
Windows session for packaged checks; offscreen execution is rejected. `-SkipSmoke` may
stage artifacts while that check is pending, but does not establish release acceptance.

Upload the generated full installer, every patch installer, and update JSON to the same
GitHub release, initially as a draft. Example assets:

```text
FPVS-Studio-Setup-1.5.2.exe
FPVS-Studio-Patch-1.5.1-to-1.5.2.exe
FPVS-Studio-Update-1.5.2.json
```

Publish only after all assets are present and their GitHub sizes/SHA-256 digests match
local artifacts. Do not replace published bytes under an existing version. The JSON
contains `schema_version: 1`, `target_version`, `platform: "windows-x64"`, and `patches`.
Each entry binds `from_version`, `source_inventory_sha256`, `asset_name`, `size_bytes`,
and `sha256`. Full installer metadata continues to come directly from GitHub. The app
fetches the bounded JSON through the same trusted GitHub/CDN boundary and verifies its
GitHub digest before using it. Invalid or tampered metadata is an error, not an implicit
permission to run a different file.

The independent helper reads the exact per-user Windows installation registration rather
than treating its own package version as Studio's installed version. For discovery it
authenticates the release JSON and installed ownership-inventory bytes, then offers a
smaller direct patch whose source version matches. It does not hash installed payload
files during discovery or download. Missing or incompatible inventory selects the full
installer with an explicit reason. A candidate is described as requiring compatibility
checks during installation; changes to installed payload files are detected by native
setup before mutation. Patches are not chained. Patch cache receipts retain source and
target identity; stale or incompatible payloads follow the existing bounded-cache policy.

The older direct backend API retains its complete Python baseline verifier for callers
that request it. Its reads reuse Windows API bindings and keep the current directory's
ancestor pins between adjacent files, while every file receives fresh identity/hash
checks. These latency improvements remain, but the independent workflow no longer
repeats those scans at discovery/download/launch. Typed phase events distinguish metadata,
package transfer/verification, waiting for Studio, installation, and restart. Manual checks
cancel the pending or running silent startup check through the shared lifecycle.

`build_patch.py` generates only changed and added target files while retaining the full
target ownership inventory. The patch's Inno mode independently verifies registration,
source version, manifest identity, and baseline bytes before writes. Unknown files at
new payload paths block the patch. Path checks reject unsafe aliases, links, and protected
project-data names. A verified transaction marker supports rerunning the same patch
after a known partial installation; unknown/corrupt states require full-installer repair.
Target files and the installed inventory must verify before successful handoff. A
post-copy verification failure returns exit code 12, displays a repair message, retains
the marker, and suppresses relaunch. Windows may already record the target version;
rerun the same downloaded patch to repair a known state, or use the full installer
when bytes are unrecognized. Do not depend on the application being able to start
after an interrupted update. Obsolete owned files are reconciled
before automatic relaunch. This is a recoverable changed-file update, not an atomic
whole-directory swap or a guarantee of automatic rollback after power loss.

Verification includes updater/packaging focused routes, registered GUI coverage, native
Inno compilation, and `scripts/check_patch_installer_lifecycle.py`. The lifecycle harness
uses synthetic bundles and unique test application identities beneath `build/`; it skips
shortcuts, application launch, production app closing, and production updater-cache hooks.
Never treat `/DIR` alone as isolation when running a production installer: its AppId and
uninstall registration still belong to the user's installed application.

## In-App Update Flow

Installed users can use `File > Check for Updates`. FPVS Studio also runs one silent
startup check after the Welcome window appears. Both routes call `HelperClient` from
the existing app-owned worker lifecycle. A private helper process checks GitHub Releases
and returns current/latest versions, notes, and a candidate package type/size without a
full installation scan. The helper downloads the selected package only after the user
chooses `Download Update`, verifying its GitHub SHA-256 and size as part of transfer/reuse.
Source development uses the same entry in a separate Python process; packaged Studio
requires the bundled helper. A source process cannot identify itself as the installed
Studio process for an installation handoff.
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

On `Install and Restart`, Studio asks for final confirmation and saves through its existing
GUI callback. The staged helper reacquires the official GitHub asset identity, verifies
cached bytes, and pins a Windows process handle for the exact registered Studio executable.
Private messages have a versioned, bounded schema. The helper sends a fresh ready nonce;
Studio must accept that nonce before the helper can proceed. Studio exits only after its
handoff worker finishes successfully. An early EOF, cancellation, or missing acceptance
cannot start setup.

The helper holds a separate `%LOCALAPPDATA%\FPVS Studio\updater-install` lock through
the bounded process wait, final registration/other-instance check, installation, and
restart. It never terminates Studio. Managed setup receives `/DIR=<registered root>`,
`/VERYSILENT`, `/SUPPRESSMSGBOXES`, `/NORESTART`, `/NOCLOSEAPPLICATIONS`, and `/NOLAUNCH=1`.
Inno owns replacement, complete patch baseline/target verification, and recovery. The
helper waits for setup's exit code and checks expected registration before restarting
Studio once. Exit 12 or any failed install prevents restart and exposes Update & Repair.
The installation-committed phase is explicit; a late cancellation cannot misreport a
failed mutation as cancellation before installation. Once setup starts, cancellation
cannot terminate it.

The standalone **Update & Repair** window works without opening Studio. It derives the
installed version from registration and offers an explicit full installer, including
same-version reinstallation; older versions are rejected. The full repair path remains
available when a patch is incompatible or Studio cannot start. It requires a registered
installation; first installation uses the full installer normally. All Studio instances
must be closed before standalone installation. User projects, settings, templates, run
history, and logs remain outside the install folder. Ordinary manual installer runs
retain their standard launch checkbox; only managed updates delegate restart to the helper.

Closing an update dialog through its button, Escape, or the window close control requests
cancellation and defers teardown until updater work finishes. Application quit similarly
cancels/finishes app-owned updater jobs without destroying running Qt threads or blocking
the GUI thread. Metadata checks, hashing, cache housekeeping, and download I/O all stay
off the GUI thread. Startup never downloads an installer or launches setup automatically.
Network work uses cancellation checkpoints and bounded socket reads. For private pipe
workers, cancellation or EOF also starts an eight-second watchdog for stalled DNS; it
exits the unaccepted worker while its bootloader remains alive to clean temporary files.
The client closes input and allows that cleanup before forced termination as a last resort.
Acceptance atomically disarms this watchdog before installation can begin. The standalone
window's local check/download workers still wait for their network call to return on cancel.

### Updater And Upgrade Acceptance

Run the focused `updates`, `gui`, and `packaging` verification scopes, then repo
precommit. Ordinary local verification uses temporary files and mocked network/process
operations; it does not run an installer, uninstall an application, or execute Qt.
Registered Qt coverage requires a separately approved safe visible environment.
The updates route includes `test_update_helper.py` for IPC, staging, registration, locks,
and handoff, plus `test_updater_main.py` for the GUI-free diagnostic entry. Candidate
selection and deferred-download/managed-launch checks remain in `test_update_patch.py`.
The registered `tests/gui/test_update_dialog.py` covers standalone repair and apply
progress, including commitment and cancellation. See
[GUI workflow](GUI_WORKFLOW.md#gui-implementation-map) for ownership and acceptance sizes.

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
