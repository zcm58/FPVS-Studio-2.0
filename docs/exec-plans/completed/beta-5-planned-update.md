# Beta 5 Planned Update

Status: Completed

## Summary

Beta 5 is a reliability and UX polish release after `0.9.1b4`. The work removed
confusing setup controls, fixed project-open state behavior, improved update-dialog
clarity, and aligned user-facing docs with the current installer/update workflow.

## Key Changes

- Removed random-order-seed editing from the normal setup UX.
- Kept the realized random order seed as reproducibility metadata in Run/logs/results.
- Updated setup/review wording to say condition order is randomized automatically.
- Fixed dirty-on-open behavior so opening a project does not mark it modified unless the
  user actually edits something.
- Improved the update dialog with clearer current/latest version text, concise release
  notes, full release-notes link, and this-launch-only `Remind Me Later` behavior.
- Show clear manual update-check errors when GitHub cannot be reached while keeping
  startup update-check failures silent.
- Updated README, packaging, and workflow docs so GitHub Releases updates and preserved
  user data are described accurately.

## Verification

- GUI tests confirm setup/session UX no longer exposes editable random-order-seed
  controls.
- GUI tests confirm setup review describes randomized condition order without showing a
  saved seed as a user-managed setting.
- GUI tests confirm opening an existing project does not mark the document dirty.
- Existing launch/session tests continue to verify unused seed generation, completed-seed
  avoidance, and logged/compiled seed metadata.
- Update-dialog tests cover current/latest version text, release notes display, full
  release-notes link, this-launch-only remind-later behavior, and manual server-error
  messaging.
- Startup update tests continue to verify no-update and server-error paths stay silent.
- `.\scripts\check_quality.ps1` passed after implementation.

## Assumptions

- Beta 5 remains a polish/reliability release, not a schema or runtime-contract release.
- No advanced manual seed override was added in beta 5.
- `Remind Me Later` only suppresses the update prompt until the app restarts.
- Manual update checks show clear errors; startup update failures remain silent.
