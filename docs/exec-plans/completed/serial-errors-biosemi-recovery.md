# Serial failure audit and BioSemi recovery guidance

Status: Completed

## Requested outcome and boundaries

Run a final adversarial pass through serial failures, repair demonstrated gaps,
extend specific actionable errors to BioSemi ActiveTwo/ActiveThree, and commit/push.
Preserve protocols, explicit port selection, diagnostics, and Test/Pilot behavior.
Do not open actual ports, install vendor software, evict other processes or claim
physical marker/timing qualification. Prior visible Windows Qt approval persists.
This follow-up requests source changes and push, not another installer release.

## Verification plan

1. Replay native/serialized access failures, missing ports, invalid settings,
   disconnects, timeouts, incomplete writes and close/cancellation failures using
   injected boundaries. Reproduce before patching; report areas with no new defect.
2. Reuse one neutral serial failure classifier; keep vendor-specific recovery
   accurate. Distinguish BioSemi USB Trigger Interface from its EEG USB Receiver
   and ActiView. Preserve the raw error and operation in diagnostic details.
3. Verify shared setup/launch messages, no false success/fallback, and interrupted
   recording evidence. Cover both BioSemi selections and minimum/default GUI sizes.
4. Run focused checks, approved visible fake-hardware checks and repository precommit.
   Document limits, archive this plan, and commit/push only task-owned files.

## Reproduced gaps and repairs

- BioSemi mapped every open error to a missing-port message and popup handling
  replaced write/reset failures with generic connection advice. Shared vendor
  recovery now distinguishes access denial, missing ports, settings, USB I/O,
  timeouts, missing Studio support and marker/close failures, preserving diagnostics.
- Shared access checks lost serialized permission and configuration context, and
  cancellation could discard a failed-close diagnostic. Native and serialized
  classifiers now agree; actual close failures are logged before cancellation.
- Real pySerial with intercepted Windows calls reproduced pending BioSemi writes
  being overwritten, delayed write errors being lost and close cancelling the last
  marker without reporting failure. BioSemi now reuses the existing native ownership
  helper, rejects overlapping writes, drains outside playback and preserves failures.
- The final marker could fail after playback returned success and before close.
  The condition boundary now observes completion before post-tasks and feedback,
  without sending reset bytes. Deferred errors discovered on the next send or in
  abort cleanup correct the original marker evidence, including repeated codes.
- Per-run JSON/CSV checkpoints could still contain the pre-cleanup marker status.
  They now refresh through existing writers after a late failure, even when the task
  journal is locked/malformed. A failed refresh remains in acquisition evidence and
  does not replace the original experiment error or erase prior results.
- A damaged/shadowed Studio serial component was misdiagnosed as a USB problem;
  worker startup rejection was also misdiagnosed before any port call. Both paths
  now name the actual software failure. Completion-error subclasses retain BioSemi
  advice through wrapped errors rather than becoming file-permission guidance.
- No additional defect was found in TriggerBox's native completion helper. Its
  existing pending-write/cancellation protection remains unchanged.
- Trigger baseline: 316 passed. User-owned untracked files and previous release
  artifacts are preserved.

## Acceptance

- BioSemi recovery and launch checks: 46 passed.
- Shared serial/access and TriggerBox adversarial checks: 202 passed.
- Final trigger-focused route: 399 passed; backend/native cases: 63 passed;
  shared serial access cases: 79 passed.
- BioSemi support explanations: 229 passed; safe GUI scope: 178 passed.
- Approved visible Windows checks: 87 passed, including both BioSemi selections,
  light/dark themes, minimum/default dialog sizes and realistic error states.
  Follow-up checks passed 8 worker-start cases and 7 TriggerBox dependency/recovery
  cases (including 3 existing recovery controls).
- Runtime focused route passed 1069 with 4 Windows symlink-permission skips before
  the final cleanup/export edits. Later final-source targeted verification covers
  native cleanup and 6 JSON/CSV refresh cases, including permission/malformed-journal
  failures: 237 recording/durability tests passed with 1 Windows symlink-permission
  skip.
- The first completed precommit had 5697 passes and two failures: an older playback
  test assumed silent close after a marker failure, and an unchanged serialization
  test encountered a fourth Windows replacement attempt instead of its expected
  three. The playback test now asserts persistent error identity plus port/engine
  cleanup (84 related tests passed). Serialization passed all 10 tests unchanged
  on recheck; the clean full rerun also passed it without changing serialization.
- Final repository precommit passed: 5699 tests, 32 environment/platform skips and
  24 subtests. Changed-file Ruff/compilation, Windows mypy (274 source files), macOS
  adapter mypy (9 files), repository audits and docs hygiene passed. The final
  source/config/test snapshot was hash checked before commit.
- Source snapshot: `C:\Users\zcm58\fsbio`, copied only task-owned files and hash
  checked against the primary worktree. The earlier precommit run was deliberately
  stopped after the final export fix so acceptance uses the final source.

Local receipts are retained in `build/serial-biosemi-precommit.log`,
`build/serial-biosemi-precommit-snapshot.json`, the focused test logs and visible
GUI check logs. This follow-up changes source only; no new installer was built.

Path audit: reviewed `RuntimeWorker.execute` and `execute_session` entry points and
their existing run/checkpoint writers. Output remains beneath the launch's validated
project/output root, with no new path inputs or persisted formats. Temporary test
projects cover permission failures and repeated checkpoint writes; there are no new
file dialogs or Cancel semantics. User directories and earlier run outputs were not
used by tests.

All native calls and serial devices were intercepted/faked. No physical driver,
hardware, EEG receipt, ActiView configuration or electrical timing has been tested.
Vendor guidance is linked from the runtime contract; successful port access or
Windows write completion is not proof that EEG acquisition received a marker.
