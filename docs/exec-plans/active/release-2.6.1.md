# Studio 2.6.1 release

Status: Active

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

- Reporting changes committed; all six remote fixes merged, one documentation conflict
  resolved without dropping entries. Version/notes and qualification are in progress.
- Earlier reporting precommit passed 5,039 tests and 31 platform-specific skips;
  this does not replace verification of the merged release source.

No production installation, real participant session, EEG marker activity or physical
Mac acceptance is authorized by the release smoke workflow. Preserve the existing
Mac acceptance limits and report skipped checks accurately.
