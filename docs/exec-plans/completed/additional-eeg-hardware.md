# ActiveThree and Brain Products recording support

Status: Completed

Date: 2026-10-16

## Outcome and decisions

The user requested the latest remote changes and recording/trigger support for
BioSemi ActiveThree with 128 electrodes and Brain Products. The checkout was clean
and `git pull --ff-only` reported already up to date. The user explicitly selected
the USB TriggerBox route while the exact Brain Products amplifier is unknown.

Settings > Recording remains the primary action: select hardware, configure its
endpoint, Apply, then launch with the existing participant and timing workflow.
Cancel preserves the prior selection. Home/Run identify the selected hardware;
Test/Pilot remains no-output. Success means persisted choices, correct adapter
selection, distinct acquisition evidence, and explicit setup/write/reset failures.

## Boundaries and implementation

- Reuse BioSemi's current single-byte serial adapter for ActiveThree; the vendor
  lists its USB Trigger Interface for Active3, Active2.5 and Active2.
- Add a dedicated Brain Products TriggerBox/rev.02/Plus serial adapter: fixed
  2,000,000 baud, 8N1, no flow control, zero idle and normal codes 1–255.
- Perform event writes synchronously at the existing flip callback. A bounded
  connection-owned worker resets to zero after the configured pulse. No sleeps,
  retries, event queues or schedule changes enter presentation. Reject overlapping
  pulses and insufficient low intervals explicitly; surface background reset errors.
- Preserve the last pulse during reset/cleanup outside the display callback. Close
  the worker and port on success, abort and failure.
- Add `biosemi_active_three` and `brainproducts_triggerbox` recording selections.
  ActiveThree resolves to the existing `serial` transport; TriggerBox has its own
  transport identity and project port/pulse settings (COM3 / 10 ms defaults).
- Keep existing serial/Unicorn defaults, profiles, frame contracts and exports.
  New devices have no fabricated Toolbox acquisition/montage profile; their
  hardware selection and marker evidence remain explicit. Toolbox qualification
  for those montages is outside this Studio task.
- Reuse existing GUI components/staged project recording saves. Cover minimum and
  default dialog sizes, conditional fields, long labels, Apply/Cancel and launch
  forwarding in registered Qt tests. Do not run Qt locally without approval.

## Evidence

Official sources checked on 2026-10-16:

- [BioSemi compatibility](https://www.biosemi.com/faq/prices.htm)
- [BioSemi USB Trigger Interface](https://www.biosemi.com/faq/USB%20Trigger%20interface%20cable.htm)
- [Brain Products programming examples](https://www.brainproducts.com/download/triggerbox-programming-examples/)
- [Brain Products trigger guide](https://www.brainproducts.com/download/communication-with-the-trigger-port-a-beginners-guide/)
- [TriggerBox Plus setup](https://www.brainproducts.com/download/how-to-set-up-the-triggerbox-plus/)

TriggerBox Plus requires its driver and PC switches for the lower eight bits,
an amplifier-specific output cable, and an exclusive COM connection. Recorder
must treat all eight bits as high-active Stimulus codes. Pulse and low intervals
must accommodate amplifier sampling (for example, 8 ms at 250 Hz for actiCHamp/
LiveAmp; 20 ms at 100 Hz for actiCHamp). Software timers are not measured physical
pulse/timing qualification. Vendor software owns acquisition and recording.

## Verification and remaining work

- [x] Baseline trigger focused route: 59 passed.
- [x] Core selection/persistence/config and compatibility coverage.
- [x] Fake-serial TriggerBox protocol, repeated markers, overlap, error and cleanup tests.
- [x] Runtime selection, Test/Pilot, preflight and acquisition evidence coverage.
- [x] Registered GUI coverage and documented visible smoke path.
- [x] Run focused routes, harness configuration and repo precommit.
- [x] Update canonical runtime/GUI contracts, architecture and agent routing.

Verification on 2026-10-16: triggers focused 97 passed; core focused 522 passed
and one Windows symlink skip; runtime focused 608 passed and two symlink skips;
GUI focused 17 passed without running Qt; docs focused 10 passed. Config/service
coverage passed 62 tests. Harness configuration, changed-file Ruff/compilation,
mypy across 237 source files and harness/docs audits passed.

Repo precommit completed with 3,117 passing tests and 11 symlink skips, but two
unchanged bundle-import tests failed at `core/project_bundle.py:454` with Windows
`PermissionError [WinError 5]` while renaming a staging directory. A focused rerun
of the two affected files produced 75 passing tests and five failures at that same
rename boundary, across different cases. Thus the full precommit gate is not green.
This task changes no bundle import/rename implementation; the selected hardware,
adapter, runtime and config tests passed. The existing active Studio/Toolbox plan
also records this Windows rename failure from its earlier validation. No retry,
permission, antivirus or unrelated filesystem behavior was changed here.

Physical hardware, recorded marker inspection and visible GUI qualification remain
manual acceptance and were not run during this implementation. The runtime and GUI
contracts above retain the reproducible operator checks. New-device Toolbox
montage/decoder support remains separate from Studio trigger support.
