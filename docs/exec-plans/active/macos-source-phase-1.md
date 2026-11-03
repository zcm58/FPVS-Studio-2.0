# macOS source support: Phase 1

Status: Active

Source implementation and automated source/bundle qualification are complete; physical Mac
GUI/display/service acceptance was explicitly deferred by the user and remains open.
Keep this plan active until those gates have evidence; no full parity claim is made.

## Decision and outcome

Requested on 2026-11-02: support FPVS Studio from source on macOS so a researcher
can set up, import, edit and test an experiment on a Mac, then transfer it to a
Windows lab PC for acquisition. Phase 1 targets parity with the non-hardware
features of the Windows source application. EEG hardware support is Phase 2.

Implementation was authorized on 2026-11-02. Work is active; native Mac acceptance
remains a required gate and is not established by Windows/fake-backed tests.
The user selected macOS CI for automated validation and explicitly deferred physical
Mac GUI/display/service checks until later. Implemented source and Windows/fake-backed
verification are recorded below; deferred native checks remain open acceptance.

Success is this workflow, using the same Studio version on both computers:

1. Export an existing Windows project as `.fpvsbundle`.
2. Install Studio's source dependencies on a Mac and import into its configured
   FPVS Studio Root Folder, without configuring an EEG device.
3. Inspect and edit all eight Setup steps, stimuli, tasks and session settings.
4. Explicitly test the experiment locally with the existing PsychoPy runtime and
   null trigger output. Mac display calibration is local to this test unless the
   researcher explicitly changes the authored project.
5. Save and export a new `.fpvsbundle` on the Mac.
6. Import on the Windows lab PC, review its actual display and recording setup,
   and use the existing production preflight and hardware workflow.
7. Support the reverse Mac -> Windows -> Mac workflow with the same guarantees.

## Scope and boundaries

| Phase 1 includes | Deferred or excluded |
| --- | --- |
| Source installation, startup, preferences, project management and all eight Setup steps | Compiled `.app`/DMG builds, signing, notarization and App Store distribution |
| Image/word authoring, templates, normalization/resizing, visual previews and presentation configuration | Windows executable installer/update/repair execution on Mac; source updates use an explicit Git/dependency workflow |
| All currently supported experiment categories, modifiers, participant/task flows, response scoring, Test/Pilot behavior and exports | EEG acquisition, serial/parallel/UDP marker delivery, recorder readiness and receiver qualification on Mac |
| Library enrollment/import/update, results/sharing, reporting and other existing software workflows through their current services | New remote services, migration of service ownership, or porting external Toolbox/vendor applications |
| `.fpvsbundle` transfer in both directions, `.fpvsconfig` software exports, generated handoff artifacts and compatible project persistence | A new Mac project schema, a second compiler or a separate Mac GUI |
| Native Mac display queries, Retina calibration and local presentation/timing diagnostics | Claims of Windows-equivalent physical timing or hardware readiness from mocks, CI or source portability alone |

Parity applies to a recorded, tested macOS/CPU support matrix. Begin qualification
with Apple Silicon and investigate Intel dependency availability in milestone 1;
record Intel as qualified or unqualified explicitly. Do not advertise untested OS
versions/architectures or silently omit software features on a supported target.
Mac users need Python/dependencies; they do not need Developer ID membership to run
the Python source application.

Reuse the existing owners and interfaces. Core remains independent of Qt, native OS
APIs and PsychoPy; engines retain lazy PsychoPy imports. Do not change seeded
compilation, frame scheduling, task semantics or persisted formats for this port.
Windows production behavior and existing Linux support must remain intact.

## Implemented seams and current gates

