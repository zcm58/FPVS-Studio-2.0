# BioSemi project serial-port selector

Status: Completed

Date: 2026-10-27

## Approved outcome

Settings > Recording > Recording Setup exposes an editable BioSemi serial-port
selector for ActiveTwo and ActiveThree. Keep COM3 as the unset default, preserve
explicit project ports and baudrates, and save the accepted port atomically with
the recording choice. Cancel and failed saves preserve prior saved state and drafts.

## Boundaries

- `settings.triggers.serial_port` remains canonical; no new project schema or
  computer-default COM field. Computer-default setup hides project-only controls.
- Enumerate metadata on an app-owned worker and retain the selected/manual port.
  Generic serial metadata must never identify a port as BioSemi automatically.
- Check Port opens/closes only the selected port using the configured baudrate
  (normally 115200), 8N1, no flow control, RTS/DTR requested low. Send no marker,
  read no bytes and call no explicit reset/flush. Opening can still affect control
  lines through the OS/driver. Availability does not prove identity or EEG receipt.
- Reuse the serial-access implementation for TriggerBox while preserving its
  recognized-candidate restriction and 2,000,000-baud behavior.
- Keep all hardware work outside widgets and off the GUI thread. Cancel checks
  on dismissal and ignore stale results after edits, device changes or reopening.

## UI and verification

Retain Recording Setup's 700x640 minimum/default size. The primary action remains
Apply. Exercise empty/listed/manual, invalid, busy, available, unavailable and
enumeration-error states in both themes, with actionable status and full error
details in tooltips. Available ports never replace the current selection.

- [x] Fake-only backend enumeration/access/cancellation/cleanup coverage.
- [x] Atomic project persistence preserving other trigger settings and drafts.
- [x] Registered Qt selector, Apply/Cancel, lifecycle and geometry coverage.
- [x] GUI, triggers, project-I/O, docs focused checks and non-Qt precommit.
- [x] Document visible manual smoke path; Qt and real hardware checks are not
  authorized by this task and will not run automatically.

## Verification results

Focused verification passed: triggers 175, GUI-safe 83, project-I/O 392 with two
Windows symlink-permission skips, and docs 10. Mypy passed all 245 source files;
changed-source Ruff, compilation and configuration validation passed. Independent
review found no blocking issues. Four-worker non-Qt precommit passed 3,645 tests
with 12 Windows symlink-permission skips in 309.87 seconds. No failures occurred.

After merging remote master `8ec53bb` (interrupted-session acknowledgements), the
combined precommit run passed 3,665 tests with the same 12 permission skips in
320.97 seconds. Focused recording/recovery integration passed 162 tests with one
permission skip. Lint, compilation, mypy and repository audits passed on the merge;
the new BioSemi Qt and physical-hardware acceptance limits below still apply.

Registered Qt tests cover 700x640 states in both themes, selected-port checks,
stale jobs, Apply/Cancel, failed saves, project reopen and default inheritance.
They are added and compiled, not executed. No real serial enumeration, port opens,
marker tests or EEG acquisition were performed during implementation. Follow the
visible fake-service smoke path in `docs/GUI_WORKFLOW.md` before claiming visual
or physical acceptance.
