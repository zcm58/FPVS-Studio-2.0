# AGENTS.md

## Scope of this directory

`src/fpvs_studio/triggers/` owns trigger interfaces, hardware adapters and discovery.

## Requirements

- Keep trigger backends runtime-facing and hardware-adapter focused.
- External adapters must explicitly report `emits_external_markers=True`; the base
  contract preserves legacy `emits_hardware_triggers` adapters. UDP must report its
  own `unicorn_udp` identity without claiming direct hardware output or EEG receipt.
- Keep trigger planning in compiled core contracts and trigger logging/export behavior
  in runtime.
- Do not push serial-port or hardware-only settings into `RunSpec` or `SessionPlan`.
- Accept normal event marker codes only in the `1`-`255` range. Code `0` is reserved
  for explicit manual reset and must not be emitted for condition or oddball events.
- Keep unavailable hardware behavior explicit; do not add silent fallbacks that hide
  failed trigger emission.
- Discovery reads port metadata. `serial_port_access.py` owns byte-free open/close
  checks on the app-owned worker. Preserve cancellation, cleanup and manual selection.
  TriggerBox Recording Setup checks named candidates and the selected port on Detect.
  BioSemi Recording Setup checks the selected port at the project baud rate.
- Trigger Tester checks one port per attempt. Automatic detection uses a unique
  named TriggerBox or BioSemi interface. BioSemi also supports operator-guided
  reconnect when one COM port appears and no others change. The configured BioSemi
  port is available when there is no named match. A generic name, chipset or
  successful open does not establish identity or marker receipt.
- `serial_errors.py` classifies native/serialized serial failures without naming an
  owner. `biosemi_errors.py` and `brainproducts_errors.py` share vendor-specific
  recovery wording between setup and launch. BioSemi recovery names the USB Trigger
  Interface, not the EEG USB Receiver or Brain Products utilities; keep ActiView recording.
  Preserve native/serialized Windows reasons and raw diagnostics. No named port does
  not prove a missing driver; a running utility or denied access does not identify
  the handle owner. Keep connection, write/reset failure and timing evidence distinct.
- ActiveThree reuses BioSemi's serial byte protocol. Brain Products TriggerBox rev.02/
  Plus uses a distinct adapter/identity at fixed 2,000,000 baud. Its connection-owned
  worker clears a latched event after the configured pulse; sends never sleep or queue.
  Reject active pulses/insufficient low intervals, retain asynchronous reset failures
  until observed, and close worker/port once pending I/O is resolved. Reset/close may drain a pulse only
  outside presentation. Keep codes 1–255 intact and use zero solely for idle/reset.
- `brainproducts_windows.py` owns genuine pySerial Win32 write completion. Preserve
  one outstanding write and its byte buffer until Windows reports a terminal result.
  Flip callbacks submit without waiting; the worker observes completion before
  starting pulse/low deadlines. Connect/reset/close drain outside presentation with
  bounded failure handling. Cancellation requests are not completion; a driver that
  never acknowledges cancellation requires retained native storage and an explicit
  restart error, never a false clean close or reuse of pending storage.
  BioSemi reuses this completion helper without a reset worker: poll before the next
  marker, reject an outstanding write rather than queue it, and drain/cancel only
  outside timed presentation. Its finish_pending_output hook drains at the runtime
  condition boundary before feedback/tasks. Do not add an implicit zero to its
  auto-reset protocol.
- Resolve unset/blank serial-port configuration to `COM3`, while preserving an
  explicit nonempty port. This is a configuration default, never a retry/fallback
  after a port fails to open or write.
- Parallel-port output is an explicit Windows actiCHamp transport. Open only the
  installed InpOut device, check each device-I/O result, and close it on failure.
  Never load the auto-installing vendor DLL, install/start drivers, guess addresses
  or probe ports by writing. Discovery reads Windows device/resource metadata only.
- Let backend open/write failures propagate to runtime so they can abort and export a
  clear error record. Runtime owns the pre-run serial-open check and trigger logs.
- Unicorn UDP uses only `127.0.0.1`, a validated port, prepared decimal ASCII codes,
  and one nonblocking datagram submission per marker. No automatic reset, waits,
  retries, receiver detection, or compensation is permitted. Runtime owns the
  prelaunch Recorder readiness check and pending qualification metadata; use injected
  fake sockets in automated tests.

## Restrictions

- No PySide6 imports here.
- No PsychoPy imports here.
- Do not couple trigger backends to project JSON models or GUI widgets.

## Verification

- Run `./scripts/verify.ps1 -Scope triggers -Tier focused`. Use the repo
  precommit tier when trigger changes cross runtime or core contracts.
