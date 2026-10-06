# Agent Task Index

Use this page after `AGENTS.md` to choose the smallest useful context and verification
route. Pick one primary scope, read only its initial context, and expand when failures or
cross-layer behavior require it.

## Fast Route

1. Run `git status --short --branch`.
2. Match the task to one scope below.
3. Read the listed package guide and focused contract document.
4. Run the scope's focused verification before broad source inspection.
5. Inspect only relevant failures, symbols, and tests.
6. Run the repo precommit tier when shared behavior or multiple layers changed.

## Verification Scopes

| Scope | Use for | Initial context |
| --- | --- | --- |
| `repo` | Harness, shared configuration, cross-layer changes, or uncertain ownership | `ARCHITECTURE.md`, this index, and the changed paths |
| `docs` | Agent guidance, contracts, plans, or docs hygiene | `docs/index.md`, the document being edited, and `docs/exec-plans/README.md` for plan work |
| `gui` | PySide6 windows, dialogs, controllers, components, workers, modular-task authoring, or GUI behavior | `src/fpvs_studio/gui/AGENTS.md`, `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, and the focused GUI test file |
| `core` | Models, validation, neutral contracts, modular-task definitions, compilation helpers, or domain logic | `src/fpvs_studio/core/AGENTS.md` and the relevant contract document |
| `compiler` | `RunSpec`/`SessionPlan` compilation, scheduling, fixation realization, or assets in compiled contracts | `src/fpvs_studio/core/AGENTS.md`, `docs/RUNSPEC.md`, and `docs/SESSION_PLAN.md` |
| `project-io` | Project persistence, `.fpvsconfig`, `.fpvsbundle`, templates, paths, import, or export | `src/fpvs_studio/core/AGENTS.md`, `docs/GUI_WORKFLOW.md`, and the active plan when bundle work is in scope |
| `preprocessing` | Image intake, inspection, normalization, variants, or manifests | `src/fpvs_studio/preprocessing/AGENTS.md` and the relevant asset/manifest tests |
| `runtime` | Launch, preflight, modular-task sequencing, session flow, participant history, scoring, or exports | `src/fpvs_studio/runtime/AGENTS.md` and `docs/RUNTIME_EXECUTION.md` |
| `engine` | Presentation interface, PsychoPy rendering, modular task screens, frame timing, or display screens | `src/fpvs_studio/engines/AGENTS.md`, `docs/ENGINE_INTERFACE.md`, and `docs/RUNSPEC.md` |
| `triggers` | Trigger contracts, serial hardware adapters, marker writes, or trigger logs | `src/fpvs_studio/triggers/AGENTS.md` and the trigger sections of `docs/RUNTIME_EXECUTION.md` |
| `updates` | Independent updater protocol/staging, release and repair selection, bounded cache/locking, verified downloads/launch, or update GUI shutdown coordination | `src/fpvs_studio/updates/AGENTS.md` and `docs/PACKAGING.md` |
| `library` | View/Create Project library entry points, private catalog, enrollment, downloads, Advanced developer mode, and publishing | `src/fpvs_studio/library/AGENTS.md`, `src/fpvs_studio/developer/AGENTS.md` for publishing, `docs/EXPERIMENT_LIBRARY.md`, and the active private-library plan |
| `data-sharing` | Experiment contribution consent, credentials, completion capture, outbox, Cloudflare intake or matched reference comparisons | `src/fpvs_studio/data_sharing/AGENTS.md`, `docs/DATA_SHARING.md`, and `services/results/AGENTS.md` for backend work |
| `packaging` | Versioning, PyInstaller, Inno Setup, sparse patches, owned-file upgrade reconciliation, branding, isolated beta/executable builds, or packaged smoke | `packaging/AGENTS.md`, `docs/PACKAGING.md`, and `pyproject.toml` |

Run a route with:

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
```

Add `-List` to a scoped command to inspect the configured steps. Use
`./scripts/verify.ps1 -CheckConfig` after editing `.agents/verification.toml`, the
PowerShell wrapper, or the Python driver.

## Verification Tiers

- `focused`: selected scope checks plus changed-file Ruff and Python compilation.
- `precommit`: repo audits, mypy, changed-file checks, and the safe non-Qt pytest suite.
  The driver selects unit files outside the Qt registry before invoking pytest.
