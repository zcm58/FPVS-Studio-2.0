# Unicorn Hybrid Black Recording Support

Status: Active

Created: 2026-09-25

Implementation selected on 2026-09-28, initially with production validation pending.
After the retained 426-marker Recorder test, the user requested normal FPVS Studio
launches to perform real hardware tests. That decision supersedes the initial blanket
receiver-qualification launch gate: normal Unicorn launches now send real markers after
configuration and automatic Recorder readiness checks pass. Full receiver, BDF+/Toolbox
and physical timing qualification remain pending; exports retain that evidence state.
Automated verification uses fakes. Hardware and timing acceptance remain separate from
software checks.

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

The later 2026-09-28 launch decision enables the existing normal workflow, without a
new test mode, bypass preference or manual approval. Experiment Test Mode and Pilot
Study Mode remain no-output workflows. The synthetic fixture verifies classic BDF
and CSV marker retention; it does not resolve the original BDF+ interchange requirement
or qualify participant data, Toolbox processing or physical timing.

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

The existing [lab-independent recording setup plan](../planned/lab-independent-recording-setup.md)
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
range and rates in retained receiver tests and qualify the recording before accepting
study data. Normal launch output remains available for these recording tests. Do not
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
5. After Launch Experiment, Studio's launch worker automatically checks that Recorder
   is open and writing raw BDF before presentation. No manual recording checkbox is
   required. This does not establish correct participant association, electrode mode,
   received markers, data integrity, or receiver/physical-timing qualification.
6. Run the unchanged experiment. Recorder remains responsible for continuous acquisition.
7. Stop Recorder manually, register its BDF+ in Toolbox, and reconcile recorded markers
   with Studio's event evidence before treating the recording as accepted data.

The launch check is scoped to the Recorder process and fresh writes to its configured
raw file; unreadable/ambiguous states fail closed. Do not infer headset connection,
electrode mode, ongoing recording after launch, or UDP receipt from that observation.
An optional operator-invoked marker test must be clearly identified and
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

Qualification criterion: known recorded-marker semantics and a usable raw-file contract.
Fakes can support parallel adapter development, but do not establish qualification.
This criterion does not block the normal launch workflow used to collect real test
evidence. Unsupported firmware/software or undiscoverable loss must be reported explicitly.

### Phase 1 - Runtime Selection And UDP Adapter

- [x] Add the narrow local configuration, legacy precedence, and validation.
- [x] Implement a focused `triggers/` adapter using standard-library sockets only.
- [x] Update factory, capability checks, transport labels, and backend-specific errors.
- [x] Preserve BioSemi single-byte output and test/pilot null behavior.
- [x] Exercise failures with fakes; no automated test opens real hardware or sends
  network markers to a potentially active Recorder.

Gate: exact encoded output, one submission per scheduled event, and deterministic
failure/cleanup behavior with unchanged scientific schedules.

### Phase 2 - Recording Workflow And Durable Evidence

- [x] Add shared-component settings/run controls and appropriate Recorder instructions.
- [x] Capture runtime configuration snapshots; retain optional explicit operator
  metadata without treating automatic readiness as human confirmation.
- [x] Export handoff evidence in full and compact modes, including partial/aborted runs.
- [x] Preserve cancellation, participant visit reservations, path invariants, and
  historical export readability; version any additive acquisition metadata.
- [x] Add registered GUI coverage and document visible acceptance at the existing
  main-window/settings minimum sizes; if Setup changes, all eight steps still fit 1120x820.
- [x] Register any new adapter test file in the explicit triggers verification route;
  run the harness configuration check if `.agents/verification.toml` changes.

Gate: an operator can prepare, run, abort, and identify the correct recording without
editing project files, and exported evidence never overstates acquisition readiness.

Software paths above are covered with fake output. The automatic Recorder readiness
check runs in the launch worker before visit reservation and presentation. A valid
configuration and passed readiness check allow the normal Unicorn launch to emit
markers, with qualification still recorded as pending. GUI layout acceptance remains
separate; checked implementation tasks do not establish those acceptance results.

