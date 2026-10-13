# Studio to Toolbox and OpenFPVS integration

Status: Active

Date: 2026-10-12

## Approved outcome

Studio declares the selected recording hardware, exports completed-session marker
evidence, and prepares a Toolbox config automatically. Toolbox owns raw recording
ingestion, channel validation, analysis and spectral contribution delivery. OpenFPVS
owns private shared-study grants and fixed reporting endpoints. Neither desktop
imports the other application's implementation.

First successful results enrollment shares newly completed eligible sessions by
default; every saved off choice survives enrollment/reconnection. Existing research
records are never backfilled. Server approval is still required. Local recording
remains offline and HTTP is excluded from presentation.

## Studio work and verification

- [x] Core-owned built-in declarations for BioSemi ActiveTwo 64 and Unicorn Hybrid
  Black factory 8, using Toolbox's exact versioned profile/montage/decoder IDs.
- [x] Add declarations to saved recording settings, setup configs and runtime
  evidence. Optional metadata keeps existing config/result envelope versions readable.
- [x] Snapshot the current native config before launch and atomically write a
  completed config after research finalization in full and compact modes. Keep
  aborted/interrupted evidence without a completed artifact.
- [x] Default first enrollment on; atomically preserve saved off choices, including
  an off choice saved while enrollment is in flight.
- [x] Focused profile, completed-session association, abort and preference-race checks.
- [x] Run repo precommit checks and resolve the transient bundle-import test failure.
- [x] Finish synthetic software integration with Toolbox/OpenFPVS without hardware,
  Qt or real researcher data.

The canonical file contract is in
[Runtime execution](../../RUNTIME_EXECUTION.md#completed-toolbox-handoff); the
contribution preference workflow is in [Data sharing](../../DATA_SHARING.md).

Reproduce the hardware-free completed artifacts from the repo root with
`.venv3.10/Scripts/python.exe scripts/verify_studio_toolbox_handoff.py`. The script
compiles native synthetic projects, runs the fake presentation engine through the
normal runtime worker, and writes a manifest plus both completed configs beneath
`build/studio-toolbox-acceptance/<unique-id>/`. It opens no Qt window, sockets or
reporting client.

Each manifest also points to a canonical `SessionReport` built directly from the
actual native completion summary using `build_session_report`, serialized with
the ordinary outbox wire format. Disabled fixation produces zero counts and null
accuracy/RT, rather than invented task metrics. Live dummy-study uploads remain
owned by the separately authorized OpenFPVS workflow.

The acceptance fixture uses 42 oddball cycles (35 seconds) so ordinary endpoint
exclusions retain enough cycles for Toolbox's harmonic neighborhood checks. Each
completed config retains the condition-start marker and all 42 oddball attempts.
The fixture does not relax scientific QC.

Verification on 2026-10-12: the repo precommit suite ran 2,971 passing tests, 11
Windows symlink skips and 20 passing subtests. One unchanged long-path bundle-import
case encountered a Windows access-denied rename; the whole bundle file then passed
all 65 tests, including both long-path cases, without code changes. The final config,
recording and GUI-coordinator files passed 134 tests with one symlink skip. Sharing
service regressions also passed. Ruff, changed-file compilation, mypy across all 235
source files, harness GC, docs hygiene and `git diff --check` passed on the final source.

Local end-to-end acceptance used the native completed manifest
`build/studio-toolbox-acceptance/9afa8befaf8d4d38926b7f459cb30de6/acceptance-manifest.json`.
Both BioSemi and Unicorn proceeded through Toolbox's actual processing, current full
audit and unchanged final QC to accepted CSV snapshots. The local OpenFPVS handlers
accepted two canonical Studio reports and two Toolbox snapshots, preserved exact
retries, denied pending devices, and allowed three approved labs to read shared
summaries and complete six exact-byte CSV downloads. A mismatched protocol was rejected.

Authorized live acceptance also passed through the real Studio
`DataSharingClient.enroll/submit` and Toolbox HTTPS transport on server version
`bcab9c4f-3701-4cd9-b496-75f14e48af45`, for synthetic study
`7cfa432a-3a31-4b46-b699-510ca41f0594`. It accepted the same two Studio reports and two
accepted full-QC Toolbox CSVs. Three approved labs read both data streams and completed
six exact downloads; pending access, exact retries, unapproved-lab 404 and anonymous
401 were verified. All test codes, native devices and browser credentials were revoked
and the synthetic study was completed afterward. No real researcher data was used.

## Acceptance boundaries

Synthetic tests cover selected-profile config round trips, exact event ordering and
session association in both export modes, abort retention, legacy reads and sharing
preference races. They do not qualify Recorder/BDF+ receiver behavior, EEG acquisition,
actual electrode wiring or physical timing. Factory mapping is a declaration.
Unicorn remains native 250 Hz in Toolbox, without resampling or interpolation.

Studio adds no new Cognitive Load preset/category. The authorized desktop release
is tracked separately in [Studio 2.4.5](release-2.4.5.md); this integration plan
retains the manual workflow and hardware qualification items. Existing native
authoring, runtime timing and participant visit ownership remain authoritative.

Visible acceptance remains manual: select each existing Recording choice, launch
a synthetic current session, inspect its completed config, and open it in Toolbox.
Exercise sharing default-on and saved off/reconnection states. Qt is not run here.