- `full`: optional full Ruff, mypy, and pytest with registered Qt tests explicitly
  enabled for an approved visible local environment.

Use the broader local gate after cross-layer or shared-contract changes:

```powershell
./scripts/verify.ps1 -Scope repo -Tier precommit
```

Do not run `full` by default. Qt tests are excluded before import during ordinary local
verification. The full tier requires `FPVS_ALLOW_QT_TESTS=1`, user approval, and a safe
visible environment; do not set `QT_QPA_PLATFORM=offscreen`. GitHub does not repeat the
repository's local test or code-quality checks. Its documentation build and publishing
workflow is separate.
The registry also includes the two `ProjectDocument` QObject test modules under
`tests/unit/`; the `core` full tier selects them, while default collection excludes
them before importing Qt.

## Skill Routing

For native AB all-character markers, start with `core/compiler_schedules.py`,
`engines/psychopy_triggers.py`, and `runtime/preflight.py`. Frame -1 is the explicit
neutral condition-marker flip for opted-in streams; see the TriggerEvent contract
in [RunSpec](../RUNSPEC.md#triggerevent). Use compiler/engine/runtime routes and
`tests/unit/test_attentional_blink_distractor_triggers.py`, then repo precommit.

| Task | Repo-local skill |
| --- | --- |
| PySide6 layout, components, workers, status/error UX | `.agents/skills/pyside6-gui-cleanup/SKILL.md` |
| Add or maintain registered pytest-qt coverage | `.agents/skills/pytest-qt-smoke/SKILL.md` |
| Project roots, dialogs, persistence, export/import paths | `.agents/skills/project-path-audit/SKILL.md` |
| Protected retired paths or historical behavior boundaries | `.agents/skills/legacy-boundary-review/SKILL.md` |
| PsychoPy migration across compile/runtime/engine seams | `.agents/skills/fpvs-psychopy-migration/SKILL.md` |

Read a selected skill completely before acting. A passing skill audit is sufficient
evidence for its invariant unless the task changes that audit or boundary.

## Backend Reliability And Compilation Efficiency

For backend reliability or compilation-efficiency regressions, start with
`core/serialization.py`, `core/compiler_inputs.py`, `core/compiler_tasks.py`,
`preprocessing/importer.py`, and `runtime/session_export.py` as appropriate.
Contracts remain in [SessionPlan](../SESSION_PLAN.md),
[GUI workflow](../GUI_WORKFLOW.md), and [Runtime execution](../RUNTIME_EXECUTION.md).
Use compiler/project-io/preprocessing/runtime focused routes; the GUI route includes
safe non-Qt source-adoption coverage. `test_import_boundaries.py` enforces internal
dependency restrictions through the repo route. Cross-layer changes require precommit.

## Independent Updater And Patches

Start with `updates/helper_client.py`, `helper_protocol.py`, `helper_service.py`, and
`helper_runtime.py` for the separate process, private handoff, registered installation,
bounded helper staging, and install/restart ownership. `updater_main.py` is the independent
entry; `gui/update_dialog.py` remains Studio's update surface, while `gui/updater_window.py`
provides standalone Update & Repair and installation progress. `UpdatePhase` reports
status and an explicit installation-committed state through the existing worker lifecycle.

`updates/patches.py` authenticates patch candidates and the installed inventory without
scanning payload files at discovery/download. Keep complete baseline/target verification
and mutation in `packaging/inno/patch_upgrade.iss`. The retained Python verifier uses
reusable Windows bindings and scoped directory pins in `updates/cache_io.py`.
`scripts/build_patch.py` generates sparse payloads and release JSON; the lightweight
helper build is `scripts/build_updater.ps1`. Build, cache, repair, and release contracts
live in [Packaging](../PACKAGING.md#independent-updater-build-and-installation).

Use updates/gui/packaging focused routes, then repo precommit. The updates route includes
`tests/unit/test_update_helper.py` and `test_updater_main.py`; registered GUI coverage
stays in `tests/gui/test_update_dialog.py`. Native lifecycle acceptance uses
`scripts/check_patch_installer_lifecycle.py` with isolated synthetic app identities.
See the completed independent-updater execution plan for implementation evidence and the
[v1.7.0 release record](../exec-plans/completed/release-1.7.0.md) for published artifact
acceptance; source checks do not establish an installed update or clean-PC repair result.

## Library Project Versions

For protected website discovery, exact-version publications, per-experiment
**total downloads**, administrator content editing, dedicated administrator password
login, web account registration and lab Library access, use the
private `zcm58/FPVS-Studio-Library` repository's `AGENTS.md`, `ARCHITECTURE.md` and
`PORTAL_PLAN.md`. Its standalone local checkout is the sibling `../OpenFPVS/`,
opened as its own PyCharm project. Studio's integration plan is
`docs/exec-plans/active/fpvs-account-portal.md`; keep backend source and schema in
the private project, not in a second desktop implementation. Run its Node tests,
syntax and dry deployment checks; this repository's Library route covers the
existing native client contract.
Website enrichment uses separate browser APIs; preserve the strict native catalog.
Browser bundle downloads use ordinary Welcome-screen imports without native origin
receipts; project-version checks require explicit linking. The personal website
repository is independent.
The private service owns Firebase Spark configuration, additive password-session
migration and encrypted provider credential rechecks. Its README is the canonical
setup guide; administrator `/admin` and `/admin/sign-in` remain separate from
researcher `/account` and native device authorization. Run Studio's documentation
focused route for integration-document changes; no desktop identity implementation
or Qt verification is needed for a website-only login change.

For reusable lab codes and optional startup setup, begin with
`gui/library_access_dialog.py`, `gui/application.py`, `gui/controller.py` and
`library/client.py`/`models.py`. The private service owns code issuance and
revocation; a code never enters project settings or grants results-upload access.
Use Library/GUI/docs focused routes and repo precommit; registered startup coverage
is `tests/gui/test_library_access_dialog.py` and is excluded from safe local runs.

For project-version checks, start with `core/library_origin.py`,
`core/library_installations.py`, `library/installations.py`,
`library/project_updates.py`, `gui/project_update_controller.py` and
[Experiment Library](../EXPERIMENT_LIBRARY.md#project-version-checks).
Library imports write local receipts before commit; checks on open never install
changes. Core's exact managed-origin alias policy preserves existing receipts and
installation matching when native access moves to `openfpvs.com`; credentials stay
scoped to the canonical connection origin. Use Library/project-io/GUI focused routes and registered project-version
dialog/controller tests. Legacy name matches require review and explicit linking;
same/newer recorded installations block downloading and bundle commit.
The version dialog warns about updating after collection begins and offers keeping
the current version or downloading separately. Preserve the original experiment and
its reporting scope; individual-condition merging is a separate deferred workflow.

## Bug Reporting

For File > Report a Bug or Request a Feature, begin with `support/AGENTS.md`, `docs/BUG_REPORTING.md`,
`gui/report_bug_dialog.py`, and `gui/bug_report_controller.py`. Support owns the
reviewed payload and OS-local drafts; the GUI owns interactions and delegates
work through the existing app-owned task lifecycle. Online reporting requires explicit submission and defaults to the approved endpoint
of the separate Cloudflare service in private `zcm58/FPVS-Studio-Feedback`;
never enable it as part of a test. That repository owns deployment and operations.
Run the GUI scope, `tests/unit/test_support_reports.py` and
`tests/unit/test_support_client.py`, then repo precommit for startup/lifecycle
changes. Registered Qt coverage is `tests/gui/test_report_bug_dialog.py`.
Visible acceptance and later service setup are in `docs/BUG_REPORTING.md`.

## Experiment Data Sharing

Start with `core/data_sharing.py`, `runtime/data_sharing.py`, the data-sharing package
guide and [Data sharing](../DATA_SHARING.md). The dialog/controller use app-owned
workers and snapshots; neither HTTP nor authored asset hashing belongs on the GUI
thread or in presentation callbacks. The independent Worker has its own source map,
registration tooling and Node SQLite tests under `services/results/`.
For linked Library identity checks, use `data_sharing/library_scope.py` and core's
canonical `library_origin.py` receipt reader. The planned lab-code contribution
bridge and current separation of Library/Results grants are in the canonical guide.

Use the data-sharing focused route, runtime for launch/finalization changes, and repo
precommit for shared behavior. Run the Worker's Node tests separately as documented;
the Python harness does not run them. Registered GUI coverage is
`tests/gui/test_data_sharing_dialog.py`; visible sizing and two-machine staging
acceptance remain explicit platform/service checks.

## Settings Test Mode

Experiment Test Mode is available in source and installed Windows/Linux builds through
Settings > Local experiment testing. Start with `gui/controller.py` and
`gui/settings_dialog.py`; registered `tests/gui/test_welcome_settings_flow.py` covers
availability and persistence for both build types. Use the GUI focused route. For
visible acceptance, open Settings at `700x610`, enable the option, reopen Settings to
check persistence, and disable it again to restore ordinary launch checks.

## Cognitive Load FPVS

For Masking, start with `core/masking.py`, `core/masking_presets.py`,
`core/compiler_masking.py`, `core/scene_models.py`, and [Masking](../MASKING.md).
Masking block order and extra catch placement/SOA sampling live in `core/compiler.py`;
catch creation, agreement/code validation and source-pool selection in `core/masking.py`;
GUI retry seeding in `gui/document.py`. Visible catch conditions are authored through
`gui/condition_setup_step.py` and `gui/document_conditions.py`, with registered coverage
in `tests/gui/test_masking_conditions.py`. The legacy automatic Catch trials tab remains
in `gui/condition_modifier_dialog.py`. Instruction text alignment flows from
`core/task_models.py` through `runtime/task_runner.py` to `engines/psychopy_tasks.py`;
its item table and preview live in `gui/condition_task_dialog.py`.
The joined target/answer/PAS v2
trial table and detection outcomes live in `runtime/masking_report.py` and `session_export.py`.
Native sources are modifier-owned; pre/post tasks remain outside stream timing.
Optional `masking.event_triggers` uses the compiler's generic trigger schedule;
focused compiler/project-io/engine routes cover frame alignment and persisted opt-in.
Catch schema guards span project/config, RunSpec and SessionPlan; read the Masking
contract before changing compatibility or exports. Use compiler/project-io/runtime/engine/gui
focused routes, then repo precommit; visible Qt acceptance remains an explicit opt-in.

For Library downloads, the publisher applies the temporary COM3 bundle policy;
see [Experiment Library](../EXPERIMENT_LIBRARY.md) before changing port handling.

For **FPVS Condition Modifiers**, start with `core/condition_modifiers.py`,
`core/modifier_presets.py`, and [Condition modifiers](../CONDITION_MODIFIERS.md).
Add/remove actions default to the current condition; `apply_modifier_draft` preserves
unchanged shared assignments when applying the dialog draft.
The existing task compiler/runner owns execution; grouped workflows do not add a
third task phase or change FPVS timing. Use core/compiler/project-io/runtime/engine
focused routes, GUI registered coverage, then repo precommit.

For Cognitive Load FPVS, begin with `core/cognitive_load_presets.py`,
`core/backward_counting.py`, `core/compiler_tasks.py` and
[`Cognitive Load FPVS`](../COGNITIVE_LOAD_FPVS.md). The preset reuses ordinary image
conditions; the library modules also work in other oddball projects. Use core,
compiler, runtime and project-io focused routes, GUI registered coverage, then repo
precommit. Task estimates and clocks never enter the `RunSpec` frame contract.

## Repeat Participant Sessions

Start with `runtime/participant_sessions.py` for read-only next-number lookup and
atomic reservation, `runtime/participant_history.py` for legacy/full/compact history,
and `runtime/session_export.py` for session numbering in reports. Execution metadata
owns `participant_session_number`; compiled timing and session seeds are unchanged.
`ProjectSettings.allow_repeated_participant_sessions` is edited in Setup > Project;
both Home and Run share the participant launch guard. Read
[`Runtime execution`](../RUNTIME_EXECUTION.md#repeat-participant-sessions) and the
launch section of [`GUI workflow`](../GUI_WORKFLOW.md). Use runtime/core/project-io
and GUI focused routes, then repo precommit. GUI acceptance remains visible/manual
unless an explicitly approved safe Qt environment is available.

## Attentional Blink Presentation Rate

For repeated targets within a burst (including MSMS AB), the same core helper owns
`target_count`, `target_interval_slots` and `omit_first_t2`, exact retiming and
per-pair cycle indices. Use the repeated-target section in
`docs/EXPERIMENT_CATEGORIES.md`. Keep GUI preview/apply, recall compilation,
runtime preflight and burst/event reports consistent; run compiler/runtime/GUI
focused routes and repo precommit. Defaults remain single-pair bursts.

Setup > Design edits the shared rate through `gui/attentional_blink_stream_designer.py`
and the atomic `gui/document_conditions.py` apply method, alongside **Bursts per SOA**.
Core owns exact five-second burst, character, SOA and display-frame compatibility in
`core/attentional_blink_stream.py`. `core/attentional_blink_presets.py` owns the new
24-bursts-per-SOA default and the two typed Enter/Next recall questions.
`compiler_tasks.py` derives answer keys from each compiled target pair; the session
compiler requires Space before every recall burst. `runtime/attentional_blink_report.py`
owns the burst journal, typed SOA summaries and Excel export;
`gui/attentional_blink_data_dialog.py` exposes saved SOA/trigger results from
View > T1 and T2 Accuracy, including accuracy for identified test sessions.
`gui/main_window.py` selects that view for AB and Fixation Task Accuracy for other categories.
Use GUI/core/compiler/runtime focused checks and the visible acceptance path in
`docs/GUI_WORKFLOW.md`; shared changes also need repo precommit.

## Setup Design Verification

For Conditions stimulus-type switching, read `gui/condition_setup_step.py` and
`gui/document_conditions.py`. Safe regressions are in `tests/unit/test_condition_modality.py`;
Yes/No, pending word edits and layout coverage are registered in
`tests/gui/test_setup_conditions.py`. Use GUI focused checks and repo precommit.
For Conditions spacing and mode labels, also read `gui/setup_wizard_page.py` and
`gui/window_helpers.py`. Registered layout coverage checks aligned ready-state panels
and vertical growth at 1120x820, 1120x960 and 1448x1086; other compact steps stay centered.

For Manage Projects renaming, start with `gui/manage_projects_dialog.py`, its
controller bindings and `core/project_service.py`. Verify metadata-only persistence
and open-document draft preservation with `tests/unit/test_project_service.py` and
registered `tests/gui/test_manage_projects_rename.py`. The dialog fits `860x520`.

For project-opening responsiveness and save feedback, start with `gui/controller.py`,
`gui/document.py`, `gui/main_window.py`, and registered
`tests/gui/test_frontend_responsiveness.py`. Preview reuse/error recovery is covered
by `tests/gui/test_design_setup_step.py`. Use the existing application-owned job
lifecycle for project reads and keep document/widget construction on the GUI thread.

The eight-step Setup flow and shared dialog acceptance sizes are documented in
[GUI workflow](../GUI_WORKFLOW.md#setup-design-and-manual-acceptance). Use the GUI
focused route for edits and the repo precommit tier for shared component changes.
Current category and Design contracts are documented in
[`EXPERIMENT_CATEGORIES.md`](../EXPERIMENT_CATEGORIES.md); implementation history is
in the completed plans directory.

For the 1120x820 Setup default and its oddball image editor, read
`tests/gui/test_design_setup_step.py` for full-window and source-choice coverage.
For the shared visual editor embedded in Setup > Design, read
[`VISUAL_EXPERIMENT_DESIGNER.md`](../VISUAL_EXPERIMENT_DESIGNER.md) and
[`EXPERIMENT_CATEGORIES.md`](../EXPERIMENT_CATEGORIES.md). Category is fixed at creation;
image pairs and their ISI editor are retired. Attentional-Blink streams expose
shared distractor/T1/T2 pools, three SOAs, burst count and an onset bracket. Read
`core/attentional_blink_presets.py`, `core/attentional_blink_stream.py`, and
`gui/attentional_blink_stream_designer.py` for that route; native sizing uses
  `gui/attentional_blink_character_size.py`. Registered
`tests/gui/test_attentional_blink_stream_designer.py` covers the new setup workflow.
There are no mode tabs or masking controls.
GUI owns interactions; `core/experiment_design.py` owns ordinary cycle mathematics
and historical masking calculations that have no current GUI.
Retired image-pair projects are rejected by category validation, and old compiled
copies by runtime preflight and the engine before launch. Native AB sources, playback
and onset exports follow existing layer boundaries. The overview works without a
preview display selection; achieved frames live under Timing & display details.
`gui/design_setup_step.py` integrates condition selection, pending apply/discard,
and worker-aware navigation around the shared `ExperimentDesignerWidget`. Folder
imports immediately update sources; timing discard preserves those imports.
`is_importing()` blocks navigation during source mutation; `is_busy()` also includes
thumbnail decoding and protects condition disposal and editor teardown. Ordinary
image/word features remain FPVS Oddball Paradigm. Legacy conflicts require explicit separation.
Use GUI/core/compiler/runtime/engine focused verification and registered
`tests/gui/test_experiment_designer.py`, `tests/gui/test_design_setup_step.py`,
category and wizard modules for approved visible acceptance. Check the embedded
`1000x600` isolated content budget and the complete `1120x820` wizard in both themes,
plus the expanded `1448x1086` mockup size. Next applies the embedded design; the
standalone editor retains its Apply action. Check numeric edits, navigation validity,
source-folder hit targets, readable schematic tokens and proportional detail.

For AB fixation visibility, use `gui/fixation_settings_page.py`, the core fixation
settings/RunSpec owners, and `engines/psychopy_engine.py` / `psychopy_stimuli.py`.
`tests/gui/test_fixation_settings_page.py` covers both AB layouts and save/reopen;
stream GUI tests cover visible/hidden layouts, and engine tests verify no cross
resources or draws with unchanged character timing and triggers.

For long Windows paths, start with `core/paths.py` (`filesystem_path`, containment
resolution and relative serialization), then the affected I/O entry point. Bundle reads,
origin hashing and import collisions use `core/project_bundle.py`; download cache I/O
uses `library/cache.py`. Keep namespace prefixes out of saved JSON. Project-I/O and
Library focused routes cover transfer with Windows long-path policy disabled. The
GUI focused route includes safe post-import opening, root/recent preferences, restart
discovery, template storage and image-readiness signature regressions in
`test_bundle_open_setup.py`; core, preprocessing and compiler/runtime routes include
the image path regressions. Imported display detection and image-size previews use
physical pixels at the experiment boundary and logical pixels for Qt painting;
registered GUI scaling coverage is in the config import and setup display modules.

## Unicorn Recorder Integration

Start with `runtime/recording.py`, `runtime/unicorn_recorder.py`,
`runtime/unicorn_recorder_windows.py`, `triggers/unicorn_udp_backend.py`,
`runtime/triggers.py`, the Settings recording controls and
[Runtime execution](../RUNTIME_EXECUTION.md#trigger-behavior). The
[active Unicorn plan](../exec-plans/active/unicorn-hybrid-black-support.md) separates
the implemented software path from pending receiver and physical timing qualification.
Normal Unicorn launches send real markers after configuration and Recorder readiness
pass; Test/Pilot always selects null. Full qualification remains pending, with a
retained 426-marker classic-BDF/CSV receiver test. Never use a fake socket test to
claim BDF acceptance.
Home and Run share the automatic Recorder process/raw-file check in the launch worker;
no manual recording checkbox, UI-thread OS probe, or marker test is part of that check.
Readiness does not establish receiver/physical-timing qualification; that pending
evidence status does not block the normal launch workflow.

Use triggers/runtime/engine/gui/docs focused routes, then repo precommit. Adapter tests
must use fake sockets and never send to an active Recorder. New adapter coverage is
explicitly registered in the triggers route. Registered GUI checks require an approved
visible session. Recording choice persists in `ProjectSettings.recording`; Settings Apply uses the
project service and ignores obsolete global overrides. Recording choice is separate
from project COM fields;
the broader named-profile/display plan remains planned work.

## Planning Route

- Planning map: `docs/PLANS.md`
- Plan rules: `docs/exec-plans/README.md`
- Current implementation: `docs/exec-plans/active/`
- Concrete future work: `docs/exec-plans/planned/`
- Historical implementation notes: `docs/exec-plans/completed/`
- Measured debt: `docs/exec-plans/tech-debt-tracker.md`

Read completed plans only when historical rationale is necessary. Never use them in
place of current architecture and workflow documents.
