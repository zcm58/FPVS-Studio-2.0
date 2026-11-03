# Studio 2.6.0 release

Status: Active

## Authorization, version and source scope

Explicitly requested on 2026-11-02: pull current source, commit/push local work,
build the next Studio release and publish it to GitHub with concise user-facing
notes. This request authorizes publication; no historical draft supplies approval.

Root confirmed the latest published stable GitHub release is `v2.5.8`, with no newer
published stable version. Local `v2.5.8` resolves to
`178591a06f3e27dceb3fde66cffef37c357008f4`; the pulled clean source baseline is
`9e3983f`. There are 29 commits after the tag, including the previous release record.
The package was still 2.5.8 before this release change. Root selected 2.6.0 under
[Packaging's minor-feature rule](../../PACKAGING.md#version-the-app) and owns the
canonical `pyproject.toml` version update.

Scope since 2.5.8: clearer Setup hierarchy and combined Display/Session, independent
participant randomization and exact fixation timing reuse, saved/randomized partial
condition blocks with within-block dragging, Recording Reminder wording, persistent
Light/Dark/Auto themes, and source-only Mac authoring/testing with qualified automated
bundle transfers. The obsolete Create Control Condition workflow is removed; manual
condition authoring, saved conditions/assets and general variants/transforms remain.
Windows stays the primary packaged app. This release does not add a Mac installer,
new acquisition hardware or a claim of physical Mac display/GUI qualification.

## Artifacts and exact notes

Build label: `release-2.6.0` (root checked that it did not already exist).
Retain build evidence under `build/release-2.6.0-evidence/`. This is a full-installer-only
release matching the preceding four-asset layout; do not generate optional patches.

Expected release assets:

- `FPVS-Studio-Setup-2.6.0.exe`
- `FPVS-Studio-Setup-2.6.0.exe.sha256`
- `FPVS-Studio-Update-2.6.0.json`
- `FPVS-Studio-Update-2.6.0.json.sha256`

The update JSON must identify `target_version=2.6.0`, `platform=windows-x64` and an
empty patch list. Record each final asset's byte size/SHA-256 after building; checksum
sidecars must agree with their corresponding bytes. No placeholder hash is evidence.

Root's exact release notes are retained in the ignored evidence directory as
`release-notes.md`; GitHub receives only these short bullets:

- Cleaner setup, Settings and Light/Dark/Auto themes.
- Repeatable image orders, condition blocks and fixation timing.
- Mac source setup and testing, with Windows–Mac project transfers.

## Prepublication work and acceptance

- [x] Pull/audit current source and verify the latest published baseline/version;
  select the next minor version from actual new features, not an old release draft.
- [ ] Update canonical package version to 2.6.0, verify imported/installed metadata,
  then commit/push the intended source. Record the exact build commit and ensure
  `v2.6.0` targets that source; preserve unrelated work and published 2.5.8 assets.
- [x] Run the applicable safe release checks and retain earlier focused GUI/source
  evidence. Packaging focused passed 189 tests, docs focused 13, and full repo precommit
  passed 5,019 tests with 18 skips; mypy/Ruff/compilation/audits are green. Packaged GUI
  smoke remains a separate build check below.
- [ ] Record the actual build environment and native-library source paths/hashes;
  compare PyInstaller collection/warnings with the authenticated 2.5.8 baseline.
  Exclude unrelated application PATH entries and review new dependencies explicitly.
- [ ] Refresh editable application metadata. Use `-SkipInstall` only when dependencies
  and metadata are already current; preserve the reviewed environment. Build with the
  canonical `scripts/build_release.ps1` and isolated label, including its independent
  updater, full installer and update JSON.
- [ ] Run the bounded packaged GUI/import smoke in the existing approved synthetic
  native Windows environment, with no hardware or real production installation.
  Verify Studio/updater version 2.6.0, required frozen modules/resources/font/license,
  complete owned-file inventory, and frozen-source/native dependency consistency.
- [ ] Calculate exact size/SHA-256 of all four artifacts and validate the JSON and
  checksum sidecars. Retain source association, inventories, logs and audit outputs.
- [ ] Verify repository release immutability is enabled. Stage a new `v2.6.0` GitHub
  draft in `zcm58/FPVS-Studio-2.0`, attach all four artifacts, and compare the complete
  draft asset inventory plus every remote byte size/SHA-256 with local artifacts.
  Resolve any mismatch before publishing; do not replace a published version's bytes.
- [ ] Publish the verified draft as the intended latest stable release under the
  existing explicit request. Record exact tag, release ID/URL and immutable status.
- [ ] Independently download public assets and match local size/SHA-256/sidecars;
  verify GitHub release/asset attestations using the correct repository. Confirm the
  production updater resolves 2.6.0 and the full installer/update JSON correctly
  without running an installation. See [artifact provenance](../../LIBRARY_ARTIFACT_PROVENANCE.md#release-publication).
- [ ] Record the final evidence and public release link, update the current Packaging
  record and plan index, and archive this plan once the requested work is complete.

## Verification boundaries

Build scripts produce local artifacts; they do not publish them. Follow the existing
[Packaging](../../PACKAGING.md) draft-first, immutable-release and downloaded-byte trust
contract. The current request authorizes build/publication and the bounded synthetic
packaged smoke; it does not authorize installing over the working application,
destructive upgrade/uninstall/failure tests or device/marker activity.

Existing clean-PC/VM installed lifecycle and physical timing/hardware gates remain
separate and must be reported accurately. Source tests, static frozen audits, native
bounded import checks and actual Mac CI/bundle transfers do not establish those gates
or physical Mac GUI/high-DPI/OS-global theme transitions. Preserve the active Mac
acceptance plan rather than turning its deferred checks into a release claim.

## Progress and evidence

Root owns version/build/publication. Results received so far:

- Full repo precommit passed 5,019 tests with 18 skips (14 Windows symlink and four
  native POSIX cases). Full-source mypy passed for 266 files and the additional Darwin
  target passed; Ruff, compilation and audits are green. The complete log is retained
  at `build/release-2.6.0-evidence/precommit.log`. Docs focused passed all 13 tests.
- Packaging focused passed 189 tests; `pip check` passed. Across 145 distributions,
  only editable app metadata changed from 2.5.8 to 2.6.0. All 555 native input hashes
  match the authenticated baseline; its 2.5.8 inventory and attestation checks passed.
- Source CI [run 41572543855](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41572543855)
  targets exact pulled commit `9e3983f391ce91d4335713072c1c345374ab2aec`, before the
  version/documentation-only release changes. The primary Windows contracts/fixture
  gate, both native Mac arm64/x86_64 jobs and Windows validation of both Mac exports
  passed. Final Mac-origin return jobs on arm64/x86_64 remain in progress; the full
  transfer chain/overall run is not yet recorded as passed.
- The isolated release build has bounded native packaged GUI/import smokes enabled;
  actual build/smoke results and the release-prep source commit are pending. Only
  version/documentation bytes differ from the pulled source; root will commit/push
  those before associating the final build tag.

No installer has been executed or release published by this documentation subtask.
Record actual remaining results as they arrive; do not infer them from a successful
build command or earlier release history.
