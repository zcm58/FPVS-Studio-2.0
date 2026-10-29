# AGENTS.md

## Scope of this directory

`src/fpvs_studio/triggers/` contains trigger backend interfaces and optional hardware
adapter scaffolding.

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
- Automatic TriggerBox discovery reads named COM-port metadata only. Explicit Detect
  may open and close recognized candidates on the app-owned worker to check access;
  never issue probe reads, marker writes or explicit reset/flush calls. Close constructed
  connections on failure/cancellation, stop between candidates, and retain manual
  selection. Metadata and successful port access do not prove identity or marker receipt.
- `serial_port_access.py` owns generic metadata enumeration and shared byte-free
  open/close checks. BioSemi checks only the user-selected port at the project's
  configured baudrate (normally 115200); never probe every generic serial port or
  infer BioSemi identity from an openable port. TriggerBox retains its named-candidate
  filter and fixed baudrate while reusing the access helper.
- ActiveThree reuses BioSemi's serial byte protocol. Brain Products TriggerBox rev.02/
  Plus uses a distinct adapter/identity at fixed 2,000,000 baud. Its connection-owned
  worker clears a latched event after the configured pulse; sends never sleep or queue.
  Reject active pulses/insufficient low intervals, retain asynchronous reset failures
  until observed, and always close worker/port. Reset/close may drain a pulse only
  outside presentation. Keep codes 1–255 intact and use zero solely for idle/reset.
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
