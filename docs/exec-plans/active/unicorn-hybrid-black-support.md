# Unicorn Hybrid Black Recording Support

Status: Active

Created: 2026-09-25

## Current baseline on November 19, 2026

[Studio 3.1.0](../completed/release-3.1.0.md) ships Windows Unicorn Recorder
output for ordinary recording runs. The device is selected in Recording settings.
Studio checks for an active raw Recorder file before launch, then submits ordered
decimal ASCII UDP markers to the selected loopback port. Test and Pilot use null
output. The September 28 decision to allow ordinary launches superseded the
original blanket receiver-validation blocker. Exports still describe receiver
validation as pending. See the [runtime contract](../../RUNTIME_EXECUTION.md#unicorn-recorder-udp-receiver-validation-pending).

Three retained checks establish the current bench evidence:

- September 28, Recorder 1.24.02 (`1.24.2.2760`), vendor test signal. All 426
  sent markers, including codes 1–255 and adjacent repeated codes, matched the
  classic `24BIT` BDF Status channel and parallel CSV. The raw header establishes
  the observed format. Long-run wireless stability and loss detection were outside
  this test.
- November 12, Windows USB Bluetooth bench, Recorder test signal. The finalized
  classic BDF retained all 11 markers from Trigger Tester and a normal Studio
  launch, in exact order. This is the verified visible path on that setup.
- The [offline timing report](../../RUNTIME_EXECUTION.md#unicorn-recorder-timing-report)
  matched 145 of 145 markers with the saved two-minute raw BDF and Studio
  acquisition log. All oddball gaps were 50 frames and the 52,989 samples had no
  counter discontinuities or invalid flags. The nominal BDF span was 115.897 ms
  longer than the Studio callback span. Fullscreen repeats separately
  characterized software cadence. The callback clock, BDF nominal rate and panel
  light are distinct references. The detailed results and limits are in the
  [progress log](#decision-and-progress-log).

Studio's completed-session and whole-study handoffs retain the effective
recording declaration and attempted marker sequence. Current Toolbox source
supports explicit Unicorn processing at native 250 Hz with eight scalp
channels, `average_scalp` reference, sample-wise marker decoding and interpolation
disabled. Generated BDF+ fixtures and the extracted 426-marker bench receipt
cover software compatibility. Live vendor BDF+ and full reviewed processing of an
actual Recorder acquisition remain open. Follow the companion plan in the active
`FPVS-Toolbox` checkout at
`docs/agent/exec-plans/active/unicorn-hybrid-black-support.md`.

## Remaining work and acceptance

1. **Qualify the Recorder and wireless path.** In an approved visible Windows
   setup, use the installed Studio build, supported Recorder, existing Bluetooth
   dongle and nonparticipant recordings. Record the Recorder and Studio builds,
   dongle/driver and power policy, logger settings, format header, signal source
   and raw data hashes. Observe ready, absent, idle, wrong-port, interrupted and
   vendor-disconnect cases. Capture a representative long run across all
   conditions and an interrupted run, with raw BDF and diagnostic CSV when
   available. Check first/last and repeated markers, exact order and sample
   association, and the visibility of gaps through counter/validity signals.
   Retain a real vendor BDF+ fixture if supported and identify its actual format
   from the header. Record proven limits for unobservable loss, unsupported
   formats and wrong-port sends. Record the packaged checks and a BioSemi
   regression for the established serial workflow.
2. **Qualify the Toolbox handoff on actual Recorder files.** Explicitly associate
   the raw recording with the Studio visits/runs. Verify the actual electrode
   labels and reference wiring, raw units and amplitude, recorded sample
   continuity and complete marker reconciliation against the Studio sidecar.
   Run the native 250 Hz, eight-channel, average-reference profile through
   ordinary reviewed processing and FFT/BCA/SNR outputs. Confirm interpolation
   stays disabled and available ROI/QC policies and provenance are explicit.
   Exercise the handling of missing/extra markers, gaps and invalid inputs.
   Retain raw file and handoff identifiers, Toolbox build, QC outcome and expected
   export evidence. Assess classic BDF and continuous BDF+ separately on
   recordings from the supported configuration. Report remaining limitations in
   the Toolbox plan and Studio runtime contract before changing receiver status.
3. **Measure physical timing on the intended setup.** Use an independent
   calibrated reference and existing suitable lab equipment to measure actual
   optical onset against recorded events at the beginning, middle and end of a
   representative session. Set acceptance bounds in advance for the intended
   analysis and highest retained harmonic. Record sign and distribution of
   onset-to-event delay, drift, sample gaps, lost events and display frame
   failures. Retain the setup, reference and calibration evidence. Until this is
   available, physical timing remains unqualified.

Close the plan after the agreed receiver format, wireless loss behavior,
packaged acquisition, Toolbox processing and physical timing gates have recorded
outcomes and the owning contracts reflect the scope supported. Keep receiver
qualification and physical timing status distinct.

## Workflow and ownership

The Windows route uses the existing headset and vendor Recorder. Bluetooth carries
EEG to Recorder. Studio sends markers to localhost and retains launch/acquisition
evidence. Recorder owns raw logging and manual start/stop. The operator associates
the raw recording with the correct visit and confirms electrode mode and montage.
Toolbox owns sample interpretation, marker reconciliation, reference, QC and
analysis provenance. The [Studio–Toolbox integration plan](studio-toolbox-integration.md)
covers cross-product handoff and the [lab-independent setup plan](../planned/lab-independent-recording-setup.md)
tracks broader recording preferences independently.

Keep the authored schedule, one-marker-per-frame rule and external output
capability. The existing adapter pre-encodes codes 1–255 and gives each compiled
callback one nonblocking submission. The runtime retains attempted, accepted and
failed output and the run-relative callback clock in both export modes, including
interrupted runs. Recorder readiness describes observed file growth at launch.
Verified receipt requires the saved recording. The BDF remains the raw EEG and
recorded-event authority. Toolbox uses reviewed recording association and preserves
the source samples and marker indices.

The existing no-purchase decision uses the vendor application and standard-library
UDP. The stock Fz, C3, Cz, C4, Pz, PO7, Oz and PO8 mapping is a declaration to
verify on the actual recording. Studio keeps the raw callback clock and sends
promptly. If a qualified measurement later supports applying a constant shift in
Toolbox, retain the calibration, signed offset, sample rounding and residual
alongside the original indices. A constant shift cannot repair jitter, drift or
missing data.

## Evidence pointers and verification

The original review on September 25 used Studio `6c95178`. The
[Recorder manual](https://github.com/unicorn-bi/Unicorn-Recorder-Hybrid-Black/blob/main/README.md)
describes raw logging and ASCII UDP. The
[vendor FAQ](https://www.gtec.at/unicorn-faq/) covers the Suite release and
licensing. The
[hardware manual](https://github.com/unicorn-bi/Unicorn-Suite-Hybrid-Black-User-Manual/blob/main/UnicornHybridBlack.md)
describes the stock cap. [PsychoPy timing guidance](https://psychopy.org/general/timing/millisecondPrecision.html)
distinguishes software timing and physical onset. Use the retained fixtures and
reports below to document the observed behavior of a specific Recorder build.

Use the `triggers`, `runtime`, `engine`, `gui` and `docs` focused verification
scopes for changed Studio behavior, and safe `repo` precommit for cross-layer
changes. Keep fake output in automated checks. Use the [Trigger Tester smoke path](../../GUI_WORKFLOW.md#trigger-tester)
and normal launch for approved visible acceptance. Check late failure and abort
evidence in full and compact exports, Test/Pilot isolation, and existing BioSemi
behavior. Add project I/O checks when its contract changes, and run `-CheckConfig`
after changing verification routing. Actual Recorder, Toolbox and timing evidence
follows the acceptance sequence above.

## Decision And Progress Log

The dated entries preserve the observations and decisions at the time. The current
baseline and acceptance sequence above replace their original launch and release gates.

- 2026-11-19: Windows source verification at `313f0bd` passed 379 tests with one
  Windows symlink-privilege skip. Checks covered fake UDP output and Recorder
  readiness, Test/Pilot isolation, marker and failure evidence in runtime exports,
  synthetic BDF and offline timing cases, and completed-session and whole-study
  handoffs. Two separate visible Windows Qt Trigger Tester cases passed for
  the saved UDP endpoint and explicit digit sends with fake output. At Toolbox
  `84ac8656`, four offline checks passed. The retained
  receipt and a generated classic-BDF replay preserved all 426 code/sample pairs,
  including four adjacent equal-code pairs. Synthetic classic BDF and continuous
  BDF+ agreed where both marker sources were represented. The original raw bench
  files were unavailable at the documented local locations, so the 145-marker
  timing comparison was not rerun. Receiver loss, reviewed Toolbox processing
  of actual Recorder files and optical timing remain open.

- 2026-11-12: On the built-in Lenovo display, same-PC PsychoPy 2026.1.1
  fullscreen repeats ended 37.790 and 36.478 ms early over 120 s. A minimal
  PsychoPy 2026.2.5 loop ended 37.233 ms early, and 7,200 Windows kernel
  vertical-blank intervals ended 37.323 ms early. The driver labels the mode
  `60/1`; its configured 138.700 MHz pixel clock and 2,080 × 1,111 scan totals
  imply 60.020425 Hz. The alternate 48 Hz Studio repeats ended 12.643 and
  11.831 ms late. The driver retained the original clock when asked to apply
  a corrected 60 Hz mode. Restored the original 1920 × 1080 / 60 Hz display
  configuration after the trials. The current software endpoint target is
  ±1 ms over 120 s. The built-in modes remain outside it. Record native
  signal timing as diagnostic evidence alongside the nominal mode and PsychoPy
  observation. Physical timing remains unmeasured.

- 2026-11-12: Repeated the 6 Hz / 1.2 Hz software timing check in fullscreen twice
  on the same fixed `60/1` Windows display mode. Windows listed no higher progressive
  mode at the active resolution. Each run completed 7,200 frames, and the local test
  receiver saw one code `1` followed by 144 codes `55`. The repeats used software
  timing only. Measured stream durations were 119.963301 s and 119.962986 s,
  respectively 36.699 ms and 37.014 ms ahead of the 120 s compiled duration. The
  software-observed refresh rates were 60.018355 Hz and 60.018513 Hz. Mean oddball
  flip periods were 833.068499 ms and 833.075278 ms. The longest measured
  frame was 22.3004 ms and 21.9711 ms, respectively, with no interval above
  25 ms. The marker callback and corresponding flip spans differed by at most
  0.006 ms. The repeated fullscreen observations support a stable software timing
  offset for this setup. Panel-light timing and EEG clock calibration remain open.
  Added [playback cadence reporting](../../RUNTIME_EXECUTION.md#playback-cadence-reporting)
  to retain this evidence independently of single-frame timing QC in both export modes.
  The fixed 6 Hz / 1.2 Hz target remains the analysis reference. The requested
  physical drift limit of 0.1 ms over 120 s is about 0.83 ppm. The setup still
  needs optical qualification against an independently calibrated reference.

- 2026-11-12: Ran the offline timing report on the saved two-minute 6 Hz / 1.2 Hz
  Recorder BDF and Studio acquisition log. All 145 sent markers matched in order
  (one code 1 and 144 code 55), all oddball callback frame gaps were 50, and the
  52,989 saved samples had zero CNT discontinuities and zero invalid flags. From
  code 1 to the last 55, Studio callbacks spanned 119.796103 s, 37.231 ms shorter
  than the corresponding 60 Hz reference frame span. The nominal BDF span was
  119.912000 s, 115.897 ms longer than the callback span. The fit gave an apparent
  250.246909 samples/s relative to Studio, with 1.258 ms RMS residual. The Markdown
  report stays with local bench evidence and both input hashes were unchanged.
  The acquisition log has marker callbacks only, so per-frame and optical timing
  remain unverified.

- 2026-11-12: Studio 3.0.1 source with Trigger Tester commit `e22b664` and Unicorn
  Recorder 1.24.02 (1.24.2.2760) passed a Windows bench test. The operator completed
  pairing through the CSR8510 A10 USB dongle with internal Bluetooth disabled after
  earlier authentication failures. Recorder acquired its built-in test signal and
  accepted UDP on `127.0.0.1:1000`. Trigger Tester sent `1, 9, 5, 5` using its buttons
  and keyboard. A normal 300-frame Studio run passed Recorder readiness and logged
  condition-start code `42` followed by six oddball codes `55`. The finalized classic
  BDF (`24BIT`) contained all 11 events in its `Status` channel in exact order, with
  zero extra nonzero samples. The BDF contained 45,563 samples at 250 Hz. The raw BDF,
  marker comparison and Studio acquisition log were retained locally. This bench run
  leaves long-run Bluetooth stability, participant EEG quality, BDF+/Toolbox
  interchange and display-to-EEG timing open.
  Raw BDF SHA-256 `b6bc4388e2301ebba498776c789ea45f59889fe00b2f4b35cd5015d5d1fdc7c0`.

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
