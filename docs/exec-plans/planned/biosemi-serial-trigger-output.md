# BioSemi Serial Trigger Output

Status: Planned

## Summary

Implement BioSemi-compatible serial trigger output for FPVS Studio while preserving the
current runtime and engine boundaries. The current runtime compiles condition trigger
events and the PsychoPy engine observes them during playback, but runtime trigger backend
selection always uses the logged null backend. As a result, trigger logs can record
attempts while no serial bytes are written to BioSemi/ActiView hardware.

This plan should add real serial output and expand trigger scheduling so markers align
with actual visual onsets:

- send the condition-specific trigger code on the exact flip that shows the first image of
  each condition;
- send an oddball trigger code on the exact flip that shows every oddball image;
- default the oddball trigger code to `55`;
- make the oddball trigger code configurable in project trigger settings;
- match the lab's previous PsychoPy serial pattern by opening
  `serial.Serial(port="COM3", baudrate=115200)` and writing marker bytes to the port.

## Current Blocker

FPVS Studio currently has the scheduling and timing seams needed for trigger output, but
the hardware backend is not implemented:

- `RunSpec.trigger_events` currently includes only a condition-start trigger at frame `0`.
- The PsychoPy engine schedules observed trigger events with `window.callOnFlip(...)`.
- `src/fpvs_studio/runtime/triggers.py` always builds a logged null backend, even when a
  serial port is configured.
- `src/fpvs_studio/triggers/serial_backend.py` is a scaffold that raises
  `NotImplementedError` for connect, send, and reset.

The first fix should address the backend and schedule gaps directly. It should not hide a
failed serial connection by falling back to null output.

## Target Behavior

During condition playback:

- the first visual frame of the condition sends the condition's configured trigger code;
- every oddball image onset sends the configured oddball trigger code;
- trigger timing is derived from compiled stimulus onset frames, not from runtime
  recomputation;
- trigger emission is scheduled with PsychoPy `window.callOnFlip(...)` so the marker write
  is tied to the flip that presents the image;
- trigger logs report the same frame index, code, label, backend, and status used for the
  attempted hardware send.

Recommended trigger labels:

- `condition_start` for the first condition image;
- `oddball_onset` for oddball image onsets.

The serial backend should initially support the lab's known BioSemi path:

```python
import serial

port = serial.Serial(port="COM3", baudrate=115200)
port.write(str.encode(chr(trigger_code)))
```

Prefer `bytes([trigger_code])` internally for byte-safe writes after confirming BioSemi
behavior, because `str.encode(chr(code))` can produce multi-byte UTF-8 output for codes
above ASCII range.

## Boundaries

- Keep trigger timing in compiled `RunSpec.trigger_events`.
- Keep COM port, baudrate, pulse width, reset code, and reset delay out of `RunSpec` and
  `SessionPlan`.
- Keep hardware I/O in `src/fpvs_studio/triggers/`.
- Keep runtime backend selection and trigger logging in `src/fpvs_studio/runtime/`.
- Keep PsychoPy-specific on-flip scheduling in `src/fpvs_studio/engines/`.
- Do not expose hidden serial controls in the current GUI unless a later UI plan explicitly
  approves that workflow.
- Do not add a parallel/TTL backend as part of the first implementation.

## Implementation Phases

### 1. Add Oddball Trigger Setting

- Add a project trigger setting for oddball trigger code with default `55`.
- Validate serial marker codes as single-byte-safe values unless BioSemi testing confirms a
  wider supported range.
- Preserve existing project defaults and persisted project compatibility.

### 2. Compile Trigger Events From Stimulus Onsets

- Update trigger schedule compilation to inspect the compiled `StimulusEvent` sequence.
- Emit the condition trigger at the first stimulus event's `on_start_frame`.
- Emit an oddball trigger at each `StimulusEvent(role="oddball").on_start_frame`.
- Keep the trigger schedule frame-based and engine-neutral.

### 3. Implement BioSemi Serial Backend

- Implement serial port connect, marker write, optional reset, and close behavior.
- Use configured port and baudrate, with the lab baseline of `COM3` and `115200`.
- Fail clearly when `pyserial` is unavailable, the port cannot be opened, or a write fails.
- Do not silently fall back to `NullBackend` after a configured serial backend fails.

### 4. Wire Runtime Backend Selection

- Build a serial logged backend when serial output is configured.
- Use `backend_name="serial"` in trigger logs for real serial attempts.
- Keep null backend behavior for explicitly disabled or unconfigured trigger output.
- Ensure `status="sent"` is recorded only after the backend write path succeeds.

### 5. Update Exports And Documentation

- Ensure run and session `trigger_log.csv` exports include condition and oddball rows.
- Update `docs/RUNTIME_EXECUTION.md`, `docs/RUNSPEC.md`, and `ARCHITECTURE.md` after
  implementation so the documented trigger behavior is current.
- Update any nested `AGENTS.md` files only if boundaries or standard verification commands
  change.

## Test Plan

Compiler tests:

- condition trigger is scheduled at the first stimulus onset frame;
- oddball triggers are scheduled exactly at oddball `StimulusEvent.on_start_frame` values;
- oddball trigger defaults to `55`;
- changing the oddball trigger setting changes all oddball trigger codes;
- trigger schedules remain deterministic for the same compiled stimulus sequence.

Serial backend tests:

- fake serial module opens the configured port and baudrate;
- marker writes match the expected BioSemi byte behavior for condition and oddball codes;
- reset behavior writes the configured reset code when enabled;
- close releases the fake port;
- missing serial dependency, open failure, invalid marker code, and write failure produce
  clear errors.

PsychoPy engine tests:

- trigger sends are scheduled through `window.callOnFlip(...)`;
- condition-start and oddball-onset markers fire in playback order;
- no trigger send is attempted when no backend is provided.

Runtime and export tests:

- configured serial output selects the serial logged backend;
- null output remains explicit when triggers are disabled or unconfigured;
- `trigger_log.csv` rows include correct frame indexes, labels, codes, backend names, and
  statuses;
- serial backend failures are not hidden by null fallback behavior.

GUI and persistence tests:

- oddball trigger setting persists in project JSON with default migration behavior;
- existing hidden serial launch settings still pass through to `LaunchSettings`;
- no new visible serial controls are exposed by this plan.

Documentation checks:

```powershell
python -m pytest -q tests\unit\test_harness_docs.py
```

## Acceptance Criteria

- BioSemi serial output is implemented behind the trigger backend boundary.
- Condition markers are sent on the flip that presents the first condition image.
- Oddball markers are sent on the flip that presents each oddball image.
- Oddball trigger code defaults to `55` and can be configured.
- Trigger logs represent actual backend attempts honestly.
- A configured serial backend failure is surfaced clearly and does not silently degrade to
  null output.
- Runtime-only machine settings remain outside compiled protocol contracts.
- Existing null/test trigger behavior remains available when hardware output is not
  configured.

## Assumptions

- The first supported BioSemi path is serial COM output matching the lab's prior PsychoPy
  implementation.
- The expected lab baseline is `COM3` at `115200` baud, but implementation should use
  configured values.
- Serial marker codes should be constrained to single-byte-safe values unless BioSemi
  testing confirms a wider supported range.
- The first implementation does not include a parallel/TTL backend.
- The first implementation does not add visible GUI controls for serial configuration.
