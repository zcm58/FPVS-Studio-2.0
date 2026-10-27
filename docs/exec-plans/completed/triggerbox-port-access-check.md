# TriggerBox serial-port access checks

Status: Completed

Date: 2026-10-27

## Authorized workflow

The user approved broadening TriggerBox name matching and checking recognized
candidate ports when Detect is pressed. Initial discovery on opening Recording Setup
remains metadata-only. No marker test, probe bytes, or automatic scan of unrelated
ports is part of this change. Marker receipt will be tested manually by the user.
Implement, verify, commit and push this work before investigating BioSemi detection.

## Scope and boundaries

- Accept both `VirtualSerial` and `Virtual Serial` driver-name spellings.
- Extend trigger-owned discovery with an opt-in access check and immutable per-port
  results. Open at 2,000,000 baud / 8N1, with flow control disabled; close every
  constructed connection, including failed/cancelled operations. Never issue probe
  reads, marker writes or explicit reset/flush calls, and never reuse the marker
  backend's `connect()`. Standard pySerial open/close initialization still applies.
- Check cancellation between candidates. Port opening stays on the existing app-owned
  worker; closing/dismissing the dialog ignores late results.
- Preserve manual/custom selections and multiple-candidate choice. An access failure
  keeps the candidate visible and reports its error without claiming it is a wrong
  device. Successful opening establishes access only, not identity or EEG receipt.
- Keep persisted recording settings, runtime launch checks and marker timing intact.

## GUI acceptance

The user's task is to choose a usable TriggerBox COM port. Detect is the primary
action for refreshing candidates and checking access. Reuse the existing editable
port list and wrapped status label at the `700x640` minimum/default size. Cover
initial metadata, checking, accessible, unavailable, multiple, empty, enumeration
error, manual edits, cancellation and late completion. Keep per-port errors and full
driver descriptions accessible without overflowing the dialog.

## Verification

- Baseline: triggers focused 126 passed; GUI focused 83 passed.
- Add fake-only serial tests proving automatic discovery never opens ports and the
  explicit check never reads/writes, closes ports on failure/cancel and retains errors.
- Update registered `tests/gui/test_recording_setup.py` coverage for explicit-only
  opening, access outcomes, retained edits, cancellation and minimum-size states.
- Run triggers, GUI and docs focused checks, followed by repo precommit.
- Qt and physical hardware checks remain manual/unrun unless separately approved.
  Visible manual smoke: at `700x640` in both themes, open TriggerBox Setup, press
  Detect, inspect one/multiple/failed candidate access results, edit a port while a
  job runs, then Cancel/reopen and Apply. Do not send marker bytes.

## Progress

- [x] Confirm approved scope and run focused baselines.
- [x] Implement neutral discovery/access results and regression tests (42 fake-only tests pass).
- [x] Integrate explicit Detect checks and registered GUI coverage, including retry
  invalidation, retained edits, failure/cancel outcomes and `700x640` theme coverage.
- [x] Update canonical workflow and agent guidance.
- [x] Complete verification and archive the implementation plan.

## Result

The implementation retains plain editable COM values, displays selected-candidate
access results, and retains full per-port descriptions/errors in tooltips and accessible
descriptions. Starting a retry clears previous access annotations. No marker test was
added, and all automated serial operations use fakes.

Triggers focused passes 139 tests; GUI focused passes 83; docs focused passes ten.
Ruff, compilation, mypy (243 source modules), repository audits and independent review
pass. Repo precommit finishes with 3,584 passed, 12 Windows symlink-permission skips
and two existing Windows filesystem failures: bundle import's final directory rename
and an exact retry-count assertion in serialization. The bundle module passes all 81
tests on rerun; isolated serialization passes all ten. The combined rerun first had
90 passes and a serialization assertion observing four retries rather than three.
These filesystem paths were not changed by this feature.

Registered Qt tests and physical port/marker checks were not run. The visible/manual
acceptance path above remains for an approved session; marker receipt is deliberately
left to the user's manual testing. Source implementation is complete and is committed
and pushed with this plan.

Follow-up outside this implementation plan: after the source commit is pushed,
investigate BioSemi COM-port detection without changing it and report the findings
to the user. This investigation does not add a marker test.
