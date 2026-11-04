# Studio 2.6.1 release

Status: Completed

Date: 2026-11-03

## Authorization and source

The user explicitly requested committing the reporting repair, merging recent remote
Mac bug fixes, resolving conflicts, bumping the version and publishing a new GitHub
release. Preserve all existing published bytes and retained output.

Reporting repair commit `12c68db` was merged with remote `3f0cf9a` through merge
commit `dec8a9b`. The only conflict was the completed-plan list in `docs/PLANS.md`;
both reporting and Mac records are retained. The six remote commits include bounded
refresh probes, nonexclusive Test/Pilot display and callback recovery, Retina backing
pixels and explicit target-resolution confirmation, keyboard event dispatch and
Test/Pilot recovery exclusion, including the Windows lifetime-lock test fix.

The latest published stable release was verified as `v2.6.0`. These are bug fixes,
so the canonical package version becomes 2.6.1 under Packaging's patch-version rule.
The public release is a full Windows installer plus update JSON and their checksum
sidecars, matching the preceding release. Mac remains source-only.

## Build and publication

- Use isolated label `release-2.6.1`; preserve earlier bundles and installers.
- Retain private build/verification evidence under `build/release-2.6.1-evidence/`.
- Refresh only editable app metadata, preserve the qualified dependencies and compare
  native inputs/payload with authenticated 2.6.0 evidence. Keep unrelated PATH entries
  out of PyInstaller collection.
- Run packaging focused and complete safe precommit checks after the merge/version
  change. Native Mac CI and cross-OS handoff evidence remain distinct from Windows
  tests and physical acceptance.
- Build the app and independent updater with canonical scripts, verify frozen code,
  metadata, inventories, native libraries and required resources. A bounded packaged
  GUI/import smoke requires the approved visible environment specified in AGENTS.md
  and `scripts/smoke_packaged_app.ps1`; track that gate explicitly.
- Commit/push exact build source and bind a new annotated `v2.6.1` tag to it. Stage a
  draft, upload all four assets and verify complete inventory, size and SHA-256 before
  publishing latest/stable. Preserve immutable-release settings and older assets.
- Verify public downloaded bytes, GitHub release/asset attestations and production
  updater selection, without installing over the working application.

## Progress

- Exact build source is `1cceee5a16b6b8f5583405c1e2c651a2b474a2df`, committed and
  pushed to master. Annotated `v2.6.1` resolves to this source. The merge retains all
  six remote fixes and the reporting repair; the documentation conflict preserves
  both sets of plan entries.
- Merged-source precommit passed Ruff, compilation, repository audits, mypy for
  267 source files and the additional nine-file Darwin target, and all 5,137 safe
  tests. The 32 skips are Windows symlink/native POSIX and PsychoPy-version cases.
  Packaging focused passed 189 checks; dependency consistency passed.
- Canonical staging build completed under `release-2.6.1`, with `-SkipInstall`
  after refreshing editable metadata and `-SkipSmoke` before visible approval.
  The exact staged executables subsequently passed the approved smoke checks
  below. No application installer has been executed.
- Authenticated 2.6.0 installer bytes and its qualified complete 7,062-file bundle
  were checked. All 555 native input paths/hashes and 482 target DLL/PYD files
  match, as do the 22 normalized warnings. Only editable app metadata changed
  among installed distributions. No runtime dependency updates were introduced.
- Static target audit passed: all 7,062 owned files match inventory SHA-256
  `8a48b95bc3294411f1543d2cdcf793d8226fe72fc5f0038360ff9e72de5e711b`;
  all 267 Studio modules plus entry and all 22 updater modules plus entry match
  exact source code objects. Studio/updater metadata and the GUI-free updater
  diagnostic report 2.6.1. Full-only update JSON and both checksum sidecars validate.
- GitHub release `433297229` was published at `2026-11-04T02:45:57Z`
  (2026-11-03 in America/Chicago) as
  [v2.6.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.6.1), latest,
  stable and immutable. All four assets and exact 178-character notes were checked
  before publication. The annotated tag retains the exact build source above;
  subsequent release-record commits change documentation only.
- [Source CI 41731234561](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41731234561)
  targets exact build source and completed successfully. Windows contracts, both
  native Mac CPUs, the Windows return check and both final Mac-origin round-trip
  jobs passed. Documentation CI passed separately. The complete observed job
  result is retained in `source-ci-checkpoint.json` under the evidence directory.
- The user explicitly approved the bounded visible Windows smoke checks. The
  canonical Studio runner passed against the exact staged executable, including
  frozen metadata/version 2.6.1, packaged imports, synthetic online states and
  layout checks. The existing updater's visible `--gui-smoke` passed standalone
  repair and repair-after-failure states with network and installer execution
  disabled. Neither payload was rebuilt to run these checks.
- Independent unauthenticated public downloads match all four local asset sizes
  and SHA-256 digests. GitHub release and individual asset attestations passed;
  the locked annotated tag, immutable/latest/stable state and exact source were
  independently verified. Results are retained in `public-download-audit.json`.
- All eight live production updater metadata checks passed with authenticated
  full-only update JSON: older/previous versions select the full installer,
  current-version checks offer no update, explicit repair selects the installer,
  and a newer installed version rejects downgrade. These checks neither read the
  installed application nor execute/download an installer; the separate public
  byte audit downloads assets without executing them.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.6.1.exe` | 298,968,689 | `9a6482669d75a798172675199ef79411366716b908091979fdfb2d5a31156b86` |
| `FPVS-Studio-Setup-2.6.1.exe.sha256` | 95 | `32fc40d0c98d011c9b8a154750bf2d3af52bccd381366b77131c350e1dd17db3` |
| `FPVS-Studio-Update-2.6.1.json` | 107 | `cc648a9f7639d6caf2b178ab2b69b2263431d46db91a234a5d10afad026c1ee5` |
| `FPVS-Studio-Update-2.6.1.json.sha256` | 97 | `2f8813d0e0775073e850d0cf274150b7a37b138bc41f32ceaff7734cdaaecec3` |

No production installation, real participant session, EEG marker activity or physical
Mac acceptance was performed by the release smoke workflow. Physical display timing,
hardware and broader installed-upgrade acceptance remain separate from these checks;
the existing active Mac acceptance plan retains its limits.
