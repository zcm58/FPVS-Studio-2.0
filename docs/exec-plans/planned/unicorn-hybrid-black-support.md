# Unicorn Hybrid Black Recording Support

Status: Planned

Created: 2026-09-25

Implementation has not started. The user requested investigation and saved execution
plans, not production changes. Move this plan to `active/` when implementation becomes
the selected task. Hardware and timing acceptance remain separate from software checks.

## Outcome And User Decisions

Allow the existing Unicorn Hybrid Black headset to record experiments presented by
FPVS Studio, with Unicorn Recorder saving raw EEG and event markers to BDF+ for FPVS
Toolbox. Preserve the familiar operator workflow and existing BioSemi behavior.

The user confirmed these constraints on 2026-09-25:

- No additional purchases: no paid Python API, SDK, subscriptions, or new equipment.
- Studio sends event messages to Unicorn Recorder; Recorder owns EEG acquisition.
- Raw BDF+ is the first supported interchange format.
- Toolbox uses the actual eight-electrode montage, native 250 Hz, no resampling in
  either direction, and no electrode interpolation for the Unicorn profile.
- Shared FFT, baseline-corrected amplitude, and SNR methods stay unchanged except for
  explicit acquisition-specific inputs and capability checks in Toolbox.
- Bluetooth timing must be characterized honestly; an assumed delay is not a calibration.

Companion plan in the FPVS Toolbox Repo repository:
`docs/agent/exec-plans/future/unicorn-hybrid-black-support.md`.
Studio owns transport and presentation evidence; Toolbox owns acquisition normalization,
sample integrity, analysis alignment, montage, referencing, QC, and analysis provenance.
Neither repository imports the other application as a dependency.

## Scope And Non-Goals

First delivery targets Windows with Studio and Recorder running on the same computer.
The EEG travels over the existing Bluetooth connection; UDP markers stay on loopback.

```text
Hybrid Black -- Bluetooth EEG --> Unicorn Recorder -- raw BDF+ --> FPVS Toolbox
FPVS Studio  -- local UDP code --> Unicorn Recorder
```

Use Python's standard-library socket support. Do not embed vendor binaries, install
an SDK, create a custom recorder, or make internet access a run-time dependency of the
Studio adapter. Vendor software installation/licensing behavior remains vendor-owned.

Out of scope: remote-computer networking, simultaneous BioSemi and Unicorn output,
LSL/XDF, general EEG-driver registries, automatic Recorder start/stop, a signal viewer,
automatic acquisition recovery, experiment redesign, and a complete monitor-settings
redesign. A limitation discovered in validation does not authorize changing transport,
buying hardware, or expanding these boundaries automatically.

## Evidence And Unknowns

Source checkout inspected: Studio `master`, commit `6c95178`, on 2026-09-25.
Recheck source owners and the companion plan before implementation; these are evidence
pointers, not permission to overwrite intervening work.

Vendor sources accessed 2026-09-25:

