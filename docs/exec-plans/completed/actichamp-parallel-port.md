# actiCHamp Parallel-Port Output

Status: Completed

## User workflow and scope

Add an explicit Brain Products / BrainVision parallel-port recording choice for
actiCHamp and actiCHamp Plus. Preserve existing TriggerBox, BioSemi and Unicorn
choices. In Recording Setup, discover Windows LPT device metadata and available
I/O addresses without emitting markers; allow explicit manual address entry and
preserve drafts. Detection does not identify an attached amplifier or prove receipt.

## Implementation boundaries

- Core owns the optional address, hardware identity and neutral recording snapshot.
  No machine transport fields enter RunSpec or SessionPlan.
- Triggers owns Windows InpOut access, full-byte writes, pulse/reset lifecycle and
  read-only port discovery. Require an already installed and running compatible driver;
  do not install drivers, guess an address or silently change transport.
- Runtime validates the explicit address and actiCHamp sampling-rate/pulse limits,
  constructs the adapter and preserves condition-boundary draining and logging.
- GUI reuses staged Recording Setup and app-owned discovery workers. Test/Pilot
  sends no markers. Missing ports, addresses or drivers remain explicit failures.

## Verification and acceptance

- Fake-driver tests cover codes 1–255, idle zero, overlapping pulses, required low
  intervals, asynchronous reset failure and cleanup. Discovery tests never touch ports.
- Non-Qt integration tests cover persistence/config interchange, launch forwarding,
  snapshots, preflight and Test/Pilot suppression.
- Registered GUI coverage checks selection, draft/cancel/detection states and geometry
  at the existing minimum/default sizes. Do not run Qt without explicit approval.
- Run triggers/runtime/gui focused routes and repo precommit; refresh routing/docs.
- Physical marker receipt, cabling and timing remain a separate lab qualification.

## Progress

- Implemented the adapter, metadata discovery, staged Recording Setup, computer
  hardware choice, persistence/config/bundle interchange, launch forwarding,
  preflight, condition-boundary reset, failure recovery and recording snapshots.
- Use checked Windows device I/O against the installed InpOut driver rather than its
  DLL: the vendor DLL can install/start a driver on load and hides failed writes.
  Studio neither loads that DLL nor installs/starts the driver.
- Driver/discovery tests: 69 passed using fake devices and Windows API seams.
  GUI focused checks: 98 passed. Model/config/project-service/default-preference
  checks: 189 passed, one expected Windows symlink-permission skip. Targeted
  recording/launcher/bundle checks: 178 passed, one expected symlink skip.
- Changed feature files pass Ruff and compilation. Mypy passes all 250 source files.
  Harness/config/docs audits pass. Read-only discovery ran successfully on this PC
  and found zero LPT candidates; no output driver was opened.
- The full safe suite with four workers reported 3,954 passed, 12 expected Windows
  symlink skips and 24 passed subtests. Two existing tests failed reading long
  temporary paths: `test_run_checkpoint_excludes_raw_task_answers` and
  `test_materialize_rot180_outputs_png_and_updates_manifest`. Both pass serially,
  reproduce with the normal parallel-worker path nesting, and pass with a fresh
  shorter `--basetemp` in parallel. No unrelated production/test code was changed.
- The unmodified precommit entry point is also blocked by four existing E501 errors
  in the pre-existing untracked `engines/standalone_contrast_example.py`. Remaining
  precommit commands were run with only that file omitted from changed-file lint
  and compilation; it was preserved.
- Registered Qt geometry/interaction tests were updated but not run, as required by
  the repository's visible-environment approval rule. Recording Setup stays at
  `700x640`; the hardware picker stays at `640x300`, with both themes covered in
  registered cases. No physical driver, EEG receipt, cabling or timing test was run.

## Implementation map

- Hardware contracts: `core/models.py`, `core/recording_hardware.py`,
  `core/execution.py`.
- Windows output/discovery: `triggers/parallel_backend.py`,
  `triggers/parallel_discovery.py`, `triggers/parallel_windows.py`.
- Runtime integration: `runtime/launcher.py`, `runtime/recording.py`,
  `runtime/triggers.py`, `runtime/run_worker.py`.
- GUI: `gui/recording_dialog.py`, `gui/parallel_port_selector.py`,
  `gui/document_runtime.py`, `gui/home_page.py`.
- Coverage: `tests/unit/test_parallel_backend.py`,
  `tests/unit/test_parallel_discovery.py`, `tests/unit/test_models.py`,
  `tests/unit/test_project_config.py`, `tests/unit/test_project_service.py`,
  `tests/unit/test_project_bundle.py`, `tests/unit/test_default_recording_preferences.py`,
  `tests/unit/test_runtime_launcher_flow.py`, `tests/unit/test_runtime_recording.py`,
  registered `tests/unit/test_document_summary_refresh.py`,
  `tests/gui/test_recording_setup.py`, `tests/gui/test_default_recording_setup.py`.
- Routing and setup guidance: `.agents/verification.toml`, `ARCHITECTURE.md`,
  `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, `docs/RUNTIME_EXECUTION.md`,
  `docs/PACKAGING.md`, `docs/agent/agent-index.md`, `docs/PLANS.md`,
  `src/fpvs_studio/gui/AGENTS.md`, `src/fpvs_studio/triggers/AGENTS.md`, and this plan.
