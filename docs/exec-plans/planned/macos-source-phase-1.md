# macOS source support: Phase 1

Status: Planned

## Decision and outcome

Requested on 2026-11-02: support FPVS Studio from source on macOS so a researcher
can set up, import, edit and test an experiment on a Mac, then transfer it to a
Windows lab PC for acquisition. Phase 1 targets parity with the non-hardware
features of the Windows source application. EEG hardware support is Phase 2.

This task authorizes creation of the plan, not implementation. Move this file to
`active/` when implementation becomes the selected task. None of the proposed Mac
behavior below is implemented or qualified by this document.

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

## Current evidence and minimal seams

- `core/paths.py` stores project-relative POSIX paths and checks lexical/resolved
  containment on every host. `core/project_bundle.py` packages project/manifest JSON
  and `stimuli/`, verifies hashes, stages imports, dry-compiles, and commits into a
  collision-safe new folder. It excludes `runs/`, `logs/` and `cache/`.
- `.fpvsbundle` carries original/generated image assets, word lists and task/scene
  media. `.fpvsconfig` intentionally does not carry ordinary image libraries and
  cannot substitute for the full transfer workflow.
- `gui/controller.py` restricts source Test/Pilot availability to Windows/Linux and
  requires default hardware setup during first-run root configuration. Both need an
  explicit Mac authoring/testing capability; merely adding `darwin` to one gate is
  insufficient.
- `runtime/display_mode.py` has a neutral `NativeDisplayMode` contract and native
  Windows/Linux dispatch, with no Mac provider. `gui/document_runtime.py` already
  accepts a launch/compile `refresh_hz` argument. Geometry is currently read from
  the project's display settings, so a local calibration needs a transient model
  copy or an equally small launch-only composition seam.
- `library/credentials.py` defines the existing load/save/delete secure-store
  protocol. Library and `data_sharing/credentials.py` need a shared Mac Keychain
  implementation; plaintext storage is not an alternative.
- `gui/controller.py`'s Recycle Bin helper currently calls permanent removal on
  non-Windows hosts. Supply native Trash semantics before offering this operation
  on Mac. Inspect folder-opening, shortcuts, fonts, subprocesses and process cleanup
  for similar platform assumptions.
- `triggers/` already isolates hardware transports. `runtime/recording.py` and
  `runtime/unicorn_recorder.py` own acquisition readiness. Phase 1 reuses their
  explicit Test/Pilot exclusion path; it does not implement Mac hardware adapters.

Source paths above are relative to `src/fpvs_studio/`. Detailed current behavior is
in [GUI workflow](../../GUI_WORKFLOW.md), [runtime execution](../../RUNTIME_EXECUTION.md),
[environment](../../ENVIRONMENT.md) and [architecture](../../../ARCHITECTURE.md).
Coordinate with [lab-independent recording setup](lab-independent-recording-setup.md)
without expanding this phase into named lab profiles or multi-monitor selection.

## Implementation milestones

### 1. Establish a reproducible Mac source environment

- [ ] Prove a clean install and source launch on the first supported Mac. Begin with
  the repository's Python 3.10 contract and establish an explicitly tested
  Python/PsychoPy/Qt/native-wheel combination per CPU architecture. Do not silently
  upgrade Python across all platforms, force incompatible wheels, or bypass dependency
  constraints to make installation appear successful.
- [ ] Add the smallest setup/run helper and concise Terminal/IDE instructions using
  an isolated environment and `python -m fpvs_studio.app`. Install Mac-only OS bindings
  conditionally and import them only inside the Mac adapter.
- [ ] Inventory every non-hardware Windows feature against a parity checklist,
  including Library/results, reporting, maintainer tools where authorized, file/folder
  actions, templates, preview dialogs, shortcuts and source-version/update messaging.
  Record each as shared, adapter required, or verified; unexplained omissions block
  completion. Preserve existing backend credentials/authorization boundaries.

Exit: record exact Mac OS/CPU/dependency versions and a repeatable clean install;
bootstrap and importing neutral core modules neither launch PsychoPy nor access EEG.

### 2. Add small native service adapters