### Phase 3 - Toolbox Integration And Timing Qualification

- [ ] Run a full recording through the companion Toolbox plan: native 250 Hz,
  interpolation off, explicit reference/ROI/QC policy, event reconciliation and spectra.
- [ ] Reconcile the expected and actually recorded code sequence across all conditions
  and runs; missing or extra markers must be surfaced, not reconstructed silently.
- [ ] Exercise Recorder absent/not recording, wrong port, vendor disconnect, missing
  samples, and interrupted sessions using controlled test data/setup.
- [x] Explicitly defer physical timing qualification; no measurement evidence is available.
- [ ] Verify the packaged Studio works without UnicornPy/vendor DLL bundling or added
  purchases; test BioSemi installation/workflows for regressions.

Gate: complete normal-workflow integration plus an explicit timing qualification state.
No claim of BioSemi timing or spatial equivalence follows from this feature alone.

### Phase 4 - Documentation And Handoff

- [x] Update `docs/RUNTIME_EXECUTION.md` as the canonical transport/export contract;
  update `docs/ENGINE_INTERFACE.md` for changed capability terminology if needed.
- [x] Update `ARCHITECTURE.md`, `docs/agent/agent-index.md`, nearest package guides,
  `docs/GUI_WORKFLOW.md`, and the relevant public setup guide after behavior lands.
- [x] Coordinate the narrower delivered recording choice with the broader recording
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

- 2026-09-30: User selected the minimal Home launch-text indicator, with
  `Recording Device: BioSemi ActiveTwo` and
  `Recording Device: Unicorn Black Mobile Headset`. Home's display-name map is the
  extension point for future supported backends; this adds no new recording backend.
  Transport/endpoint and Recorder-check details remain in the tooltip and accessible
  description. Run's output summary, Test/Pilot no-marker text, invalid-configuration
  messages and launch checks retain their existing behavior. Registered visible Qt
  coverage includes both themes at `1120x720`, incomplete/ready projects, configuration
  changes, no-output modes and a long future display name. Local Qt execution remains
  opt-in; the visible acceptance route is in `docs/GUI_WORKFLOW.md`.
  Validation: focused GUI checks passed seven tests; Ruff, compilation, mypy across
  212 source files and repository/docs audits passed. The non-Qt precommit suite
  had 2,407 passes, 11 Windows symlink skips and two failures in unchanged Windows
  named-pipe/file-lock tests. Both affected modules passed outside the sandbox on
  targeted rerun (16 passed, one symlink skip). Registered Qt checks were not run.

- 2026-09-29: Prepared the Unicorn implementation for the requested remote push,
  rebasing onto the existing 2.2.1 release commits and preserving the newer BioSemi
  serial-port error. Corrected stale Settings guidance that still claimed normal
  Unicorn launches were blocked; the registered Qt test covers the current wording.
  Replaced a synthetic user-directory test path with `tmp_path`. All changed Python
  files passed Ruff and compilation; mypy passed 212 source files, repository/docs
  audits and verification configuration passed, and safe GUI checks passed seven tests.
  Focused runtime checks passed 529 tests with two Windows symlink-privilege skips.
  The full non-Qt precommit suite had 2,408 passes, 11 symlink skips and one unchanged
  serialization test failure after an extra Windows file-lock retry; all eight
  serialization tests passed on isolated rerun without changes to that implementation.
  Registered Qt and physical timing checks were not repeated. Local recordings and
  untracked `output/` remain outside the commit; timing qualification remains pending.

