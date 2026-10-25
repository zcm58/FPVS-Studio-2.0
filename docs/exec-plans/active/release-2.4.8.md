# Studio 2.4.8 minor bug fixes release

Status: Active

Date: 2026-10-25

## Authorized outcome

Commit, push and publish version 2.4.8 with the exact GitHub release title
`minor bug fixes`. Build a full Windows installer and direct 2.4.7 patch from the
isolated crash-recovery worktree, preserving the primary checkout's unrelated
edits and the installed 2.4.7 application.

## Scope and source

Runtime fixes are committed and pushed as
`1d27c33833e53a1808a7cd8194b439f0af963859`. They cover reusable task graphics and
cleanup, finite numeric input, restoration after task-input setup failures,
durable completed results during later failures, interrupted-condition recovery,
and deferred-launch/persistent-worker lifecycle races. The
[runtime reliability audit](../completed/runtime-reliability-audit.md) records
the implementation and source verification.

Only package version and release documentation change during this release task.
There are no new scientific methods, runtime formats or architecture boundaries.
No architecture update is needed.

## Verification and publication plan

- Packaging focused baseline: 181 tests passed.
- Refresh only editable application metadata; retain authenticated dependency
  versions, native inputs and the Windows threadpoolctl exclusion.
- Authenticate the published 2.4.7 baseline and build isolated 2.4.8 artifacts.
- Verify extracted full payload, exact patch reconstruction, frozen source,
  dependency/native parity and the GUI-free updater packaging diagnostic.
- Verify candidate updater selection, exact draft tag/title/notes/assets, then
  publish and verify public downloads, updater selection and signed attestations.
- Record asset sizes, hashes and source identity here after publication.

The source audit's broad precommit had 3,276 passes, 20 passing subtests, 12
Windows symlink-permission skips and two intermittent Windows directory-rename
failures. Both exact failed cases passed unchanged on immediate rerun. See the
runtime audit record for commands and evidence; this is not an all-green full run.

## Acceptance boundaries

Visible Qt/native graphics, physical display/EEG timing, clean-machine installation
and destructive installer lifecycle checks remain unperformed. Artifact checks do
not establish those results. No installer will be executed on the working machine
for this release task. Automatic crash-email service activation is separate and
remains pending; the release does not deploy the feedback service.
