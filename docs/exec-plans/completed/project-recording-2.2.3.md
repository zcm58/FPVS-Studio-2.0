# Project recording persistence and 2.2.3 release

Status: Completed

The user requested an immediate fix and release: recording device settings must
persist independently for each project. On this machine Semantic Categories must
use Unicorn and every other active project must use BioSemi.

## Implementation and acceptance

- Persist a typed optional recording configuration in ProjectSettings; absent
  configurations use BioSemi. Keep recording transport outside compiled contracts.
- Stop injecting the computer-wide preference when projects open. Settings Apply
  atomically saves only recording fields and preserves unrelated pending edits.
- Preserve the choice through project save/reopen, bundle and config interchange.
- Validate invalid input and failed writes without changing the accepted device.
- Back up and update the 15 active projects under the configured external-drive
  root, excluding archival backups and migration snapshots.
- Verify focused project-io/GUI/runtime checks and repo precommit. Add registered
  Qt coverage; do not run unapproved Qt or physical acquisition checks.
- Bump to 2.2.3, commit/push, build full installer and direct patches from published
  2.2.1 and 2.2.2 baselines, audit, verify draft assets and publish release notes.

## Evidence

Initial project-io checks passed 261 tests with two Windows symlink skips.
The existing global Unicorn QSettings preference overrides every opened document.
No user installation or acquisition process will be launched during checks.

The local project repair completed: 14 BioSemi selections and one Unicorn selection
for Semantic Categories; only recording fields changed. Exact originals are retained
under `build/project-recording-2.2.3/project-backups/`.

## Completed implementation and verification

- Device and UDP port persist in the optional typed `ProjectSettings.recording`.
  Older projects without that field use BioSemi. Recording Setup is available only
  with an open project; Apply atomically saves only recording fields and preserves
  other pending setup edits. Failed writes retain both saved and accepted device.
- The obsolete computer-wide override is ignored. Save/reopen, project switching,
  `.fpvsconfig` and `.fpvsbundle` transfer restore the saved project choice. Runtime
  snapshots identify `project_settings` provenance; compiled timing is unchanged.
- Rechecked all 15 active external-drive projects after publication: Semantic
  Categories remains Unicorn, the other 14 remain BioSemi. Original backups and the
  per-project hash report remain under `build/project-recording-2.2.3/`.
- Repo precommit passed Ruff, compilation, mypy across 212 source files, repository
  audits and 2,419 safe tests; 11 Windows symlink-permission tests skipped. Focused
  routes passed project-io 270 (two skips), GUI seven, packaging 181 and docs nine.
- Registered Qt coverage includes Apply/Cancel, project reopening/switching with an
  obsolete global override, failed saves, output labels and existing size budgets.
  Qt/manual GUI, physical EEG and installed upgrade/repair/uninstall were not run.

## Release publication

Source commit `ba2ff23eac9334fdc860811ffdf0eb39051e04d6` was committed and pushed
before packaging. Annotated tag `v2.2.3` points to that commit.

[FPVS Studio 2.2.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.3)
is the public latest release with full installer, direct 2.2.1/2.2.2 patches,
update JSON and four checksum files. All eight uploaded sizes and GitHub SHA-256
values match the audited local files. Release notes are exactly:

> Recording device settings are now saved per project and persist when reopening or switching projects. Projects without a saved device selection use BioSemi.

- Authenticated baseline inventories match the published installers.
- Extracted full installer matches all 7,061 final owned files.
- 2.2.1 patch changes/adds 33, removes 937 and retains 7,028 files.
- 2.2.2 patch changes/adds 13, removes eight and retains 7,048 files.
- Both patches reconstruct the complete target; all source/target/payload/transaction
  manifests, update JSON and checksum files were verified before publication.
- Native payloads match 2.2.2 with no additions/removals. The 488 native build inputs
  come only from the repo Python environment or Windows; 211 embedded package
  submodules match source-compiled code. Frozen non-GUI updater diagnostic passed.
- Live updater selects each direct patch, reports no update for 2.2.3 and uses the
  full installer for repair. No installer or acquisition process was executed.

### Installer hashes

- `FPVS-Studio-Setup-2.2.3.exe`: 299,022,455 bytes; SHA-256
  `9d14f75cc0a1638dd4f8fd97ce7f5fb9780febf153ecdba059ff7d360921be4a`.
- `FPVS-Studio-Patch-2.2.1-to-2.2.3.exe`: 72,363,428 bytes; SHA-256
  `3f962b59e7a345fb5ec8b802b42ffbfc4b72a9f4720baba81358b6ecbc81c377`.
- `FPVS-Studio-Patch-2.2.2-to-2.2.3.exe`: 72,164,069 bytes; SHA-256
  `5297f0bdf58ada48867df2a152142b118bbde19e2d5a9f6ea7f7bcb248d2c2f2`.

Release evidence is retained under `build/release-2.2.3-baseline/` and
`build/release-2.2.3/`; assets are under `dist/release-2.2.3/installer/`.
