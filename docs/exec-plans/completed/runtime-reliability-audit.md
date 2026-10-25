# Runtime reliability audit

Status: Complete

Date: 2026-10-25

## Authorized outcome

Audit FPVS Studio after 2.4.7 for concrete runtime bugs, fix reproducible defects,
verify, commit and push. Use the existing clean isolated worktree and preserve the
unrelated edits in the primary checkout. Publishing or installing another release
is not part of this request.

## Scope and constraints

- Review presentation resource lifetime, task/condition transitions and exceptions.
- Review session launch, result durability, interruption recovery and cancellation.
- Review GUI worker completion, stale callbacks, launch guards and shutdown.
- Review recording preflight and trigger cleanup using fake hardware only.
- Preserve timing, randomization, scoring, marker order and persisted output formats.
- Make narrow fixes backed by a reproducer or regression test; avoid speculative
  refactors and changes to unrelated services or user research files.
- Run safe focused routes before targeted inspection and a final repo precommit gate.
  Registered Qt tests require a separately approved visible environment; no offscreen
  Qt, native presentation or real EEG acquisition is part of the default audit.

## Progress

- [x] Confirm clean source matches remote master and preserve primary-checkout edits.
- [x] Run focused baselines and inspect independent runtime areas.
- [x] Reproduce and fix confirmed defects with focused regression coverage.
- [x] Review the combined diff and complete verification, documenting remaining limits.
- [x] Prepare the verified changes and summary for commit and push.

## Findings and verification

Confirmed defects repaired:

- Task screens used PsychoPy's `clearTextures()` directly, leaving its lowercase
  pixel-buffer ID allocated. Partial item construction and a cleanup exception also
  left later items unreleased. Synthetic resource-ID tests reproduce each exit path.
  Textbox focus/editability and mouse/background restoration now also cover
  failures during input setup, not only failures inside the frame loop.
- Task-screen text and controls were constructed on every frame. Installed Pyglet
  defers buffer deletion until context activation, which does not occur inside the
  task loop. A 120-frame synthetic heading/body/footer screen accumulated 360 text
  objects and queued buffers. Per-screen reuse bounds these resources without adding
  context drains to timed presentation.
- Numeric task responses accepted `nan`; the result validator or stepped-number
  arithmetic then failed the session instead of letting the participant correct it.
- A feedback, completion-screen or engine-close error after single-condition playback
  bypassed writing the already completed result.
- A trigger-output failure was treated as user cancellation for recovery bookkeeping,
  removing the saved plan needed to rerun the incomplete condition.
- Failure of the final TriggerBox reset replaced a returned complete playback result
  with a reconstructed partial result, dropping frame/response evidence.
- Deferred launch callbacks could outlive their project window and start playback
  after close or project handoff. Participant confirmation and recovery discovery
  also needed shutdown guards while completion handlers drained existing workers.
- Overlapping jobs on the shared presentation worker subscribed to untagged results
  and completion signals, so one job could consume another's result and disconnect
  before its own work finished.

Safe baselines: engines 389 passed; runtime 667 passed / 3 Windows symlink skips;
triggers 97 passed; GUI scope 17 passed. Recording/preflight/trigger adapters were
reviewed with no additional confirmed adapter defect. No real acquisition, Qt event
loop or native presentation was run.

The final engine route passed 422 tests; runtime passed 683 tests with 3 Windows
symlink skips; the safe GUI route passed 48 tests. Existing acquisition receipt states
remain compatible: a handled trigger abort still produces an aborted receipt, while the independent local
condition-recovery record retains the interrupted plan. Runtime failure tests also
verify that secondary cleanup, export and recovery-write errors do not hide the
original trigger failure.

Static task regression: 120 frames use 3 text stimuli instead of 360. Changing numeric
input uses 2 text stimuli across 102 frames instead of 204; a 101-frame text task uses
one submit rectangle instead of 101. Synthetic tests verify draw content, selection
visibility, correction and cleanup, rather than treating these counts as physical
display or native-memory qualification.

Independent reviews covered worker request routing and cancellation, completed-result
retention, original-error precedence, input-state restoration, graphics ownership and
the native-scene boundary. No new queue drain, synchronization barrier, clock reset,
stimulus flip or I/O operation was added to the timed frame loop. Physical timing and
fixation-to-frame-zero latency still require native acceptance; synthetic frame counts
do not establish those measurements.

## Final repository verification

`./scripts/verify.ps1 -Scope repo -Tier precommit` passed changed-file Ruff and
compilation, mypy across 240 source files, harness audits and documentation hygiene.
Its safe suite completed with **3,276 passed, 2 failed, 12 skipped and 20 subtests
passed**. The two failures were Windows `PermissionError [WinError 5]` at the unchanged
bundle-import directory rename:

- `tests/unit/test_library_origin.py::test_explicit_newer_library_import_preserves_the_previous_project`
- `tests/unit/test_project_bundle.py::test_bundle_transfer_without_windows_long_path_policy[False]`

Both exact cases passed unchanged on immediate rerun: **2 passed in 0.56s**. The earlier
[behavior-preserving cleanup audit](behavior-preserving-cleanup.md) reproduced the same
intermittent rename failure against baseline source. The locking process remains
unknown; no speculative retry or fallback was added. The full precommit invocation
therefore completed but was not fully passing. All 12 skips require Windows symlink
privileges unavailable to this account.

Final evidence is retained under ignored `build/`: `runtime-audit-precommit-verified.log`
and `runtime-audit-bundle-recheck.log`. Two earlier broad runs were deliberately stopped
while final regression review was still making changes; they are not verification
results. The final run used the frozen source and tests.

This audit changes source only. Version 2.4.7, its published assets and the installation
on this machine remain unchanged.

## Visible acceptance path

Not executed locally; requires an approved visible environment. Use synthetic
callbacks, participant data and Test/Pilot marker output for these checks:

1. At the existing Home/default window size, hold initial seed preparation, queue
   Launch, then close or switch projects. Releasing the preparation must not open an
   old-window participant prompt or start playback. Normal active-window launch must
   still proceed.
2. Hold participant-history lookup, then begin application shutdown. Releasing the
   lookup must clean up without another confirmation, recovery query or launch.
3. Queue two fake presentation jobs, covering success and failure in each order. Each
   progress dialog and receiver must finish only for its own job. Destroy a queued
   requester and start shutdown while another job runs; retain the running owner
   thread and suppress new work/outcomes for retired requesters.
4. On synthetic task screens, hold a long static page, then exercise image choices,
   changing text, numeric correction, validation and abort. Confirm unchanged geometry,
   visible labels, response capture and memory behavior. No layout or copy redesign is
   part of this change.
5. Inject a late feedback/cleanup failure and a trigger reset failure in a synthetic
   session. Inspect saved frames/responses and the exact interrupted occurrence; a
   rerun must preserve completed prior outputs.

Existing engine/runtime/GUI documents describe the repaired contracts. No package
ownership, scientific method, persisted schema or public engine interface changes
require an architecture-map update.