| Gate | Current evidence | Status |
| --- | --- | --- |
| Source implementation | Mac source helper/dependencies, native display/Retina, Keychain, Trash/Finder, local Test/Pilot calibration, presentation subprocess, portable bundle guards and software inventory implemented. | Complete; native acceptance is separate. |
| Windows regressions | Repo precommit: 4,974 passed, 14 symlink-permission skips; Ruff, full source mypy, compilation and audits passed. Final focused bundle/fixture checks: 197 passed, 5 native-only skips. Counts overlap. | Passed. |
| Visible Windows regressions | 18 focused GUI cases passed; Mac-only platform policy was faked. | Passed on Windows; no native Mac GUI claim. |
| Native dependency/adapter CI | Each CPU passed 1,358 checks with 10 platform skips, including real private-Keychain roundtrip, Trash, display queries and actual child IPC. Exact matrix in the support guide. | Both lanes passed on `f6b6721`. |
| Cross-OS artifact CI | All six jobs in [run 41554238134](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41554238134) passed, covering both transfer directions on both CPUs. Full settings, 14 asset hashes and 7-run/fixation plans matched. | Passed; no physical GUI/timing claim. |
| Physical Mac software acceptance | Native visible GUI, connected display/PsychoPy, interactive secure-store/service and failure/recovery checks. | Explicitly deferred by user; open. |
| EEG/hardware acquisition | No Mac adapters or physical qualification claimed. | Phase 2, outside this implementation. |

The source implementation reuses existing owners: `runtime/macos_display.py` supplies
native mode information, `gui/local_test_display_dialog.py` and
`gui/document_runtime.py` compose transient local calibration, and
`runtime/macos_session_process.py` keeps native presentation on a subprocess main
thread. Mac testing retains native/engine refresh verification and timing QC while
using null output without changing saved lab settings. Keychain and Finder/Trash
adapters remain lazy and preserve existing secure-store/file-operation boundaries.

`core/portable_paths.py` and `core/project_bundle.py` retain the bundle schema and
payload bytes while rejecting ambiguous/unportable paths, source links and archive
links/special files. Signature-recognized, unreferenced Finder metadata is omitted at
image intake, owned folder discovery and export; explicit image references are never
silently removed. Authored dot-prefixed images and word content are preserved. Bundle staging, hashes,
compile validation, cancellation and collision-safe installation remain in place.

Source paths above are relative to `src/fpvs_studio/`. The
[software inventory and native checklist](../../MACOS_SUPPORT.md) records shared
features, adapters, successful CI and deferred physical evidence. Detailed behavior stays
in [GUI workflow](../../GUI_WORKFLOW.md), [runtime execution](../../RUNTIME_EXECUTION.md),
[environment](../../ENVIRONMENT.md) and [architecture](../../../ARCHITECTURE.md).
Coordinate with [lab-independent recording setup](../planned/lab-independent-recording-setup.md)
without expanding this phase into named lab profiles or multi-monitor selection.

## Implementation milestones and remaining acceptance

Checked items mean implementation/recorded checks are complete. They do not close
an adjacent native acceptance item. Physical acceptance below remains deferred by the
user; completed CI items link to the real hosted results.

### 1. Establish a reproducible Mac source environment

- [x] Add `scripts/macos-source.sh` for isolated Python 3.10 setup, source launch and
  safe verification. Install declared real `dev,engine` dependencies and conditional
  Mac bindings; fail dependency checks without ignoring upstream constraints.
- [x] Document Terminal/source-update workflows and inventory all non-hardware areas,
  including Library/results, reports, templates, maintainer/access boundaries,
  file/folder actions, previews, shortcuts, fonts and source-version messaging.
- [x] Run clean arm64/x86_64 dependency/import CI and record exact macOS, CPU,
  Python/PsychoPy/Qt/native-wheel versions. Unavailable combinations remain unqualified.
- [ ] Complete visible first source launch, preferences/restart and close on each
  claimed native target. Physical acceptance deferred by user.

Exit: a recorded compatible native matrix and repeatable clean install/launch.
Neutral imports must not open PsychoPy windows or access EEG.

### 2. Add small native service adapters

- [x] Implement the primary/default-display Mac provider behind `NativeDisplayMode`,
  including Retina physical pixels and explicit unknown/variable/unsupported mode
  errors. Do not invent an exact refresh from Qt's nominal rate.
