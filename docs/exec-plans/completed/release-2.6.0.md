# Studio 2.6.0 release

Status: Completed

Published [Studio 2.6.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.6.0)
as the latest stable immutable release, ID `432257846`, at `2026-11-03T03:54:27Z`
(November 2 in Chicago). Independent public-byte, attestation and production-updater
checks all passed. The immutable build tag and published bytes are unchanged.

## Authorization, version and source scope

Explicitly requested on 2026-11-02: pull current source, commit/push local work,
build the next Studio release and publish it to GitHub with concise user-facing
notes. This request authorizes publication; no historical draft supplies approval.

At release preparation, root confirmed the latest published stable GitHub release
was `v2.5.8`, with no newer published stable version. Local `v2.5.8` resolves to
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

Published assets were checked against local bytes and GitHub digests before publication:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.6.0.exe` | 298,969,071 | `ddcd6074bed89dec099c78a1762b193be951ac6a16fb54ed3a0e824b7bfb18c0` |
| `FPVS-Studio-Setup-2.6.0.exe.sha256` | 95 | `4460439ad1bf3a2d49bc4d922749ac4f2e51807c3daf0ca12a7654cbb5a8d953` |
| `FPVS-Studio-Update-2.6.0.json` | 107 | `28a9194ecbb5d2d3e6ea9f9a1768302e5886ccccff4baf47c7cd64e3ab864f62` |
| `FPVS-Studio-Update-2.6.0.json.sha256` | 97 | `199362d8588a1caab46252a8f791cbc6140859dadaf6c60537bca326d1707a80` |

The update JSON identifies `target_version=2.6.0`, `platform=windows-x64` and an
empty patch list; checksum sidecars agree with their corresponding bytes. Full audit
results are retained in `build/release-2.6.0-evidence/artifact-audit.json`. Independent
fresh public downloads also match these byte sizes/SHA-256 values and sidecars.

Root's exact release notes are retained in the ignored evidence directory as
`release-notes.md`; GitHub received only these short bullets:

- Cleaner setup, Settings and Light/Dark/Auto themes.
- Repeatable image orders, condition blocks and fixation timing.
- Mac source setup and testing, with Windows–Mac project transfers.

## Prepublication work and acceptance

- [x] Pull/audit current source and verify the latest published baseline/version;
  select the next minor version from actual new features, not an old release draft.
- [x] Update canonical package version to 2.6.0, verify imported/installed metadata,
  then commit/push the intended source. Record the exact build commit and ensure
  `v2.6.0` targets that source; preserve unrelated work and published 2.5.8 assets.
- [x] Run the applicable safe release checks and retain earlier focused GUI/source
  evidence. Packaging focused passed 189 tests, docs focused 13, and full repo precommit
  passed 5,019 tests with 18 skips; mypy/Ruff/compilation/audits are green. Packaged GUI
  smoke remains a separate build check below.
- [x] Record the actual build environment and native-library source paths/hashes;
  compare PyInstaller collection/warnings with the authenticated 2.5.8 baseline.
  Exclude unrelated application PATH entries and review new dependencies explicitly.
- [x] Refresh editable application metadata. Use `-SkipInstall` only when dependencies
  and metadata are already current; preserve the reviewed environment. Build with the
  canonical `scripts/build_release.ps1` and isolated label, including its independent
  updater, full installer and update JSON.
- [x] Run the bounded packaged GUI/import smoke in the existing approved synthetic
  native Windows environment, with no hardware or real production installation.
  Verify Studio/updater version 2.6.0, required frozen modules/resources/font/license,
  complete owned-file inventory, and frozen-source/native dependency consistency.
- [x] Calculate exact size/SHA-256 of all four artifacts and validate the JSON and
  checksum sidecars. Retain source association, inventories, logs and audit outputs.
- [x] Verify repository release immutability is enabled. Stage a new `v2.6.0` GitHub
  draft in `zcm58/FPVS-Studio-2.0`, attach all four artifacts, and compare the complete
  draft asset inventory plus every remote byte size/SHA-256 with local artifacts.
  Resolve any mismatch before publishing; do not replace a published version's bytes.
- [x] Publish the verified draft as the intended latest stable release under the
  existing explicit request. Record exact tag, release ID/URL and immutable status.
- [x] Independently download public assets and match local size/SHA-256/sidecars;
  verify GitHub release/asset attestations using the correct repository. Confirm the
  production updater resolves 2.6.0 and the full installer/update JSON correctly
  without running an installation. See [artifact provenance](../../LIBRARY_ARTIFACT_PROVENANCE.md#release-publication).
- [x] Record the final evidence and public release link, update the current Packaging
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

Completed release evidence:

- Full repo precommit passed 5,019 tests with 18 skips (14 Windows symlink and four
  native POSIX cases). Full-source mypy passed for 266 files and the additional Darwin
  target passed; Ruff, compilation and audits are green. The complete log is retained
  at `build/release-2.6.0-evidence/precommit.log`. Docs focused passed all 13 tests.
- Packaging focused passed 189 tests; `pip check` passed. Across 145 distributions,
  only editable app metadata changed from 2.5.8 to 2.6.0. All 555 native input hashes
  match the authenticated baseline; its 2.5.8 inventory and attestation checks passed.
- Release preparation was committed/pushed as exact build/tag source
  `112ad201fca2606f0944ab4bf527e6313fece96c`. Local `v2.6.0` resolves to that commit.
  App source is unchanged from pulled `9e3983f` apart from package version 2.6.0 and
  release documentation. The final evidence record will use a docs-only follow-up
  commit without moving the build tag.
- Bounded native packaged GUI/import smoke passed with `ok=true` and version 2.6.0;
  the report is copied into the evidence directory. Updater GUI and GUI-free diagnostic
  checks passed. All 266 Studio modules plus entry and all 22 updater modules plus
  entry match clean build source; the deleted control-condition dialog is absent.
- All 7,062 bundle files match the complete ownership inventory, SHA-256
  `0a58b7801cab3472a0432d012d2b7ec1f6bda0bf25fbc3b14360b72e61e1a94e`.
  All 555 native TOC records, 482 DLL/PYD files and 22 warnings match the 2.5.8 baseline.
- All four draft assets, byte sizes and GitHub digests matched `artifact-audit.json`
  before publication. The immutable/latest stable release is ID `432257846`; exact
  notes were reviewed from the retained file. No production installer, real project
  or acquisition hardware was executed.

## Source CI association and limits

[Run 41572543855](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41572543855)
targets pulled source `9e3983f391ce91d4335713072c1c345374ab2aec`. Primary Windows,
both native Mac lanes, Windows return validation and arm64 final return jobs succeeded.
The final Intel return job and overall run conclude `cancelled` in a concurrency race;
they are not recorded as overall green. Every Intel return step nevertheless succeeded,
including native comparison and evidence upload. Independently retrieved GitHub-digest-
verified evidence ZIPs report exact semantic project, 14-asset SHA-256 and seven-run
60 Hz compiled-plan/fixation matches for both Mac CPUs and both Windows returns.
No substantive source/transfer check failed in that audited run.

[Run 41574206790](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41574206790)
was automatically started for exact build source `112ad201fca2606f0944ab4bf527e6313fece96c`.
Its final result is not asserted in this record. It was pending when the release was
qualified; it is not an additional release gate because runtime code is identical to
the qualified pulled source apart from the separately checked package version/docs.
The earlier evidence does not imply an overall green conclusion for either run or
physical Mac GUI, hardware, high-DPI or OS-global theme-transition acceptance.

## Public verification and updater acceptance

`build/release-2.6.0-evidence/public-download-audit.json` passed. The published release
is stable/latest/immutable, ID `432257846`. Locked annotated tag object
`db0ac29bd78118cf6dfe34ff19aca285a946725b` peels to exact build source
`112ad201fca2606f0944ab4bf527e6313fece96c`. The source association is verified through
that immutable annotated tag.

All four fresh unauthenticated public downloads match local and GitHub byte sizes/
SHA-256 values. Update JSON and checksum sidecars validate. Release attestation and
all four asset attestations verify on the first attempt, with zero retries; no
published bytes or tags were modified.

`build/release-2.6.0-evidence/public-updater-check.json` passed all eight bounded live
checks using production updater code. Previous 2.5.8/older 2.4.4, registration-aware,
forced-full and repair selections resolve to the full 2.6.0 installer. Current 2.6.0
reports no normal update while allowing repair; 2.6.1 rejects downgrade. These checks
read no working installation and execute no installer or Qt.

Requested source preparation, build, immutable publication and public verification
are complete. This archived evidence is a docs-only follow-up to the immutable build
commit; the build tag remains fixed. Existing installed-lifecycle and Mac physical
acceptance gates remain separate as documented above. Final documentation hygiene
and all 13 focused docs tests passed after archiving.