- [ ] Implement a Mac display-mode provider behind the current dispatcher. Reconcile
  native mode information, approved targets, Retina physical pixels and engine
  observations for the same primary/default display used by playback. Unknown,
  variable and unsupported modes remain explicit; never invent an
  exact refresh rate from Qt's nominal value or suppress a failed check.
- [ ] Implement Keychain load/save/delete for Library and results credentials. Verify
  enrollment, restart, disconnect/revocation, locked/unavailable store and actionable
  recovery; preserve consent and redaction. Credentials stay machine-local.
- [ ] Implement native Trash and portable folder-opening behavior. Verify Cancel,
  permissions and failures without permanently deleting projects under a Trash label.
  Preserve worker ownership, nonblocking UI and deterministic process cleanup.

Exit: native adapters have fake-backed Windows tests plus real Mac integration
evidence. Existing Windows/Linux adapters and error contracts remain unchanged.

### 3. Enable safe local experiment testing

- [ ] Allow Mac source users to configure a root, author/import projects and enter
  explicit Test/Pilot mode without an EEG selection. Retain a clear test identity
  and existing participant/test-data eligibility rules.
- [ ] Use launch-only null output. Assert that serial, parallel, Unicorn and other
  hardware adapters/readiness probes are never constructed, opened or contacted.
  Do not save a null backend, disable project trigger settings, or replace a Windows
  recording override merely because a project is opened on Mac.
- [ ] Keep Mac test preferences local and reuse the acquisition-only Test/Pilot
  exceptions. Current local testing also sets `verify_refresh_rate=False`; do not
  blindly carry that bypass into Mac playback. Require native mode plus engine
  observation of the connected display, compile at that verified transient target,
  and retain timing QC. Failed/unsupported verification must be actionable instead
  of permitting wrong-speed tests. Preserve existing Windows source-test policy and
  normal lab checks; a successful Mac test is not EEG/hardware qualification.
- [ ] Compile tests at an explicit local refresh target through the existing seam.
  Compose local physical width, viewing distance and resolution through a transient
  deep copy when needed. Never update/save the authored lab calibration to test on
  another display. Unsupported timing combinations must explain the corrective action;
  retain the compiler's exact/realized-rate rules and never silently change authored
  frequency, duration, SOA or fixation rules.
- [ ] Exercise all supported experiment categories and image/word modes, ordinary
  and repeated conditions, randomized blocks/partial blocks, seed modes, fixation
  targets, tutorials, modifiers, questions, scoring, abort/recovery and exports through
  the same runtime/engine used on Windows.

Exit: a representative Mac session runs and exports as a local test with no EEG;
the project retains its lab settings and Windows defaults remain production-safe.
Compare seeded compiled schedules across OSes at the same target refresh/settings.
With different refresh targets, verify the authored timing where representable and
report the realized schedule; identical fixation frame/onset schedules across different
refresh rates are not promised.

### 4. Qualify portable bundles and the lab handoff

- [ ] Preserve the current archive/schema rather than inventing a Mac bundle type.
  Export must be self-contained: no Windows drive/UNC path, Mac home path or external
  stimulus dependency. Include image variants, words, task media and masking scenes;
  preserve payload bytes/hashes, instructions, trigger codes, counts, saved condition
  blocks, seed roots/modes and fixation rules.
- [ ] Verify Windows -> Mac -> Windows and Mac -> Windows -> Mac transfers on real
  filesystems. Compare semantic project data and asset hashes, allowing documented
  explicit rename/collision-ID remapping. Delete/move synthetic source directories
  before compiling the import to prove independence from the exporting computer.
- [ ] Add fixtures for case-sensitive and case-insensitive destinations, exact
  reference/payload casing, composed/decomposed Unicode filenames, spaces/non-ASCII
  names, portable filename/component limits, reserved/trailing-dot/space names,
  inside-root links/aliases and escaping links. Determine safe behavior for Finder
  metadata/AppleDouble sidecars. Reject ambiguous/unportable transfers with actionable
  errors; do not silently rename assets, normalize word content, overwrite files or
  discard authored media. Inspect current guards before adding duplicate validation.
- [ ] Retain traversal, symlink/special-file, checksum, archive/resource-limit and
  cancellation protections. Failed export preserves the old destination; failed
  import cleans only its own staging and preserves existing projects.
