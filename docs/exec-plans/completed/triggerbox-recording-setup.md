# TriggerBox discovery and pulse validation

Status: Completed

Date: 2026-10-26

## Authorized outcome

Keep Settings > Recording > Recording Setup simple while discovering TriggerBox
COM ports without opening them. Manual port entry remains available. Validate the
pulse against the selected amplifier family, EEG sampling rate and compiled marker
spacing. Explain and verify ordinary 6 Hz FPVS on a 60 Hz display.

## Boundaries and assumptions

- Discover explicit TriggerBox device descriptions using serial-port metadata on an
  app-owned worker. Never send probe bytes or claim that enumeration proves receipt.
- Keep one common 2,000,000 baud profile for TriggerBox rev.02 and Plus. No driver
  installation, Recorder control, EEG reads or guessed amplifier settings.
- Add optional amplifier/rate fields so existing project files remain readable.
  Require explicit valid information for normal Brain Products recording launches.
- Use Brain Products' January 2025 trigger-port guide, tables 1, 4 and 6. Preserve
  integer pulse widths, zero reset and the existing gap greater than twice the pulse.
- Preserve Test/Pilot no-output behavior and all other recording devices.
- Existing Recording Setup controls anchor the UI. Its primary action stays Apply.
  Budget the added fields, detection busy/empty/multiple/error states and wrapped
  validation at 700x640, without required scrolling. Keep optional detail in tooltips.

## Steps and checks

1. Add read-only discovery and amplifier timing helpers. Verify with fake port
   enumeration and parameterized vendor-table checks.
2. Wire staged GUI fields and app-owned discovery. Cover auto-selection, manual
   edits, multiple/no candidates, cancellation, persistence and no-clipping states
   in registered Qt tests; run only safe non-Qt checks locally.
3. Validate normal launch and record amplifier/rate metadata. Compile actual 6 Hz /
   60 Hz schedules and check ordinary oddball gaps plus short invalid schedules.
4. Update canonical workflow/runtime docs and agent routing. Run focused routes,
   harness checks and repo precommit. Physical hardware and approved visible GUI
   acceptance remain explicitly separate.

## Progress

- Baseline: clean master at 2962330; GUI focused verification passed (48 tests).
- Discovery, staged GUI integration, amplifier/rate validation and launch metadata
  are implemented. No transport, compiler schedule, version or installer changes.
- Read-only live enumeration completed with zero named TriggerBox candidates on
  this PC. Hardware-dependent recognition, marker receipt and physical timing
  remain separate acceptance work.
- Focused checks: triggers 126 passed; core 555 passed / one Windows symlink skip;
  GUI safe route 48 passed; docs 10 passed. Config routing, Ruff and compilation pass.
- Targeted runtime/model/persistence checks: 269 passed / two Windows symlink skips.
- Registered Qt tests cover `700x640`, both themes, discovery busy/empty/multiple/
  error/success, manual edits, cancellation and amplifier/rate validation. They were
  not run because no approved visible Qt environment was requested.
- Final runtime focused verification passed: 712 tests, three Windows symlink skips.
- Repo precommit Ruff, compilation, mypy (242 source files), harness GC and docs
  hygiene passed. Its broad unit run reported 3,389 passed, 12 skipped, 20 subtests
  passed and two failures. One was the launch-options assertion missing the new
  optional keys; it was corrected and its 29-test file passed, followed by the full
  runtime focused success above. The unchanged serialization Windows lock-code-33
  case failed in the broad run; all eight serialization tests passed on immediate
  rerun. No serialization code was changed, and the entire precommit command was
  not rerun. Final GUI source mypy, Ruff and compilation passed.
- No GUI window, electrical trigger test, Recorder acquisition or installer build
  was run. The canonical runtime/workflow docs describe the visible and lab smoke
  paths; synthetic passing tests do not qualify physical timing.

Subsequent approved visible GUI and packaging acceptance is tracked in the
[2.5.0 release record](../active/release-2.5.0.md).

## Files changed

- `.agents/verification.toml`
- `ARCHITECTURE.md`
- `docs/GUI_WORKFLOW.md`
- `docs/PLANS.md`
- `docs/RUNTIME_EXECUTION.md`
- `docs/agent/agent-index.md`
- This execution plan.
- `src/fpvs_studio/core/brainproducts.py`
- `src/fpvs_studio/core/execution.py`
- `src/fpvs_studio/core/models.py`
- `src/fpvs_studio/gui/AGENTS.md`
- `src/fpvs_studio/gui/document_runtime.py`
- `src/fpvs_studio/gui/recording_dialog.py`
- `src/fpvs_studio/runtime/launcher.py`
- `src/fpvs_studio/runtime/recording.py`
- `src/fpvs_studio/triggers/AGENTS.md`
- `src/fpvs_studio/triggers/brainproducts_discovery.py`
- `tests/gui/test_recording_setup.py`
- `tests/unit/test_brainproducts_discovery.py`
- `tests/unit/test_brainproducts_timing.py`
- `tests/unit/test_models.py`
- `tests/unit/test_document_summary_refresh.py`
- `tests/unit/test_project_config.py`
- `tests/unit/test_project_service.py`
- `tests/unit/test_runtime_recording.py`
- `tests/unit/test_runtime_launcher_flow.py`