- [x] Implement shared Keychain load/save/delete for Library/results credentials with
  fake-backed failure coverage; no plaintext fallback or bundled credentials.
- [x] Implement native Trash and portable Qt folder opening, preserving cancellation/errors,
  nonblocking worker ownership and cleanup. Use native Save/Find shortcut bindings.
- [x] Execute opted-in native CI probes for bindings, display diagnostics and unique
  synthetic Keychain/Trash entries. A hosted display probe is not physical timing proof.
- [ ] Verify interactive enrollment/restart/revocation, locked/unavailable Keychain,
  Finder/Trash permissions/cancel and recovery on a physical Mac. Deferred by user.

Exit: native adapter evidence plus preserved Windows/Linux contracts and failure behavior.

### 3. Enable safe local experiment testing

- [x] Allow Mac source root setup, authoring/import and explicit Test/Pilot without
  EEG selection, preserving test identity and participant/test-data eligibility.
- [x] Use launch-only null output with fake-backed checks that hardware adapters and
  acquisition readiness are not constructed/contacted. Preserve saved trigger/backend
  settings and Windows recording overrides.
- [x] Retain Mac native mode plus engine observation, verified transient refresh and
  timing QC; preserve existing Windows source-test policy and normal lab checks.
  Report unsupported/failed verification instead of permitting a wrong-speed test.
- [x] Compose local width, distance and resolution through transient state; reject
  incompatible timing without changing authored frequency, duration, SOA, fixation
  rules or saved lab calibration. Keep native presentation on a subprocess main thread.
- [ ] Exercise every supported category and representative image/word, repeated/partial
  block, seed, fixation/tutorial, task/modifier/question/scoring, abort/recovery and
  export flow in visible native PsychoPy. Physical acceptance deferred by user.

Exit: representative native local tests with correct identity, cleanup and unchanged
lab settings. Compare seeded schedules at the same refresh/settings. Different refresh
rates need compatible authored timing and realized-rate reporting; identical frame or
fixation-onset schedules across different refresh targets are not promised.

### 4. Qualify portable bundles and the lab handoff

- [x] Preserve existing archive/project schemas and self-contained relative asset
  references, including variants, words, task/scene media, instructions, trigger codes,
  counts, saved blocks, seeds/modes and fixation rules. No absolute/external dependency.
- [x] Add host-independent Unicode/casefold/prefix collision, reference-spelling,
  reserved/invalid/trailing-dot/space, UTF-8/UTF-16 component-limit and link guards;
  preserve authored bytes/text and reject ambiguity with actionable errors.
- [x] Add safe Finder metadata intake that retains authored dot-prefixed media;
  preserve checksum/resource/active-payload/traversal/cancellation protections and
  atomic destination/staging behavior.
- [x] Preserve **Open with Imported Values** versus explicit **Apply & Open Project**.
  Keep test calibration/preferences, credentials and consent/enrollment local;
  exclude runs/logs/cache/history and preserve imported recording overrides.
- [x] Implement the synthetic handoff CLI and CI artifact chain. Fixture covers images,
  words, derivatives, task media, 3/2/2 saved blocks, independent seeds, fixation
  schedules and a Windows recording declaration. Source relocation and semantic,
  SHA256/full 60 Hz plan comparison pass in local CLI checks.
- [x] Run actual Windows -> Mac -> Windows and Mac -> Windows -> Mac CI chains on
  both CPUs; retain unchanged baselines, artifact payload hashes and complete plans.
- [ ] Complete physical dialogs, case-sensitive volumes and broader scene/media
  workflow checks, allowing only deliberate collision-ID remapping. Deferred by user.
- [x] Check normal Windows recording policy offline for four real Mac exports:
  explicit production flags resolve to Brain Products TriggerBox, never null;
  missing amplifier/sampling-rate configuration correctly blocks readiness. No
  Test/Pilot flags were saved or project bytes changed. Hardware/probes were not used;
  actual acquisition/marker validation remains Phase 2.