- [ ] Preserve the explicit import-display choices: **Open with Imported Values**
  leaves authored values unchanged; **Apply & Open Project** is an intentional save.
  Detection in the review dialog is not proof of presentation timing. Preview-local
  calibration must not silently become the exported lab configuration.
- [ ] Keep computer defaults, credentials, consent/enrollment sidecars and test mode
  local. Bundles remain authoring transfers, not result/history backups. Test logs,
  runs and cache remain excluded. Imported Windows recording overrides survive;
  projects without overrides use the receiving lab computer's existing defaults.
- [ ] On Windows, import the Mac-exported bundle and verify compile/readiness checks
  with faked acquisition dependencies. Confirm real lab launch cannot inherit Mac
  null output, suppressed hardware preflight or test identity.

Exit: real cross-OS roundtrips pass on the declared support matrix, imports operate
under the receiving root, and an unchanged project survives open/test/re-export without
unintended edits to scientific or recording configuration. No new Mac credential or
network connection is needed just to import an offline bundle.

### 5. Complete software parity and document support

- [ ] Finish the milestone-1 parity checklist, including Library/results and software
  exports/handoff generation through current service contracts. Do not port external
  backend/Toolbox/vendor applications as part of this repository change.
- [ ] Verify all eight Setup steps at 1120x820 in both themes, long Mac paths, Retina
  sizing, dialogs, keyboard navigation, validation/busy/error states and runtime cleanup.
- [ ] Add a Mac lane for dependency/import/unit/adapter checks to the existing
  verification driver, using Windows for most editing and fake-backed regression work.
  Any new CI workflow must update the current docs-only GitHub policy, task routing
  and architecture verification notes when implemented. CI cannot qualify a physical
  display or EEG. Visible Qt/PsychoPy checks require an approved native GUI session;
  never use local offscreen Qt.
- [ ] Document source install/update, supported versions, permissions actually required
  by the selected input/render backend, local test limitations, portable handoff and
  recovery. Do not request unnecessary OS permissions or run a Windows installer on Mac.

Exit: the checklist and evidence matrix below are complete for each advertised Mac
target; any remaining gap is explicit and prevents a full Phase-1 parity claim.

## Verification and completion evidence

| Acceptance gate | Required evidence |
| --- | --- |
| Clean source install | Recorded versions and repeatable install/launch on a clean Mac environment |
| Full software authoring | All supported categories/modifiers, eight steps, dialogs and exports; bounds/text checks at minimum size |
| Safe local tests | No hardware construction/transport writes; stable stop/abort; correct test identity and result eligibility |
| Scientific invariants | Same-target seeded compilation/order/fixation comparisons and explicit incompatible-local-rate rejection |
| Offline bundle portability | Real two-direction cross-OS roundtrips, relocated source, asset hashes and preserved lab settings |
| Secure services/OS behavior | Keychain, Trash, file/folder actions, failure recovery and existing consent semantics |
| Windows/Linux regressions | Applicable focused scopes, repo precommit and safe source-import/contract checks |
| Mac acceptance | Approved visible native GUI/PsychoPy session, recorded display/calibration and unqualified cases |

Reuse `test_project_bundle.py`, `test_masking_media_portability.py`, `test_models.py`,
`test_bundle_open_setup.py`, `test_default_recording_preferences.py`,
`test_runtime_recording.py`, `test_runtime_display_refresh.py`,
`test_randomization_integrations.py`, `test_saved_order_integrations.py` and block
ordering tests. Extend registered GUI import/export, Setup, preview and Test/Pilot
coverage. Do not run hardware or transmit markers during automated verification.

Run owning focused scopes as milestones change, then repo precommit for shared
behavior. Use the docs focused route for this plan. Record skipped visible/external
checks truthfully; mocks, Windows tests and a successful source launch do not establish
Mac parity. Update canonical workflow/environment docs only as implemented behavior
lands, keeping detailed contracts in their existing owners.

Planning baseline on Windows: 30 focused non-Qt checks passed for bundle contents,
task assets, import/rename/recording preservation, collision/path rejection, checksums,
cancellation and relocation. This demonstrates reusable portable foundations, not a
completed Mac transfer test. No production code, user projects, Qt or hardware were
changed/run while preparing this plan.
Plan inventory/link/hygiene verification also passed all 13 docs-focused checks.

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