- [Recorder manual](https://github.com/unicorn-bi/Unicorn-Recorder-Hybrid-Black/blob/main/README.md):
  raw BDF+/CSV logging, UDP ASCII trigger input, and optional diagnostic signals.
  Its example uses loopback port 1000; raw logging is separate from display processing.
- [Vendor FAQ](https://www.gtec.at/unicorn-faq/): Suite 1.24.00 introduced BDF+ support
  and made Recorder available without its previous separate license. Confirm the
  installed build; do not purchase the separately described Python API for this route.
- [Hardware manual](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornHybridBlack.md):
  stock cap positions are Fz, C3, Cz, C4, Pz, PO7, Oz, PO8. Confirm actual wiring.
- [PsychoPy timing guidance](https://psychopy.org/general/timing/millisecondPrecision.html):
  software flip timing and physical stimulus appearance require separate validation.

The Recorder documentation does not establish exact supported trigger ranges,
repeated-code/reset behavior, same-sample collision handling, status-channel scaling,
or the acquisition sample to which a received message is assigned. Built-in Bluetooth
delay compensation is not established. These are Phase 0 questions, not assumed facts.

## Current Owners And Required Seams

| Existing owner | Current behavior and planned responsibility |
| --- | --- |
| `gui/document_runtime.py` | Forces serial for ordinary runs. Resolve the selected local recording configuration before building launch settings. |
| `gui/controller.py`, `gui/settings_dialog.py` | Existing preference ownership and settings surface. Persist/edit the narrow local transport choice here rather than in experiment timing contracts. |
| `runtime/launcher.py` | `LaunchSettings` and validation assume serial outside Test/Pilot modes. Validate the selected production transport explicitly. |
| `triggers/base.py`, `triggers/serial_backend.py` | Adapter contract and unchanged BioSemi byte-writing behavior. Add one focused Unicorn UDP adapter under `triggers/`. |
| `runtime/triggers.py` | Factory and logged wrapper currently allow serial/null identities only. Add truthful Unicorn transport identity and logging. |
| `engines/psychopy_engine.py`, `engines/psychopy_triggers.py` | Existing `callOnFlip` emission seam and run-relative callback clock. Preserve frame scheduling and warmup exclusion. |
| `runtime/run_worker.py` | Open before presentation, abort/error handling, cleanup; replace COM-specific error assumptions only where the selected backend requires it. |
| `core/execution.py`, `runtime/session_export.py` | Neutral result fields and export ownership. Retain actual marker attempts, profile, and clock provenance. |
| `gui/run_page.py` | Current BioSemi recording prompt. Present device-appropriate readiness instructions and honest confirmation status. |
| `core/library_publish.py` | Legacy portable serial fields are normalized to COM3. A local Unicorn choice must not be overwritten by project/library settings. |
| `core/compiler_schedules.py` | Existing condition/oddball schedule and one-marker-per-frame rule; scientific scheduling remains unchanged. |

The existing [lab-independent recording setup plan](lab-independent-recording-setup.md)
owns the broader profile/display direction. Reuse its local-settings and migration
precedence rather than creating a competing profile store. If it lands first, extend it.
Otherwise implement only the two transport choices needed here using existing preference
services; named custom profiles and display-identity changes are not prerequisites.

## Proposed Behavior

### Local Setup And Compatibility

1. Offer BioSemi serial and Unicorn Recorder UDP as explicit recording choices.
2. Use loopback `127.0.0.1`; expose a validated UDP port matching Recorder, initially
   1000. No remote host selection in this first delivery.
3. Keep endpoint/device details outside portable `ProjectFile` timing settings,
   `RunSpec`, and `SessionPlan`. Keep existing project trigger fields readable and
   round-trippable; do not silently migrate or rewrite old projects.
4. An explicitly selected local configuration takes precedence over legacy serial
   fields. With no selection, retain the existing BioSemi behavior. An invalid saved
   selection is an actionable error, never a reason to switch to serial or null.
5. Show the effective choice before launch. Preserve existing BioSemi/Sophia prompt
   behavior for that choice and preserve display/timing preflight requirements.
6. Test/Pilot remains an explicit no-output workflow. Selecting Unicorn must not turn
   test sessions into real transmissions or bypass existing production safeguards.

### Adapter And Event Semantics

Prepare the socket and encoded payloads before timed presentation. Convert an approved
numeric code to decimal ASCII: proposed code 55 becomes `b"55"`, not a single raw
byte with numeric value 55. Exact payload framing must match the tested Recorder build.

At the existing flip callback, make one nonblocking datagram submission for each
compiled marker. Do not add sleeps, waits for replies, unbounded worker queues,
retries, or guessed Bluetooth compensation to the frame loop. A would-block or socket
error propagates through the existing failed-run path with exportable evidence.
Opening a UDP socket does not prove that Recorder is listening or saving to disk.

Preserve normal codes 1-255, the existing oddball-55 policy, event order, actual
compiled frames, and one-marker-per-frame validation. Verify Recorder accepts the
range and rates before enabling the corresponding production configuration. Do not
silently remap codes, split colliding markers, or add automatic reset messages. Code
zero remains an explicit reset only if the receiver semantics are proven compatible.
If repeated codes require a different wire protocol, resolve that explicitly before
enabling support; no hidden pulse schedule is introduced into the compiler.

Update the base capability, production gate, factory, and logged wrapper together.
The existing `emits_hardware_triggers` and serial/null name assumptions must not force
UDP to impersonate serial. Use a narrowly scoped capability meaning external marker
output, preserving rejection of log-only output in production. No backend capability
or success status may imply a marker reached an EEG sample or disk.

### Operator Workflow

1. Pair the existing headset using the vendor-supported setup and open Recorder.
2. Select raw BDF+ recording and the tested diagnostic-channel configuration. Confirm
   the acquisition source is real electrodes rather than the vendor test signal.
3. Enable Recorder's UDP trigger input on the same port selected in Studio.
4. Start recording under the intended participant/session association before launching.
5. Studio displays the selected transport and asks the operator to confirm Recorder
   is saving the intended recording. Store this as operator confirmation, not telemetry.
6. Run the unchanged experiment. Recorder remains responsible for continuous acquisition.
7. Stop Recorder manually, register its BDF+ in Toolbox, and reconcile recorded markers
   with Studio's event evidence before treating the recording as accepted data.

Do not claim automatic detection of an absent recorder, a paused recording, disk-write
failure, headset disconnection, or UDP packet loss without a demonstrated receiving-side
mechanism. An optional operator-invoked marker test must be clearly identified and
outside participant data; final marker verification reads the saved recording.

### Cross-Application Evidence Contract

Freeze one versioned semantic handoff with the Toolbox plan in Phase 0. Reuse current
session/run identifiers and export owners. Final serialization and filename belong in
the canonical runtime contract when implemented; no schema described here exists yet.

| Evidence | Owner and meaning |
| --- | --- |
| Contract/Studio version; participant, session and run identities | Studio; explicit association, never inferred from time proximity alone. |
| Recording association and condition/oddball code map | Explicit operator/project mapping; BDF remains the EEG authority. |
| Ordered actual event attempts: code, label, run, frame, callback timestamp, send status | Studio runtime; distinguish compiled intent from attempted/failed emission. |
| Clock origin and units for each time field | Studio; callback time is run-relative, not an EEG sample index or synchronized headset clock. |
| Effective transport/port and Recorder/raw-logging confirmation | Runtime snapshot; vendor version/device information is observed or explicitly unknown. |
| Recorded event samples, integrity findings, montage, reference and any alignment correction | Toolbox; preserve original values and record derived analysis values separately. |

Keep the evidence available in both full and compact export modes. Reuse existing
full-mode trigger/event exports. Current compact mode has no durable trigger log and
deletes successful recovery checkpoints after report export; those checkpoints cannot
satisfy this requirement. Add a small runtime-owned acquisition/event sidecar for
Unicorn compact sessions rather than globally enabling detailed exports. Place artifacts
under the active project using existing run/log ownership; support reserved visits,
aborts, cancellation, and partial
failure. Do not write into vendor installation directories or overwrite the raw BDF.

The BDF is self-contained for EEG and recorded markers. The handoff supports audit and
session association; Toolbox's explicit reviewed-protocol import remains the route
for recordings without a Studio handoff. Do not manufacture a Studio reconciliation
result when that evidence is absent.

## Bluetooth Delay And Acceptance Levels

An event message reaches Recorder locally while the arriving EEG may have been
buffered by the device, Bluetooth stack, or acquisition software. Depending on
Recorder's assignment rule, a marker can precede or follow its correct EEG sample.
Do not hard-code a 20 ms, 40 ms, or literature-derived shift, or delay Studio messages
to compensate. The correction sign is a measured property of the complete setup.

Separate four levels of evidence:

1. Configuration valid: local selection and socket setup passed.
2. Operator confirmed recording: a human confirmed the selected vendor workflow.
3. Recorded-marker integrity verified: Toolbox found the expected events in the BDF.
4. Physical timing characterized: measured onset-to-event offset, variability, and
   drift are within a predeclared bound for the intended experiment/harmonics.

No level implies the next. Packet counters and reception intervals can support
continuity checks but cannot alone measure absolute acquisition-to-PC latency.
Screen-flip timestamps are not measurements of monitor pixel onset.

When existing suitable lab equipment is available, measure known physical onsets
through an appropriate recording arrangement; do not require buying sensors or
improvise electrical connections to the headset. Include the beginning, middle, and
end of a representative long session under expected load. Record offset sign, median,
spread/tails, drift, lost markers, sample gaps, and display frame failures. Choose
acceptance bounds before qualification, based on the intended analysis and highest
retained harmonic; do not choose a passing threshold after seeing results.

A constant measured offset may later be applied by Toolbox to analysis event indices
with rounding/residual error and calibration provenance. Studio sends promptly and
keeps its raw timestamps. Uncalibrated/unknown and measured zero must be distinguishable.
A constant shift does not repair jitter, drift, or dropped samples. If no suitable
existing measurement setup or trustworthy vendor characterization is available, software
development can proceed, but physical timing qualification remains explicitly pending.

## Implementation Phases

### Phase 0 - Prove The Receiver Contract And Freeze The Handoff

- [ ] Record installed Suite/Recorder build, headset identity, Windows/Bluetooth setup,
  raw logger configuration, and actual electrode mapping without publishing identifiers.
- [ ] Capture a small permission-cleared raw BDF+ fixture and parallel raw CSV for
  validation only; CSV import is not a new shipping feature in this plan.
- [ ] Test known condition markers, repeated 55, boundary values, adjacent-frame rates,
  first/last events, and an aborted session. Verify wire framing, reset behavior,
  recorded counts/order, sample placement, status units, and loss indicators.
- [ ] Determine whether BDF diagnostics preserve detectable dropped/invalid samples.
  Document omissions rather than inventing continuous data.
- [ ] Freeze the shared semantic evidence contract and supported Recorder configuration
  with Toolbox. Archive source/build references and fixture hashes alongside tests/docs.
- [ ] Identify remaining physical timing uncertainty and a no-purchase validation route.

Gate: known recorded-marker semantics and a usable raw-file contract. Fakes can support
parallel adapter development, but they do not satisfy this gate or authorize a support
claim. Unsupported firmware/software or undiscoverable loss must be reported explicitly.

### Phase 1 - Runtime Selection And UDP Adapter

- [ ] Add the narrow local configuration, legacy precedence, and validation.
- [ ] Implement a focused `triggers/` adapter using standard-library sockets only.
- [ ] Update factory, capability checks, transport labels, and backend-specific errors.
- [ ] Preserve BioSemi single-byte output and test/pilot null behavior.
- [ ] Exercise failures with fakes; no automated test opens real hardware or sends
  network markers to a potentially active Recorder.

Gate: exact encoded output, one submission per scheduled event, and deterministic
failure/cleanup behavior with unchanged scientific schedules.

### Phase 2 - Recording Workflow And Durable Evidence

- [ ] Add shared-component settings/run controls and appropriate Recorder instructions.
- [ ] Capture explicit operator confirmation and runtime configuration snapshots.
- [ ] Export handoff evidence in full and compact modes, including partial/aborted runs.
- [ ] Preserve cancellation, participant visit reservations, path invariants, and
  historical export readability; version any additive acquisition metadata.
- [ ] Add registered GUI coverage and document visible acceptance at the existing
  main-window/settings minimum sizes; if Setup changes, all eight steps still fit 1120x820.
- [ ] Register any new adapter test file in the explicit triggers verification route;
  run the harness configuration check if `.agents/verification.toml` changes.

Gate: an operator can prepare, run, abort, and identify the correct recording without
editing project files, and exported evidence never overstates acquisition readiness.

### Phase 3 - Toolbox Integration And Timing Qualification

- [ ] Run a full recording through the companion Toolbox plan: native 250 Hz,
  interpolation off, explicit reference/ROI/QC policy, event reconciliation and spectra.
- [ ] Reconcile the expected and actually recorded code sequence across all conditions
  and runs; missing or extra markers must be surfaced, not reconstructed silently.
- [ ] Exercise Recorder absent/not recording, wrong port, vendor disconnect, missing
  samples, and interrupted sessions using controlled test data/setup.
- [ ] Complete or explicitly defer physical timing qualification with measured evidence.
- [ ] Verify the packaged Studio works without UnicornPy/vendor DLL bundling or added
  purchases; test BioSemi installation/workflows for regressions.

Gate: complete normal-workflow integration plus an explicit timing qualification state.
No claim of BioSemi timing or spatial equivalence follows from this feature alone.

### Phase 4 - Documentation And Handoff

- [ ] Update `docs/RUNTIME_EXECUTION.md` as the canonical transport/export contract;
  update `docs/ENGINE_INTERFACE.md` for changed capability terminology if needed.
- [ ] Update `ARCHITECTURE.md`, `docs/agent/agent-index.md`, nearest package guides,
  `docs/GUI_WORKFLOW.md`, and the relevant public setup guide after behavior lands.
- [ ] Coordinate the narrower delivered recording choice with the broader recording
  setup plan; do not mark its unimplemented monitor/profile work completed.
- [ ] Record tested vendor versions, fixture identity, checks, residual limitations,
  and physical acceptance evidence. Move this plan to completed only after its agreed
  implementation scope and documented acceptance are fulfilled.

## Verification Matrix

| Area | Required evidence |
| --- | --- |
| Adapter | ASCII framing/range, repeated codes, one send per event, explicit reset policy, invalid port, would-block/error, close and reconnect lifecycle with fakes. |
| Timing hooks | Same compiled frames/order across serial/UDP, warmup exclusion, callback clock origin, no added waits/queues/retries, same-frame collision rejection. |
| Launch policy | Legacy defaults, selected-local precedence, invalid saved choice, production null rejection, Test/Pilot isolation, no fallback. |
| Logs/paths | Full and compact evidence, attempted versus sent, abort/partial export, explicit participant/session association, no raw-file overwrite. |
| GUI | Apply/Cancel, keyboard access, long labels/error states, truthful readiness wording, no clipping, correct device instructions. |
| BioSemi regression | Existing wire bytes, codes, resets, recording prompt, legacy project/bundle round trips, library COM3 policy and schedules unchanged. |
| End-to-end | Actual BDF event reconciliation, 250 Hz Toolbox processing, loss handling, expected FFT/SNR outputs and documented timing qualification. |

Extend existing focused test homes such as `tests/unit/test_serial_trigger_backend.py`,
`tests/unit/test_psychopy_engine.py`, `tests/unit/test_runtime_launcher_flow.py`, and
runtime/export tests. Add the Unicorn adapter tests beside the current backend tests;
avoid duplicating the implementation in assertions. The triggers route currently lists
`test_serial_trigger_backend.py` explicitly: register a new adapter file in
`.agents/verification.toml`, or extend the existing routed file. Run
`./scripts/verify.ps1 -CheckConfig` after changing verification configuration. Register
any new GUI test file in the Qt registry.

Implementation verification routes (run from the Studio repository):

```powershell
./scripts/verify.ps1 -Scope triggers -Tier focused
./scripts/verify.ps1 -Scope runtime -Tier focused
./scripts/verify.ps1 -Scope engine -Tier focused
./scripts/verify.ps1 -Scope gui -Tier focused
./scripts/verify.ps1 -Scope docs -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

Use additional core/project-io routes only when their contracts change. Ordinary
checks must use fakes and safe non-Qt coverage. Qt execution and physical marker
tests require a user-approved safe visible setup; never use offscreen Qt locally.

## Decision And Progress Log

- 2026-09-25: User selected a no-purchase vendor-Recorder route. Paid SDK/custom
  acquisition and alternative transports are outside this plan.
- 2026-09-25: User requested native 250 Hz and no interpolation in the Toolbox profile.
- 2026-09-25: Research and source inspection completed; no recording fixture,
  receiver protocol test, implementation, or physical calibration has been performed.
- 2026-09-25: Saved as planned work with a companion Toolbox plan. Current architecture
  docs remain descriptions of shipped behavior; this plan does not make Unicorn supported.