- 2026-09-28: Read-only comparison with the user's BioSemi `MCCTR/p74.bdf`
  found six blocks of 146 oddball-55 pulses each (876 oddballs total), at declared
  2,048 Hz. Low-16-bit pulse onsets were counted once; 16-17-sample pulse widths
  and upper acquisition-status bits were excluded from event counting. All block
  endpoint rates were 1.199998384-1.200008082 Hz, corresponding to -0.808 to +0.162 ms
  difference from nominal 1.2 Hz when normalized to 120 seconds; fitted rates also
  implied less than 1 ms per 120 seconds. The Unicorn file's equivalent endpoint
  difference was +115.726 ms by the same nominal-rate method. Individual BioSemi
  intervals varied, but did not show the comparable accumulated discrepancy.
  BioSemi presentation logs were not supplied, so this is a comparison against
  nominal 1.2 Hz across different recordings/setups, not a controlled hardware
  comparison or EEG-frequency/physical-onset qualification. Original files were
  unchanged; independent Status-only decoders agreed.

- 2026-09-28: Diagnosed a false idle report after the user changed Recorder's live
  raw folder and filename prefix. Its saved configuration still described the old
  output because Settings applies changes in memory and only closing Recorder saves
  them. No supported live raw-logger query was found. Missing-output diagnostics now
  describe inability to verify using saved settings, include the checked folder/prefix
  when available, and prioritize the stop/close/reopen recovery. Acceptance still
  requires the configured raw file's exact Recorder ownership and two growth checks;
  no guessed-path fallback, recording control, or raw-data modification is added.
  A Recorder restart after changing raw logging settings remains required.
  The user's subsequent Recorder restart persisted the new folder/prefix, and the
  unchanged live probe returned `recording` against the new process. No Studio
  restart was required for that recovery; source diagnostic changes load on its
  next restart. Baseline runtime checks passed 502 tests with two Windows symlink
  skips outside the sandbox; the sandbox's named-pipe permission failure was
  environmental. Documentation checks passed nine tests.
  The diagnostic-only patch passed 56 targeted readiness tests and Ruff; a later
  read-only native invocation returned `not_running` after Recorder had closed.
  Full precommit was not repeated during the user's timing experiment. Acceptance,
  marker output, and presentation scheduling were unchanged.

- 2026-09-28: Compared the user's longer finalized `Studio_Test_28_09_2026_17_36_07.bdf`
  in Desktop/Unicorn Data with its Studio trigger/frame logs. All 148 sent markers
  matched in order (one condition-2 marker and 147 oddball-55 markers); the saved
  sample counter was continuous and validity was set throughout. The BDF contains
  42,338 samples at declared 250 Hz (169.352 seconds). The 146 oddball intervals
  spanned 121.784 seconds in BDF sample time, versus 121.665690 seconds in Studio's
  callback clock: endpoint rates 1.198843855 and 1.200009633 Hz respectively, a
  118.31 ms increase in relative offset. This exceeds sample quantization alone.
  All oddball frame gaps were 50; the completed condition had 7,350 frames with
  mean software-observed refresh 60.000465 Hz and no frame exceeding 25 ms.
  The next condition was aborted before playback; its 59.997365 Hz preliminary
  estimate must not be attributed to the completed condition. Read-only Windows
  and EDID queries identified a Dell P2422H at 1920x1080 with configured 60/1 Hz
  timing. A hypothetical 59.997 Hz would imply 1.19994 Hz and only 6.08 ms extra
  across these intervals, not the observed difference. These data support a
  mismatch between the computer and recording timelines, not a physical clock
  calibration or a proven cause. No display settings or timing compensation changed.
  The companion raw CSV matched all marker sample locations. Bounded inspection of
  the installed vendor implementation showed that DT measures acquisition-loop
  intervals with a stop/start gap, so summing DT is not an independent elapsed-time
  reference. Recorder's trigger stage uses a separate running Stopwatch and buffered,
  smoothed sample timestamp assignment. That provides a possible receiver-side
  mechanism, but does not isolate it from clock-rate differences or prove the cause
  of this measurement. Neither DT nor this inspection justifies a timing correction.

