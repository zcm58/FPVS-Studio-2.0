# Graphics crash repair and interrupted-condition recovery

Status: Active

Date: 2026-10-24

## Authorized outcome

Fix the native crash observed between conditions, identify the incomplete condition
after an interrupted session, and commit, push and publish a new Windows release.
Work is isolated from unrelated edits in the primary checkout.

## Evidence and assumptions

The October 22 Cognitive Decline execution completed five runs and entered run six
(Emotional Processing) before process termination. Its native log repeatedly records
GUI-thread garbage collection deleting pyglet textures while the presentation worker
creates text screens. Windows records a fatal native exit; no retained dump establishes
every step of the final failure. Fix the demonstrated resource-lifetime defect without
changing stimulus timing, scoring, marker order or compiled scientific contracts.

Automatic email intake is independently inactive in the deployed feedback service.
Local interrupted-condition guidance must work offline and without registration.
This release does not claim to activate that separate service.

## Workflow and ownership

- Engine owns graphics resources, text reuse and graphics-thread cleanup across
  presentation, transition, feedback, cancellation and exceptions.
- Runtime owns durable project-local progress and a read-only interruption query.
  Distinguish completed playback, unfinished activities and not-started occurrences;
  retain condition names and occurrence order even when conditions repeat.
- GUI queries on a background worker when opening a project and after a failed run.
  It presents actionable recovery information and preserves existing research outputs.
- A targeted rerun must execute only the selected occurrence as a new visit, using
  existing validation/recording safeguards, never overwriting the interrupted visit.
  Older records without a saved plan offer an explicitly confirmed current-setup
  replacement with a fresh schedule, only when the condition still exists.
- Packaging uses the clean committed source and authenticated published baseline.

## Acceptance

- Fake graphics tests cover bounded text allocations, thread ownership, cleanup on
  normal/error paths and restoration of process state.
- Temporary-project tests cover full and compact exports, repeated conditions,
  interruption before/during/after playback, finalized sessions, malformed or missing
  evidence and legacy acquisition receipts.
- Registered GUI coverage uses fake runtime/network services and checks recovery
  messages, launch guards, cancellation and long names at minimum/default size.
- Run engine/runtime/gui/packaging/docs focused checks and repository precommit.
  Local Qt/native presentation requires explicit approval for a safe visible session;
  no offscreen execution or real participant data is used for acceptance.
- Build and verify full installer, applicable patch and release metadata; publish
  the exact tested commit. Record any unperformed platform acceptance honestly.

## Progress

- [x] Preserve crash evidence and isolate clean worktree at `72aecb8`.
- [x] Confirm latest published baseline `v2.4.6` and safe GUI baseline (17 tests).
- [x] Implement graphics lifetime repair and regression checks.
- [x] Implement local recovery query, targeted rerun and GUI coverage.
- [ ] Complete verification and release artifact checks.
- [ ] Commit, push and publish the release.

## Verification record

- Engine focused: 386 passing tests; no change to compiled timing or trigger order.
- Runtime focused before review follow-up: 639 passing tests, three Windows symlink skips.
- GUI safe focused: 17 passing tests; new registered visible tests are prepared.
- Packaging focused: 181 passing tests; authenticated 2.4.6 baseline inventory verified.
- Initial repo precommit: 3,169 passing tests, 12 Windows symlink skips, with Ruff,
  compilation, mypy and repo audits passing. Review follow-ups receive focused checks
  and a final precommit run before publication.
- The actual Cognitive Decline receipt was queried read-only: run six, Emotional
  Processing, five completed and two not started; the receipt hash was unchanged.
- Independent review covered late project-close callbacks, seed readiness, malformed
  checkpoint coherence and the no-disk-I/O boundary after timed pre-condition fixation.
  Final recovery/launcher/task follow-up: 144 passing tests, one Windows symlink skip;
  full-source mypy passes all 240 modules. Native scene interruption is deliberately
  labeled "armed" because writes cannot observe frame zero without disturbing timing.
- Visible Qt and native graphics acceptance requested in this task; not executed
  without the user's explicit approval. No offscreen tests or real EEG markers.
