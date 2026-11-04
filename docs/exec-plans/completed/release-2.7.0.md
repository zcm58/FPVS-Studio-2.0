# Studio 2.7.0 release

Status: Completed

Date: 2026-11-04

## Authorization and scope

The user requested building and publishing a new FPVS Studio release with the
participant workbook changes already committed in `19ccc9b`. The latest stable
release was verified as `v2.6.1`; workbook consolidation is a new user-facing
feature, so Packaging's minor-version rule selects 2.7.0.

Publish a full Windows installer, update JSON and both checksum sidecars. Mac
remains source-only. Preserve existing releases, bundles, dependencies and user
data. The normal output is `logs/participant_summary.xlsx` relative to each
project root, with separate tabs for summary, demographics, fixation conditions,
individual responses, task answers and notes; unusually long values use a linked
Full Text tab. Centering and automatic sizing apply on generation and append.
Optional diagnostic exports and canonical recovery records remain available.

## Build and acceptance

- Use isolated label `release-2.7.0` and retain private evidence under
  `build/release-2.7.0-evidence/`.
- Refresh editable package metadata without updating qualified dependencies.
  Compare native inputs and payload against authenticated 2.6.1 evidence.
- Run packaging focused and safe repository precommit checks. Verify exact
  staged metadata, ownership inventory, resources and frozen source.
- Stage without GUI execution, then test the existing staged bytes in the
  explicitly approved visible Windows session.
- Commit/push the exact build source, bind annotated `v2.7.0` to it and check
  source CI. Create a draft, upload all four assets and compare every size and
  SHA-256 before publishing latest/stable with repository immutability enabled.
- Independently verify public downloaded bytes, release/asset attestations and
  production updater selection without executing an installer.

## Progress

- Repository was clean and synchronized at `19ccc9b` when release work began.
- Latest stable `v2.6.1` is immutable; repository future-release immutability is
  enabled. Packaging focused passed 192 checks before the version change.
- Exact build source `3565448df1d85cc56e205d68d30069ec3a4e878b` was committed
  and pushed. Annotated `v2.7.0`, object
  `aa455f0121e002ee9695ca36297e2cac22638ff4`, resolves directly to that source.
  Release records after this commit change documentation only. This source also
  retains the vertical image visual angle and Mac compatibility fixes since 2.6.1.
- Post-version packaging focused passed 192 checks; docs focused passed 13.
  Safe precommit passed Ruff, compilation, repository audits, Windows mypy for
  269 source files, the nine-file Darwin target and 5,227 tests with 32 platform
  or environment skips. Dependency consistency passed.
- Canonical build completed with `-SkipInstall -SkipSmoke` after a metadata-only
  editable install refresh. The qualified dependencies remained unchanged. All
  555 native input paths/hashes, 482 DLL/PYD files and 22 normalized warnings
  match the authenticated published 2.6.1 baseline.
- All 7,062 owned files match inventory SHA-256
  `f6ef54f7e3653e9287567f6c4aec425c90c83e5c16ea320a6c1585a980dc6ee9`.
  Frozen Studio's 269 modules plus entry and updater's 22 modules plus entry
  match exact source code objects. Both metadata records and the GUI-free
  updater diagnostic report 2.7.0.
- The user explicitly approved bounded visible checks. The canonical Studio
  smoke passed with the staged executable: metadata, packaged imports, synthetic
  online states and fitting layouts. The same staged updater passed standalone
  repair and repair-after-failure screens with network and installer execution
  disabled. These checks did not rebuild either executable.
- Draft release `434106478` contained exactly the four expected assets. Their
  names, sizes, SHA-256 digests, uploaded states, exact notes, annotated source
  tag and repository immutability setting were checked again before publication.
- [v2.7.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.7.0)
  was published at `2026-11-04T15:39:58Z` as latest, stable and immutable.
  Independent unauthenticated public downloads match every local size/hash;
  GitHub release and all four asset attestations verify. All eight live
  production updater metadata checks passed, including older/current versions,
  explicit repair and downgrade rejection, without executing an installer.

## Source CI and external acceptance

[Exact-source CI 41856162340](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41856162340)
passed Windows contracts and native Intel Mac source/adapter and export checks.
The initial Apple Silicon job ran zero steps: GitHub cancelled it after failing
to allocate a hosted runner, with explicit macOS arm64 capacity annotations.
Only that job and its dependents were retried. At publication/recording, the
retry remains queued; Apple Silicon and the dependent cross-platform return
checks are pending, not passed. Documentation CI passed separately.

All documented Windows publication gates passed. Complete Mac CI is a preferred
precedent rather than a mandatory Windows publication dependency; this external
runner limitation is recorded without changing the workflow or its assertions.
Private evidence, annotations and checkpoints are retained under
`build/release-2.7.0-evidence/`.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.7.0.exe` | 299,004,859 | `9598cb520b9b2fa449079f9c4abfe971cf62d8fc6df55edc655216e5ddfc91e1` |
| `FPVS-Studio-Setup-2.7.0.exe.sha256` | 95 | `2bac400943ed7a0cded627c8e2d5385e74742a45524fd94933b5a672a3703425` |
| `FPVS-Studio-Update-2.7.0.json` | 107 | `6028702dd7c504363cdd4fc2c4fe76a6d9e567e684d17aaecaedef5c3b999186` |
| `FPVS-Studio-Update-2.7.0.json.sha256` | 97 | `91cfd1c46f88dbd5c543275464859d379a2e0fa2dcc471efbff52fb699785554` |

## Limits

Production install/upgrade/uninstall, real participant sessions, EEG activity and
physical display timing are separate acceptance tasks. This workflow does not
claim those checks or modify the working application installation.