- 2026-09-28: The user requested real hardware testing through the ordinary Studio
  launch workflow. Removed the blanket receiver-qualification launch blocker while
  preserving configuration validation, automatic Recorder process/raw-file readiness,
  serial behavior and Test/Pilot null output. Normal Unicorn launches now send to
  the configured loopback port, initially 1000; there is no new validation mode,
  bypass setting or manual approval. The retained 426-marker classic-BDF/CSV fixture
  remains limited receiver evidence. BDF+ interchange, Toolbox reconciliation, loss
  handling, packaged acceptance and physical timing remain pending, as does exported
  `receiver_validation`. Earlier dated gate decisions below are implementation history
  and are superseded by this launch policy.
  Verification: real runtime/preflight/export paths with simulated hardware passed;
  runtime focused 502 passed/two Windows symlink skips, triggers 59 passed, safe GUI
  seven passed, docs nine passed and harness configuration valid. Precommit passed
  Ruff, compilation, mypy and audits; 2,381 tests passed with 11 symlink skips and one
  unrelated library-import WinError 5 rename failure, which passed on isolated rerun.
  Registered Home/Run success and failure GUI tests were updated but not run locally.
  No real markers or participant presentation were started by automated verification.

- 2026-09-28: Refined launch errors to distinguish Recorder closed, no active raw
  recording found, and an owned raw recording file with no new writes. The last two
  include headset power/connection guidance without claiming an independently
  detected headset disconnection. Inspection failures retain separate messages.
  Targeted runtime tests passed 80 with one symlink skip; PowerShell parsing and
  docs checks passed. Precommit lint/type/audits passed; its suite passed 2,377 with
  11 skips and two unrelated library rename WinError 5 failures, both passing on
  targeted retry without source changes. Registered GUI checks now use the actual
  runtime errors for all four states on Home/Run; Qt execution remains unrun.

- 2026-09-28: User requested only an automatic open/recording check after Launch
  Experiment and before presentation. Replaced the prepared manual Unicorn confirmation
  with a shared background runtime check; preserve the separate receiver-qualification
  gate and Test/Pilot isolation. This Recorder styles its Record button rather than
  exposing a reliable recording-state flag, so the check uses the process and fresh raw
  file writes. Live checks correctly rejected the open/stopped Recorder and accepted
  active recording twice (about 2.9 seconds each). Recorder's saved XML declares Unicode
  despite UTF-8 bytes; the reader now handles the vendor's text-file encoding. A later
  check rejected Recorder again after fresh writes stopped. Static inspection confirms
  configuration saves only on window close; recovery messages explain closing/reopening
  after logging-setting changes. Runtime focused verification passed 499 tests (two
  Windows symlink skips); GUI safe checks passed seven tests, docs nine, and config
  validation passed. Final repository precommit passed Ruff, compilation, mypy and
  audits with 2,378 tests passed and 11 Windows symlink skips. Registered Qt tests
  were updated but not run; full visible Home/Run launch, acquisition-only and
  minimized-window checks remain unverified. No markers were sent in readiness checks.

- 2026-09-28: Actual receiver test completed after the user had an administrator
  disable Intel Bluetooth. Suite identified CSR8510 A10 as the recommended adapter
  and the headset connected. Recorder 1.24.02 (1.24.2.2760) acquired its synthetic
  test signal with CNT, VALID and DT; raw BDF and parallel raw CSV were enabled.
  Studio's actual source `UnicornUDPBackend` submitted 426 ASCII datagrams to local
  port 1000, outside the ordinary GUI/production launch gate. All 426 markers were
  present in exact order in both files, including every code 1-255 and 32 consecutive
  repetitions of 55. Counts by phase: known/boundary 11, full range 255, repeated 55
  32, nominal 60 Hz 64 and nominal 120 Hz 64. BDF/CSV trigger values match at every
  sample. The 22,621-sample recording is 90.484 seconds at 250 Hz; CSV CNT increments
  by one throughout and VALID is always 1. Two independent decoders agreed.
