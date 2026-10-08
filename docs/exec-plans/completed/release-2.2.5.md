# FPVS Studio 2.2.5 Release

Status: Completed

## Scope

Released the requested bundle and Windows path compatibility fixes. Bundle review,
imports, cache access, project/manifest opening, root/recent preferences, restart
discovery, template setup and image-readiness signatures now share the long-path
filesystem adapter. The release also includes actionable storage/authentication/
truncated-transfer errors, case-conflict validation and scaled-display calculations.
The earlier private Library service streaming fix was already deployed separately.

## Publication

- Stable Latest release: <https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.5>.
- Release ID: `402244286`. Tag: `v2.2.5`.
- Tagged/built source: `267453f779102c1cac5ddf7de4ab3c58ead89459` on master.
- Compatibility/version source commit: `c63990f17e6a9d5d01c4b14aac67499fc6e67579`.
- Full installer, direct 2.2.4 patch, update JSON and three SHA-256 sidecars published.
- Exact user-provided release note:

Improved backend handling of long windows filepaths causing errors on some systems.

## Artifacts

- `FPVS-Studio-Patch-2.2.4-to-2.2.5.exe`: 74387943 bytes; SHA-256 `01a00af469e0707c4a3743e3518c98a616419ed412312b45cf70bc07c6b62836`.
- `FPVS-Studio-Setup-2.2.5.exe`: 301002902 bytes; SHA-256 `0eeea66307a638fb3b445199aa5b99de18ba154ea9fe767fb1cb547f16d9627b`.
- `FPVS-Studio-Update-2.2.5.json`: 435 bytes; SHA-256 `d32b33e93d0b9ccd4166e8cd0e9caddc162d4a19ee8489e948a9dee91965a774`.

Artifacts remain under `dist/release-2.2.5/installer/`; source, baseline metadata,
build log, upload sizes/digests and GitHub publication readback remain under
`build/release-2.2.5/`. The app/updater bundle is under
`dist/release-2.2.5/FPVS Studio/`.

## Check Boundary And User Waiver

The user explicitly requested "skip release checks to be faster." No additional
release test suites, full/patch extraction and reconstruction audits, source/native
payload audits, GUI smoke, installed-upgrade tests or live updater-selection tests
were run. Do not describe these waived checks as passed.

Packaging focused had already started before the waiver and completed with 181 tests
passing. Earlier compatibility implementation tests are documented in the active
private-library audit. The existing build completed its required package metadata,
ownership-inventory checks and bounded no-GUI updater packaging diagnostic. The
2.2.4 baseline installer/inventory identities were required inputs to patch creation.
GitHub accepted all six assets; uploaded sizes/digests and exact release text matched
the prepared files. Source master and the release tag were pushed.

Runtime dependencies were left at their existing installed versions; only editable
Studio package metadata was refreshed. Build outputs used isolated release folders
and the existing sanitized build PATH. No existing app installation or project data
was modified. Second-PC, physical-display/recording and EEG acceptance remain unrun.

The user paused before building because the PC was about to lose power. The saved
checkpoint was resumed on October 2, 2026, with the waiver and exact release note
preserved.
