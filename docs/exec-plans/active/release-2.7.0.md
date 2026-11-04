# Studio 2.7.0 release

Status: Active

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
- Stage without GUI execution. The required bounded Studio/updater visible
  checks await explicit safe-visible approval; test the existing staged bytes.
- Commit/push the exact build source, bind annotated `v2.7.0` to it and check
  source CI. Create a draft, upload all four assets and compare every size and
  SHA-256 before publishing latest/stable with repository immutability enabled.
- Independently verify public downloaded bytes, release/asset attestations and
  production updater selection without executing an installer.

## Progress

- Repository was clean and synchronized at `19ccc9b` when release work began.
- Latest stable `v2.6.1` is immutable; repository future-release immutability is
  enabled. Packaging focused passed 192 checks before the version change.
- Safe-visible approval requested while independent staging proceeds.

## Limits

Production install/upgrade/uninstall, real participant sessions, EEG activity and
physical display timing are separate acceptance tasks. This workflow does not
claim those checks or modify the working application installation.