- 2026-09-28: Receiver semantics/format findings: this build writes classic BDF
  (`24BIT` reserved header, no BDF+ annotation channel), despite the BDF+ wording
  in vendor documentation. The BDF signal is `Status`, with identity numeric scaling;
  GUI and CSV call it `TRIG`. Each nonzero sample matched one sent event in this
  fixture. Adjacent nonzero samples can carry distinct events, including identical
  55s: there are 426 events but only 422 contiguous nonzero value runs. No reset
  datagrams were sent. Edge-only or run-collapsing import would lose repeated events.
  Nominal fast phases used OS sleeps and include catch-up bursts, so this is no
  display/physical-timing qualification. BDF header time (12:42:48) is about the file
  duration later than filename time (12:41:18); absolute start-time semantics remain
  unresolved. Dongle power saving remains enabled. Aborts, deliberate loss, long-run
  integrity, Toolbox import, BDF+ requirement and physical timing remain pending;
  the production gate is unchanged.
- 2026-09-28: Retained raw fixtures, sender, independent decoder, reports and SHA-256
  manifest under `%USERPROFILE%/Documents/FPVS Studio Diagnostics/Unicorn/2026-09-28-2bce2ff1/`.
  Recorder is stopped. Its Suite Open button silently failed because Suite always
  roots the executable path under Program Files. Direct launch from the existing
  per-user installation succeeded; added a `Unicorn Recorder` desktop shortcut.
  No vendor binaries, drivers, cached tool definitions or production code were changed.
- 2026-09-28: Follow-up driver audit confirmed the dongle already uses Microsoft's
  inbox `bth.inf`, version 10.0.26100.9444, signed by Microsoft Windows, with an
  exact `USB\\VID_0A12&PID_0001` hardware match marked Best Ranked / Installed.
  System BTHUSB event 6 explicitly reported that only one active Bluetooth adapter
  is supported at a time. No additional driver package was needed or installed.
  At the user's request to use the dongle without administrator privileges, attempted
  the documented Intel PnP disable using a verified non-administrator token. Windows
  rejected it with `HRESULT 0x80041001` / Generic failure. No UAC elevation was used.
  The supported adapter switch requires administrator intervention; user-level
  driver installation or a Recorder setting cannot substitute for this device change.
- 2026-09-28: Retried receiver validation after the user powered the headset on
  and inserted its USB Bluetooth dongle. Suite discovered the headset, but pairing/
  connection did not persist and Recorder acquisition could not start. Windows
  reported `Generic Bluetooth Radio` problem code 31; the active Intel Bluetooth
  adapter reported code 0. Suite explicitly identified Intel as the selected,
  nonrecommended adapter with power saving enabled. No marker was sent to Recorder
  and no receiver fixture was captured. Vendor guidance requires disabling the
  internal Bluetooth adapter before reinserting the Unicorn dongle; changing device
  state requires administrator access and can interrupt other Bluetooth peripherals.
  No drivers, adapter settings or production gates were changed. Resume after the
  dongle is healthy and Suite identifies the recommended adapter.
- 2026-09-28: Installed Suite 1.24.00 BETA 2621 and Recorder 1.24.02
  (file version 1.24.2.2760) per-user without administrator privileges. The user
  requested synthetic marker validation, then confirmed no headset is available
  and deferred connecting it until a later session. Vendor documentation requires
  a paired/connected device even for test-signal acquisition; Recorder receipt and
  raw BDF/CSV reconciliation remain pending. The installed vendor UDP example uses
  decimal ASCII without zero resets, consistent with Studio's adapter.
