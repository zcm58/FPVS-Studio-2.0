# TriggerBox USB edge cases

Status: Completed

Source fixes and documentation are complete. Further TriggerBox testing and the
remaining full-suite run were explicitly deferred by the user on 2026-11-05.

## Scope and assumptions

Audit the USB TriggerBox rev.02/Plus workflow for actiCHamp against current Brain
Products documentation. Parallel-port changes are outside this pass. Port metadata,
OS access, submitted bytes and EEG marker receipt remain distinct evidence.

## Work and verification

1. Pull remote master and run the existing trigger checks as a baseline.
2. Correct confirmed discovery/cleanup failures with fake-transport regressions;
   review runtime preflight and durable failure evidence.
3. Qualify Recording Setup's discovery/access wording and preserve manual selection.
   Extend its registered 700x640, both-theme status/geometry coverage. Keep errors in
   plain language, including the shared popup classifier; preserve technical details.
4. Run trigger/GUI/runtime focused checks and repo non-Qt precommit. Physical USB,
   Recorder marker receipt and timing, and visible Qt checks remain separate.

## Progress

- Fast-forwarded master from `5ad86a2` to `1ebcbe5` (v2.7.0); existing untracked files
  preserved. Trigger baseline: 252 tests passed.
- Vendor sampling/pulse table and 2,000,000-baud settings agree with implementation.
- Fixed cancellation during lazy discovery, secondary close-error retention and
  metadata-only device claims. USB backend errors now lead with plain next steps.
- Runtime regression coverage checks USB open/send/cleanup/presentation/export
  failures without using real ports. Shared popup classification retains TriggerBox
  guidance ahead of generic file/network errors, including serialized launch messages.
- Added Recorder 1/2 operating guidance. The requested vendor MSI was inspected:
  version 2.0.3, valid Brain Products signature, per-machine driver/device installation;
  no supported non-admin installation was identified and no installer was launched.

## Verification and limits

- Trigger focused: 254 passed. Safe GUI focused: 164 passed. Error explanation
  unit tests: 49 passed. Docs focused: 13 passed. Changed-file Ruff/compilation passed.
- Runtime focused: 1031 passed, 4 Windows symlink-privilege skips, one Windows
  long-path test-read failure. Its 263-character checkpoint existed and was readable
  with an extended path; the exact test passed with a short temporary path.
- Ordinary precommit stopped on pre-existing user-owned untracked scripts' lint
  errors. A temporary clean checkout received byte-identical changes; changed-file
  lint/compilation, Windows and Darwin mypy, invariant and documentation audits passed.
  Its full non-Qt suite was interrupted at the user's request; no full-suite pass
  is claimed. The original untracked files were preserved.
- Automatic approval review blocked removal of the temporary verification checkout
  and test directories. They were retained; source changes remain in the main workspace.
- Registered Qt coverage was extended for Recording Setup at 700x640 in both themes
  and the error popup at its 580-pixel minimum width. Qt was not run. Visible manual
  checks: metadata-only/access/error/cancel states, long COM names and popup Show
  Details; verify wrapping and usable controls. No real port or Recorder was tested.
- Hardware acceptance remains separate: a saved short normal recording must verify
  repeated/distinct marker codes, zero resets and actual display/EEG timing.

## Changed files

- `src/fpvs_studio/triggers/brainproducts_backend.py`,
  `src/fpvs_studio/triggers/brainproducts_discovery.py`
- `src/fpvs_studio/gui/recording_dialog.py`,
  `src/fpvs_studio/support/error_explanations.py`
- `tests/unit/test_brainproducts_trigger_backend.py`,
  `tests/unit/test_brainproducts_discovery.py`, `tests/unit/test_runtime_recording.py`,
  `tests/unit/test_error_explanations.py`
- `tests/gui/test_recording_setup.py`, `tests/gui/test_error_dialogs.py`
- `docs/RUNTIME_EXECUTION.md`, `docs/GUI_WORKFLOW.md`, `docs/BUG_REPORTING.md`,
  `docs/PLANS.md`, and this record
