# In-App Update Checker

Status: Completed

## Summary

Add an end-user update workflow under `File > Check for Updates`. FPVS Studio should
compare the installed app version against GitHub Releases, show the latest available
release, optionally show a short "What's New" summary with a link to full release notes,
download the installer with progress, and then close the running app before launching the
installer. The Inno installer handles replacing application files and relaunching FPVS
Studio after installation.

Implemented in this pass:

- backend-only `fpvs_studio.updates` package for release parsing, update selection,
  installer download, and explicit installer launch
- Inno `/RELAUNCH=1` support for updater-launched installs while preserving the normal
  post-install launch checkbox
- `File > Check for Updates` menu action
- PySide6 update dialog with current/latest version display, release notes link,
  download progress, install confirmation, and app quit handoff
- unit and pytest-qt smoke coverage for the update checker, downloader, and GUI flow
- architecture, GUI workflow, packaging, and README documentation updates

This feature builds on the existing packaging contract:

```text
pyproject.toml -> fpvs_studio.__version__
GitHub Release tag -> latest app version
GitHub Release asset -> FPVS-Studio-Setup-*.exe
Inno installer -> updates installed app files outside user project data
```

## User Workflow

Menu entry:

```text
File > Check for Updates
```

If the app is current:

```text
FPVS Studio is up to date.
Current version: 0.9.0b1
```

If an update is available:

```text
A new FPVS Studio version is available.
Current version: 0.9.0b1
Latest version: 0.9.0b2

What's New
<short release summary>

[View Full Release Notes] [Download Update] [Cancel]
```

During download:

```text
Downloading update...
<progress bar>
```

After download:

```text
FPVS Studio needs to close to install the update.

[Install and Restart] [Later]
```

When the user chooses install:

1. FPVS Studio launches the downloaded installer.
2. FPVS Studio exits.
3. The Inno installer replaces app files.
4. The installer relaunches FPVS Studio after installation.

## Release Conventions

GitHub release tags should be parseable as package versions:

- beta example: `v0.9.0b2` or `v0.9.0-beta.2`
- stable example: `v1.0.0`

Release assets should include exactly one Windows installer EXE matching:

```text
FPVS-Studio-Setup-*.exe
```

Draft releases must be ignored. Prerelease handling should be explicit:

- if the current installed version is a prerelease, include GitHub prereleases when
  checking for updates
- if the current installed version is stable, ignore prereleases by default

The first implementation can target the repository's public GitHub Releases endpoint.
Private-release authentication is out of scope.

## Proposed Files

- `src/fpvs_studio/updates/`
  - small backend package for release metadata, version comparison, and installer
    download helpers
  - no PySide6 imports
- `src/fpvs_studio/updates/github_releases.py`
  - fetch release JSON from GitHub
  - select the latest eligible non-draft release
  - parse tag/version and installer asset metadata
  - expose release URL and body/summary for "What's New"
- `src/fpvs_studio/updates/downloader.py`
  - stream installer downloads to a user-writable temp/cache path
  - report byte progress when `Content-Length` is available
  - avoid writing into the install directory
- `src/fpvs_studio/gui/update_dialog.py`
  - dialog for checking status, showing latest version, release notes link, download
    progress, and install confirmation
  - use Qt worker/thread patterns so network/download work never blocks the UI thread
- `src/fpvs_studio/gui/controller.py`
  - add `File > Check for Updates` action and open the update dialog
- `src/fpvs_studio/gui/application.py`
  - only if a relaunch or install-state startup hook becomes necessary
- `docs/GUI_WORKFLOW.md`
  - document `File > Check for Updates`
- `docs/PACKAGING.md`
  - document release tag and installer asset naming conventions that the updater expects

## Backend Contract

Return a typed result from the update checker:

```text
UpdateCheckResult
- current_version
- latest_version
- update_available
- release_url
- release_notes_summary
- installer_asset_name
- installer_download_url
- installer_size_bytes
- is_prerelease
```

Use Python package metadata as the current version source:

```text
fpvs_studio.__version__
```

Use PEP 440-compatible version comparison for local metadata. Normalize GitHub tags by
removing a leading `v` and accepting common beta aliases such as `0.9.0-beta.2` when
they normalize cleanly.

Network failures should become clear user-facing errors, not crashes.

## Download And Install Contract

- Download installers to a user-writable cache/temp location, not the install folder.
- Use a stable filename based on the GitHub asset name.
- If the downloaded file already exists and matches the expected size, allow reuse.
- Do not silently run an installer without a final user confirmation.
- Do not attempt to overwrite app files from the running Python process.
- On `Install and Restart`, launch the installer and quit FPVS Studio.
- Keep installer UI visible for the first implementation.
- Let the Inno `[Run]` post-install entry relaunch FPVS Studio.

## UI Requirements

- Add `File > Check for Updates`.
- Keep the dialog concise and user-facing; avoid developer terms such as PyInstaller,
  Inno Setup, package metadata, or release asset unless an error needs that detail.
- Show a progress bar during downloads.
- Show a clear "FPVS Studio will close" confirmation before running the installer.
- Include `View Full Release Notes`, opening the GitHub release page in the browser.
- If the release body is long, show a short clipped "What's New" preview and link out for
  the full notes.
- If the update check fails, explain that the user can still visit GitHub Releases
  manually.

## Security And Trust Boundaries

The first implementation is a convenience updater, not a full secure auto-update system.

Minimum guardrails:

- only use HTTPS GitHub release URLs
- only download `.exe` assets from the configured repository release metadata
- show the asset name and version before install
- do not run arbitrary URLs entered by users
- do not install silently

Future hardening can add checksums or code-signing verification once the release process
supports them.

## Boundaries

- Do not store projects, templates, logs, runs, or settings inside the install folder.
- Do not implement background silent updates.
- Do not add a persistent auto-update scheduler.
- Do not require GitHub authentication in the first pass.
- Do not block GUI startup when offline.
- Do not move installer behavior out of `packaging/inno/fpvs_studio.iss`.
- Do not add MkDocs work to this plan.

## Test Plan

Unit tests:

```powershell
python -m pytest -q tests\unit\test_update_check.py
python -m pytest -q tests\unit\test_update_download.py
```

GUI tests:

```powershell
python -m pytest -q tests\gui\test_update_dialog.py
```

Focused app checks:

```powershell
python -m pytest -q tests\unit\test_package_metadata.py tests\unit\test_import_boundaries.py
```

Release gate:

```powershell
.\scripts\check_quality.ps1
```

Manual smoke tests:

- no network: dialog shows a recoverable error and release-page fallback
- no update: dialog says the current app is up to date
- update available: dialog shows latest version and release notes link
- download: progress bar advances and writes installer to temp/cache path
- cancel download: partial work is handled cleanly
- install and restart: app launches installer, exits, installer updates app, and app
  relaunches

## Acceptance Criteria

- `File > Check for Updates` is visible in the app.
- Update checks do not freeze the GUI.
- Current and latest versions are displayed clearly.
- Prerelease/stable release handling follows the release conventions above.
- Installer download shows progress.
- The app asks before closing to install.
- The app launches the downloaded installer and exits.
- User projects, templates, settings, run history, and logs remain untouched by update
  flow code.
- The release notes link opens the GitHub release page.
- Full quality gate passes.

## Assumptions

- GitHub Releases is the source of update truth.
- The installer filename remains `FPVS-Studio-Setup-*.exe`.
- The Inno installer keeps a stable `AppId` across versions.
- The Inno installer remains responsible for replacing installed app files and relaunching
  FPVS Studio.
- Users may be on restricted Windows PCs, so the updater should preserve the current
  per-user installer model.
