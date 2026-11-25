# Studio to Toolbox and OpenFPVS integration

Status: Active

Date: 2026-10-12

## Recorder and cap handoff

Studio's Recording settings can declare the cap used with a recorder. The
[exchange contract](../../PROJECT_CONFIG.md#recording-system-and-electrode-montage)
covers setup import, completion and the per-visit study declaration. Source
validation covers the named ActiveThree and actiCAP layouts, the retained
Unicorn factory declaration, and older visits without a selected cap. Tests
check that mismatched setup and captured declarations fail and that a later
project edit cannot supply a missing historical montage. Installed acceptance
should compare the montage displayed after importing a setup and a completed
study against the cap originally selected in Studio.

## Current baseline on November 19, 2026

[Studio 3.1.0](../completed/release-3.1.0.md) ships the whole-study handoff and
the local collection workflow. Studio retains each visit's acquisition evidence
and exports a completed study on request. Setup and completed-session exports
remain supported. The matching Toolbox source reviews the roster against one EEG
folder, applies revisions to the same study, prepares reviewed recordings, and
can publish a lab-specific output snapshot. The installed Toolbox build needs
its own compatibility check. OpenFPVS owns study permissions, collection status
and separate lab results. The desktop releases and the website deploy
independently. See the [Studio exchange contract](../../PROJECT_CONFIG.md) and
[Toolbox cohort implementation](https://github.com/zcm58/FPVS-Toolbox/commit/c77086df).

First successful results enrollment shares newly completed eligible sessions by
default. Every saved off choice survives enrollment and reconnection. Existing research
records are never backfilled. Server approval is still required. Local recording
remains offline and HTTP is excluded from presentation.

The November 19 production D1 check for Worker `fpvs-studio-library` found both
collection migrations absent from the applied migration history and neither
`study_rosters` nor `study_collection_leads` in the schema. The October synthetic
report and snapshot acceptance below predates the collection/roster workflow.
The sibling `OpenFPVS/INTEGRATION_PLAN.md` owns its deployment and live acceptance.

## Windows source verification on November 19, 2026

Studio `313f0bd` and Toolbox `84ac8656` passed a paired synthetic transfer.
The Studio runtime with a stub renderer and marker transport wrote a 30-visit
study. Toolbox proposed 28 clear matches, one ambiguous visit and one missing
visit. After resolving the ambiguity and deferring the missing visit, Toolbox
selected 29 recordings for processing. Reopening preserved the decisions and
replaying the export left `project.json` byte-identical.

Studio retained the study identity across reopen and required a reason for an
in-place protocol edit. The next export added one method-compatible visit.
Preview left the Toolbox manifest unchanged. Applying and reopening the new
revision preserved the prior decisions and added the new recording to the
selection. Replaying it left the manifest byte-identical again. A later
cycle-count change blocked a mixed-version selection before any write. A
separate Studio copy received a new study identity. Standalone Setup and
completed-session files also imported and reopened. The official
`scripts/verify_studio_toolbox_handoff.py` run produced BioSemi and Unicorn
completed files and canonical session reports with 43 simulated marker attempts
per visit. Toolbox imported both completed files.

Studio passed 68 focused handoff, project version and collection tests. Toolbox
passed 206 focused import, cohort and results-sharing tests. These include
explicit handling of a previously reviewed visit omitted from a later roster,
archived output for the 20-visit result, and a new release for 21 visits.
The Windows source smoke exercised review and batch selection with synthetic
filenames. Separately, Toolbox decoded all 43 markers from a generated 256 Hz
BioSemi BDF built from one visit's exported schedule, preprocessed the recording,
and wrote a spectral result using the imported protocol. The installed batch and
production result-release workflow remain in the acceptance steps below.

The broader Toolbox project-I/O route reported 1,353 passes and 14 skips.
Its manifest-write recovery test exceeded the 20-second wait for a spawned
process on the full run and passed on an isolated rerun.

OpenFPVS `03fa4f3` passed 82 local Results tests and 42 analysis-snapshot and
processed-results tests. Fresh local Workerd and D1 applied both collection
migrations. The checks cover session intake, revocation, separate labs and
protocols, exact receipt retries, and collection closure and reopening. Reviewed
roster revisions and CSV-backed visit coverage drove per-lab analysis status.
Snapshot reads respected lab scope and revocation, and revisions preserved the
published parent. The site and installed applications still need the linked
production study below.

## Remaining work and acceptance

1. **Verify the installed Studio–Toolbox pair.** Record the exact builds and
   verify Studio's completed-project review and export, same-study identity across
   reopen and in-place protocol change with a recorded reason, and a new study
   identity for a separate copy. Check that quit during an active website export
   preserves local results. In Toolbox, import a synthetic roster, select the EEG
   folder once, and confirm the proposed matches. Resolve one ambiguous recording
   among 30, defer a missing visit, and run an accepted batch. Cancel and then apply
   a revised roster and reopen it after restart. Verify unchanged matches and prior
   outputs are retained, an omitted reviewed visit requires explicit resolution,
   replaying the same revision adds nothing, and scientific incompatibility blocks
   the batch. Check setup and single-session import on the same Toolbox build.
2. **Roll out the website changes in the owning repository.** Under the separate
   website release workflow, apply `0035_study_collection.sql` and
   `0036_collection_lead_revocation.sql`, deploy the matching Worker, then verify
   the live schema, permitted routes and denied access. Record the migration and
   Worker versions in the OpenFPVS plan.
3. **Run a synthetic three-product study in production.** Verify close by the
   administrator or an authorized lead, reopen by the administrator or a
   participating lab PI, and denial for a revoked lead or unrelated lab. Exercise
   held reports, offline/reconnect, duplicate submission and a concurrent reopen.
   Check sharing default-on and saved-off behavior. Grow the cohort from 20 to 21
   and confirm the existing lab snapshot remains readable during collection and
   after closure while the site shows **Analysis needs updating**. Publish an
   eligible revised Toolbox result, then verify **Analysis complete**, the expected
   coverage and separate lab results and downloads. Keep versioned receipts with
   the synthetic study and record cleanup of its temporary credentials.

The workflow closes when the installed pair passes the supported local transfers
and a deployed synthetic study passes the linked permissions, roster revision and
snapshot checks. Record physical acquisition evidence separately for each supported
device, including actual montage/reference, marker order and sample alignment, and
independent timing where required. The [Unicorn plan](unicorn-hybrid-black-support.md)
tracks Recorder and native 250 Hz qualification.

## Implementation and historical verification

### Earlier setup and completed-session exchange format, authorized 2026-11-10

This slice replaces feature-selected config envelope revisions with one shared
Studio–Toolbox handoff format. Setup and completed-session exports use document
kinds within that format; the producer application/version is separate provenance.
Historical 1.x configs remain readable through explicit normalization. Internal
project, RunSpec, SessionPlan, acquisition-evidence and scientific method versions
retain their existing responsibilities.

- [x] Define the stable envelope and optional descriptive metadata boundary.
- [x] Emit one current format from setup, completed and retained-handoff export
  paths; preserve exact launch snapshots and source identity checks.
- [x] Normalize historical configs into the current model and restore authored
  projects by content, without treating an exchange revision as a project version.
- [x] Verify shared producer fixtures in Studio and Toolbox, including completed
  metadata/electrodes, unsupported scientific semantics and unknown revisions.
- [x] Update contracts and complete focused, precommit and documentation checks.

The canonical [config contract](../../PROJECT_CONFIG.md) owns the format policy;
`core/project_config_legacy.py` isolates frozen historical checks. Strict MkDocs,
documentation hygiene and changed-document relative-link checks pass; the
docs-focused driver passed 13 tests. Studio project-I/O focused verification
passed 868 tests with three Windows symlink skips, including 39 new format tests.
Changed-file Ruff/compilation, Windows mypy across 284 files, Darwin mypy across
nine files and the GC check passed. Final safe repo precommit passed 5,931 tests
with 33 skips. This slice's source implementation and verification are complete;
visible/installed workflow and physical acquisition acceptance remain pending.
No local Qt or physical acquisition validation was performed.

Four deterministic producer fixture copies are byte-identical across both
repositories. On the final fixtures, Toolbox consumer import/workflow checks
passed 92 tests with one skip; its broader project-I/O, GUI-focused non-Qt and
precommit gates passed. The fixtures use a fixed synthetic seed, identifiers and
export time so unrelated source releases do not change their scientific payloads.

Toolbox still owns raw registration and scientific interpretation. This format
change cannot infer an EEG file from participant/session metadata or qualify a
recording. Visible GUI and physical hardware acceptance remain separate.

### Fractional refresh handoff

- [x] Retain the configured display refresh and the compiled session refresh in
  the existing fields. Verify the 60.02 Hz project restore and completed Unicorn
  handoff with the planned code 1 and code 55 markers.
- [x] Enforce one compiled refresh across runs when writing a completed handoff.
- [x] Verify and retain the compiled cadence in the matching Toolbox import.
- [x] Show the 60.02 Hz tradeoff in Studio Setup and the Windows launch advisory,
  and in the Toolbox import review. Keep continuation available.

The [config contract](../../PROJECT_CONFIG.md#display-cadence-in-the-handoff)
defines the timing fields. This slice keeps the raw samples, marker positions,
and existing Toolbox FFT method at requested frequencies. Visible smoke path:
in Setup select 60.02 Hz, then verify the timing notice. Change to 60 Hz to verify
ordinary status, and select 60.02 Hz again. On a fixed 60.02 Hz Windows display,
launch from Home or Run and continue at that rate. Import the completed handoff
into Toolbox and verify the notice describes its nominal analysis basis.
The shared 60.02 Hz fixture passed the Toolbox import and project save/reopen
checks in [FPVS Toolbox `3e90420`](https://github.com/zcm58/FPVS-Toolbox/commit/3e90420).

### Existing integration

- [x] Core-owned built-in declarations for BioSemi ActiveTwo 64 and Unicorn Hybrid
  Black factory 8, using Toolbox's exact versioned profile/montage/decoder IDs.
- [x] Add declarations to saved recording settings, setup configs and runtime
  evidence. Optional metadata keeps existing config/result envelope versions readable.
- [x] Capture the effective recording settings before launch. On research
  finalization, atomically write a private completion receipt in full and compact
  modes. Interrupted runs retain acquisition evidence for recovery.
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

## Acquisition scope

The 2026-10-16 ActiveThree/Brain Products Studio extension retains the hardware
selection and marker evidence in completed configs without declaring a versioned
Toolbox profile. Current Toolbox source has explicit acquisition routes for
ActiveThree and Brain Products. Verify the actual device, reference, montage and
decoder through a reviewed recording for each route. See the
[Studio runtime contract](../../RUNTIME_EXECUTION.md#biosemi-activethree-and-brain-products-triggerbox)
and the Toolbox project I/O contract in the sibling checkout.

Synthetic tests cover selected-profile config round trips, exact event ordering and
session association in both export modes, abort retention, legacy reads and sharing
preference races. They do not qualify Recorder/BDF+ receiver behavior, EEG acquisition,
actual electrode wiring or physical timing. Factory mapping is a declaration.
Unicorn remains native 250 Hz in Toolbox, without resampling or interpolation.

The original release is recorded in [Studio 2.4.5](../completed/release-2.4.5.md).
The current acceptance sequence above covers the expanded whole-study workflow.