Exit: recorded two-direction native transfer evidence on the declared matrix, with
receiving-root containment and unchanged scientific/recording state. Offline bundle
import must not require Mac enrollment or a new network connection.

### 5. Complete software parity and document support

- [x] Document source installation/update, recorded source environments, local-test limits,
  portable handoff/recovery and a complete shared/adapter/native-evidence inventory.
  Preserve existing services, external-app and maintainer authorization boundaries.
- [x] Configure the `macos` verification scope, native CPU CI lanes, evidence artifacts
  and cross-OS handoff jobs. Update canonical policy/routing/docs for CI execution;
  neither local nor hosted offscreen Qt is a substitute for approved visible checks.
- [x] Record successful native CI runs, resolved dependency versions and qualification
  limits. Both recorded source environments pass; physical acceptance remains open.
- [ ] Finish physical software acceptance: eight Setup steps at 1120x820 in both
  themes, long paths, Retina/dialog/font geometry, keyboard/accessibility, native
  rendering/cleanup and authorized Library/sharing/support/maintainer/export flows.
  Explicitly deferred by user; no service activity is authorized merely by the plan.

Exit: close each advertised-target gate using its recorded evidence. Keep this plan
active while native/physical acceptance remains deferred; source completion alone
must not be described as full Phase-1 parity.

## Verification record

### Local source-startup investigation, 2026-11-02

The user's standalone base Python lacked Studio dependencies, and the existing `.venv`
still described Studio 1.0.0 with incomplete/outdated dependencies. Refreshing its
editable `dev,engine` install and selecting `.venv/bin/python` in PyCharm resolved
startup imports. The user approved visible startup and observed Studio opening, then
reported a native crash after a Library download. The native trace entered PySide6
6.12.0's QObject wrapper/event-filter handling during garbage collection while a
worker read the bundle manifest. This is evidence of the crash location, not proof
of a particular ownership or upstream defect.

Repeated synthetic workers, cancellation/handoff checks and five read-only reviews
of the retained downloaded archive did not reproduce the fault. Mac dependency
selection now uses the PySide6 6.11.3 maintenance release as a bounded compatibility
mitigation, with PyQt6 6.11 for valid engine type stubs. Windows/Linux dependency
ranges and production Python code remain unchanged. Keep the original crash and
broader physical acceptance open until the actual workflow has confirming evidence;
the earlier CI matrix does not qualify this new dependency selection.

Local verification on macOS 26.5.2 / arm64 / CPython 3.10.20, Studio 2.5.8,
PySide6 6.11.3 and PsychoPy 2026.2.5:

- Mac focused: 1,353 passed, 15 platform/native-opt-in skips. Two separately selected
  native dependency/display probes passed; personal Keychain/Trash probes were not run.
- Metadata, documentation-harness, import-boundary and Qt-registry checks: 82 passed,
  6 Windows build/junction skips. Windows/Linux base, dev, engine and packaging
  dependency selections also matched the pre-change revision exactly.
- Approved visible Library, worker and deferred-shutdown coverage: 76 passed. Library
  layout states passed at 900x640 and 1040x760 with the native default palette.
- An offline native-Cocoa check used the retained approximately 500 MB, 3,080-entry
  download with a fake transport and an isolated temporary Studio Root. Manifest
  review, full extraction, **Open with Imported Values**, an exposed project window,
  lease release and clean exit code 0 passed. The temporary import was removed;
  the user's cache, projects and normal settings were preserved. No service request
  or experiment playback was made by this check.
- Windows-targeted mypy passed all 267 source files. Changed-file Ruff, compilation
  and whitespace checks passed. These are not physical Windows acquisition checks.
- Full repo precommit remains unqualified: PowerShell is unavailable for its audits;
  native-Mac mypy reports the same 35 pre-existing Windows-API/Mac-branch type errors.
  The safe GUI scope has 8 Windows-recording-policy fixture failures on Mac, and a
  broader safe run was stopped on Windows-assumption failures. Extra native
  QMessageBox smoke coverage had 11 failures and one fixture teardown error involving
  Mac title/size/Escape behavior and a previously deleted reporter. These failures
  were retained as acceptance gaps rather than changing unrelated production code.