- 2026-09-28: An explicitly requested manual transport check used the actual
  `UnicornUDPBackend` and a temporary real UDP listener on an OS-assigned loopback
  port, separate from Recorder port 1000. All 426 datagrams matched expected ASCII
  payloads and order: known codes/boundaries, the full 1-255 range, 32 consecutive
  code-55 markers, and nominal 60/120 Hz sequences. Reset emitted no extra datagram.
  Pacing used OS sleeps, not display flips. This verifies local transport only;
  it provides no Recorder, EEG sample, BDF, loss-detection or physical-timing evidence.
  The manual report is retained locally at
  `%TEMP%/fpvs-unicorn-loopback-9b8tiumn/transport-results.json` (SHA-256
  `5a8cf01be5d2d66990e4765331ae7f2415a59b8c3c44e6131c2d9b3672928813`).
  Focused trigger verification also passed all 58 tests. No production gate changed.
  Resume with a separate test-signal recording, UDP input on 127.0.0.1:1000,
  raw BDF+ and parallel raw CSV, then compare saved STATUS events against the actual
  sender sequence, including repeated codes, boundaries and first/last events.

- 2026-09-28: Final repo precommit passed: changed-file Ruff and compilation, mypy
  across 210 source files, repository/docs audits, and 2,330 non-Qt tests. Eleven
  tests skipped because this Windows account cannot create symlinks. No Qt window,
  physical trigger validation, vendor recording, Toolbox integration or packaged-build
  acceptance was performed. No runtime dependencies or vendor binaries were added.

- 2026-09-28: Implemented local preferences and staged Recording Setup, shared launch
  gates, a nonblocking ASCII adapter, external-marker capability with serial
  compatibility, explicit Test/Pilot isolation, and versioned acquisition snapshots.
  Candidate handoffs are retained under project `logs/acquisition/` in both export
  modes. Orderly send, presentation, cleanup and export failures preserve attempt
  evidence; abrupt process loss may omit the current run. Settings and launch controls
  have registered visible Qt coverage at their documented sizes, not locally executed.
  Canonical behavior and manual acceptance live in Runtime execution and GUI workflow.
  Receiver fixtures, Toolbox reconciliation, packaged acceptance and physical timing
  remain pending; the plan stays active and production cannot be enabled by a preference.
- 2026-09-28: Focused checks passed: triggers 58, engine 336, runtime 450 with
  2 Windows symlink-privilege skips, safe GUI route 7, safe document behavior 20,
  and docs 9. Harness configuration passed all 13 scopes. The pre-existing sandbox
  named-pipe failure passed with the safe runtime suite outside the sandbox.

- 2026-09-28: Pulled Studio `master` from `6c95178` to `237c7bc`, reviewed this
  plan, and began its software implementation. User explicitly selected production
  validation pending; no receiver fixture or qualified vendor build is available.
  The local Toolbox checkout does not contain the named companion plan, so the
  versioned Studio handoff remains a candidate pending cross-application validation.
  Initial trigger verification passed all 23 tests.
- 2026-09-28: Rechecked the vendor Recorder manual's ASCII datagram example and
  distinct raw BDF+ logger. These support implementation framing, but provide no
  fixture evidence for the installed receiver, marker repetition, code range or
  acquisition sample timing. The named companion plan is also absent from the local
  Toolbox `origin/main` ref; this task does not modify or pull that other checkout.

- 2026-09-25: User selected a no-purchase vendor-Recorder route. Paid SDK/custom
  acquisition and alternative transports are outside this plan.
- 2026-09-25: User requested native 250 Hz and no interpolation in the Toolbox profile.
- 2026-09-25: Research and source inspection completed; no recording fixture,
  receiver protocol test, implementation, or physical calibration has been performed.
- 2026-09-25: Saved as planned work with a companion Toolbox plan. Current architecture
  docs remain descriptions of shipped behavior; this plan does not make Unicorn supported.

- 2026-09-30: User requested urgent per-project device persistence. The 2.2.3 fix
  saves typed device/port settings in ProjectSettings, ignores the former global
  override, and preserves existing serial fields, compiled timing and readiness checks.
  Software acceptance and publication are recorded in
  [the completed 2.2.3 plan](../completed/project-recording-2.2.3.md).
