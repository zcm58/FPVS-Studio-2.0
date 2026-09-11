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
| `updates` | Release checks, direct patch selection, bounded cache/locking, verified downloads/launch, or update GUI shutdown coordination | `src/fpvs_studio/updates/AGENTS.md` and `docs/PACKAGING.md` |
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

## Skill Routing

| Task | Repo-local skill |
| --- | --- |
| PySide6 layout, components, workers, status/error UX | `.agents/skills/pyside6-gui-cleanup/SKILL.md` |
| Add or maintain registered pytest-qt coverage | `.agents/skills/pytest-qt-smoke/SKILL.md` |
| Project roots, dialogs, persistence, export/import paths | `.agents/skills/project-path-audit/SKILL.md` |
| Protected retired paths or historical behavior boundaries | `.agents/skills/legacy-boundary-review/SKILL.md` |
| PsychoPy migration across compile/runtime/engine seams | `.agents/skills/fpvs-psychopy-migration/SKILL.md` |

Read a selected skill completely before acting. A passing skill audit is sufficient
evidence for its invariant unless the task changes that audit or boundary.

## Patch Updates

Start with `updates/patches.py` for authenticated direct-patch selection and baseline
file verification. `scripts/build_patch.py` generates sparse payloads and release JSON;
`packaging/inno/patch_upgrade.iss` validates and applies them through the shared installer.
Use updates/packaging focused routes, then repo precommit. Native lifecycle acceptance
uses `scripts/check_patch_installer_lifecycle.py` with isolated synthetic app identities.
Exact release steps and recovery limits live in `docs/PACKAGING.md#direct-patch-releases`.

## Settings Test Mode

Experiment Test Mode is available in source and installed Windows/Linux builds through
Settings > Local experiment testing. Start with `gui/controller.py` and
`gui/settings_dialog.py`; registered `tests/gui/test_welcome_settings_flow.py` covers
availability and persistence for both build types. Use the GUI focused route. For
visible acceptance, open Settings at `700x610`, enable the option, reopen Settings to
check persistence, and disable it again to restore ordinary launch checks.

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

Setup > Design edits the shared rate through `gui/attentional_blink_stream_designer.py`
and the atomic `gui/document_conditions.py` apply method. Core owns exact character,
SOA, and display-frame compatibility in `core/attentional_blink_stream.py`. Use GUI/core
focused checks and the visible acceptance path in `docs/GUI_WORKFLOW.md`.

## Setup Design Verification

For Manage Projects renaming, start with `gui/manage_projects_dialog.py`, its
controller bindings and `core/project_service.py`. Verify metadata-only persistence
and open-document draft preservation with `tests/unit/test_project_service.py` and
registered `tests/gui/test_manage_projects_rename.py`. The dialog fits `860x520`.

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
image pairs and their ISI editor are retired. Attentional-Blink letter streams expose
shared digit/T1/T2 pools, three SOAs, and a full-cycle onset bracket. Read
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

For long Windows image paths, start with `core/paths.py` (`filesystem_path`, containment
resolution and relative serialization), then the image I/O entry point. Keep namespace
prefixes out of saved JSON. Core, preprocessing and compiler/runtime focused routes
include the Windows path regression files.

## Planning Route

- Planning map: `docs/PLANS.md`
- Plan rules: `docs/exec-plans/README.md`
- Current implementation: `docs/exec-plans/active/`
- Concrete future work: `docs/exec-plans/planned/`
- Historical implementation notes: `docs/exec-plans/completed/`
- Measured debt: `docs/exec-plans/tech-debt-tracker.md`

Read completed plans only when historical rationale is necessary. Never use them in
place of current architecture and workflow documents.