The successful offline import is new workflow evidence, not a deterministic
reproduction or proof of the original native crash's cause. Keep its intermittent
stability qualification and the remaining physical/interactive acceptance open.

The subsequent [Windows-primary test-adapter repair](../completed/windows-primary-platform-test-adapters.md)
resolved the host-dependent safe-suite and type-checking gaps above: native Mac repo
precommit passed **4,973 tests**, 64 platform/filesystem skips and 24 subtests; Windows
mypy passed all 266 current source files and Darwin mypy passed six adapter owners.
Mac focused passed 1,376 tests with 15 platform/native-opt-in skips. Existing audits
ran through official temporary PowerShell 7.6.9; both native verification launchers
now select the active environment correctly. CI runs Windows precommit before the
Mac jobs. These are local Mac results pending the new native CI run. The Mac became
locked, preventing a further visible Qt pass; native QMessageBox failures and the
intermittent original crash remain open. No physical timing/hardware claim follows.

After the user unlocked the Mac, 80 visible Mac/Library/worker cases passed and the
obsolete IDE interpreter registration was removed. Popup test adapters preserve
primary Windows titles/580 px sizing while checking actual Mac content bounds,
native Cocoa reporting and asynchronous Return/Escape dismissal. Deferred test
reporter deletion is drained between cases; application dialog behavior is unchanged.
The final combined visible selection passed 100 cases, including all 19 popup cases,
Welcome actions, Mac calibration/policy, Library dialogs and native worker shutdown.
Native Windows precommit on `185471b` passed
5,033 tests, four POSIX-only skips, 24 subtests and both type passes in
[run 41571020291](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41571020291).
Both secondary Mac CPU jobs passed 1,382 checks, ten platform skips, adapter mypy
and native probes with the new Qt selection. Final local precommit after the popup
test changes again passed 4,973 tests, 64 platform/filesystem skips and 24 subtests.
Original crash stability, actual presentation timing and hardware remain unqualified.

Current implementation evidence is in the gate table above and
[MACOS_SUPPORT.md](../../MACOS_SUPPORT.md). Native CI source commit `f6b6721` passed
all six jobs in [run 41554238134](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/41554238134).
ARM used macOS 15.8.2 / CPython 3.10.11; Intel used 15.7.9 / 3.10.21. Both used
PySide6 6.12.0, PsychoPy 2026.2.5 and PyObjC 12.2.2; complete freezes and host/JUnit
evidence are attached to the run. Private native Keychain probes performed real
save/load/delete without an interactive skip. Hosted 60 Hz / 1024x768 display
metadata is recorded with `physical_display_qualified=false`.

No real projects, participant data, live service enrollment, EEG devices or physical
Mac presentation were used. Physical and interactive acceptance remains explicitly
deferred rather than inferred from the automated results.

Planning baseline (historical): 30 focused non-Qt bundle/path/task/relocation checks
and 13 documentation checks passed before implementation. Those checks established
reusable foundations, not a native Mac transfer or visible acceptance result.

## Phase 2: hardware support, separately scoped

After Phase 1, create a hardware-specific plan and qualification matrix for Mac
serial/USB/parallel interfaces, acquisition/recorder readiness, external marker
delivery, receiving-software compatibility and physical timing/receiver evidence.
The current actiCHamp path uses a Windows kernel driver; Unicorn uses local loopback
UDP plus a Windows Recorder/BDF check. Equivalent Mac workflows need supported
software/drivers, not just a new platform string. A remote Windows recorder would be
an explicit new endpoint/readiness/provenance design, not a silent fallback.

Phase 2 must preserve Windows support and obtain explicit authorization before
contacting acquisition hardware or sending markers. It does not delay Phase-1
authoring/local-testing support, and Phase 1 must not claim hardware parity.
