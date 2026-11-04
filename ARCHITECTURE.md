# Architecture

FPVS Studio's package and dependency map. Start with `AGENTS.md` and
[the task index](docs/agent/agent-index.md); open detailed contracts only for the
behavior being changed. Source package guides add local rules.

## Application Shape

The PySide6 GUI edits projects and requests engine-neutral compilation. Runtime
coordinates sessions; the PsychoPy engine renders compiled stimuli with lazy imports.
Windows/Linux use the presentation worker; macOS source uses a child process's main
thread for Cocoa playback and refresh probes. Test/Pilot explicitly selects null
triggers; normal Windows/Linux launches retain hardware and display preflight.
Mac tests retain refresh verification and transient calibration; EEG is excluded.

Guided Setup keeps Timing (step 3) separate from a two-column Display & Session
step (step 4). GUI retains timing drafts across that transition; core still owns
validation and compilation, including exact shared-refresh compatibility for mixed
image presentation rates. See [Setup workflow](docs/GUI_WORKFLOW.md#frameless-setup-layout-and-copy).

Core owns randomized block membership and occurrence identity; see the
[block contract](docs/SESSION_PLAN.md#explicit-randomized-condition-blocks).

## Package Map

| Owner | Responsibility |
| --- | --- |
| `src/fpvs_studio/app/` | Thin startup entry points and wiring |
| `src/fpvs_studio/assets/` | Packaged branding and licensed task fonts |
| `src/fpvs_studio/core/` | Editable models, validation, compilation, portable contracts and project services |
| `src/fpvs_studio/data_sharing/` | Consent, protected credentials, durable outbox, delivery and comparisons |
| `src/fpvs_studio/developer/` | Gated maintainer publishing and catalog services |
| `src/fpvs_studio/engines/` | Presentation interface, PsychoPy rendering and graphics lifetime |
| `src/fpvs_studio/gui/` | PySide6 views, document/controller bindings, components and worker lifecycle |
| `src/fpvs_studio/library/` | Catalog, enrollment, verified downloads, submissions and update discovery |
| `src/fpvs_studio/preprocessing/` | Image inspection/intake, normalization, derived assets and manifests |
| `src/fpvs_studio/runtime/` | Launch, preflight, participant/task/session flow, scoring, recovery and exports |
| `src/fpvs_studio/support/` | Diagnostics, reviewed reports, local drafts and automatic crash outbox |
| `src/fpvs_studio/tools/` | Reserved native utility namespace; Image Resizer currently uses GUI/preprocessing |
| `src/fpvs_studio/triggers/` | Serial, parallel and UDP adapters, discovery and transport evidence |
| `src/fpvs_studio/updates/` | Independent updater protocol, verified downloads, bounded cache and install handoff |

`src/fpvs_studio/updater_main.py` is the separate updater entry. Its windows live in
GUI; it excludes experiment runtime/engine dependencies. `packaging/` owns
PyInstaller/Inno builds, release assets, installed-file reconciliation and patch
application. `tests/` contains unit/integration and registered Qt coverage.

External ownership: private sibling `../OpenFPVS` owns the OpenFPVS website, Library
service and Results backend. Private `zcm58/FPVS-Studio-Feedback` owns report intake
and maintainer email. `services/results/` is an undeployed reference, not the live
backend. Consult each repository's own guidance for service changes.

## Contract Flow

```text
ProjectFile -> core compiler -> RunSpec (one condition)
ProjectFile -> session compiler -> SessionPlan (ordered runs + pre/post tasks)
RunSpec / SessionPlan -> runtime (task flow + engine playback)
Runtime -> core execution results -> exporters -> project logs and detailed artifacts
```

| Contract or seam | Canonical owner |
| --- | --- |
| Editable state and migrations | `core/models.py`, `core/migrations.py` |
| Run/session/result schemas | `core/run_spec.py`, `core/session_plan.py`, `core/execution.py` |
| Effective frequency/duration and ordering | `core/condition_timing.py`, `core/session_ordering.py` |
| Common display frame grid for mixed image rates | `core/validation.py`; shared by authoring, readiness and compilation |
| Independent participant reuse policies and randomization domains | `core/randomization.py`; [contract](docs/SESSION_PLAN.md#independent-randomization) |
| Task definitions and condition modifiers | `core/task_models.py`, `core/condition_modifiers.py` |
| Optional single-target fixation onset window | `core/compiler_fixation.py`; compiled frame events remain the runtime contract |
| Library mouse-task compatibility floor | `core/library_publish.py`; final prepared-bundle verification rechecks it |
| Manifest schemas and persistence | `preprocessing/models.py`, `preprocessing/manifest.py` |
| Portable paths and project persistence | `core/paths.py`, `core/project_service.py` |
| Guarded current-project Library replacement | `core/project_bundle_update.py`; ordinary imports never replace projects |
| Runtime recording and evidence | `runtime/recording.py`, `runtime/acquisition_evidence.py` |
| Interrupted occurrence recovery | `runtime/condition_recovery.py` |
| Participant results | `runtime/session_export.py`, `runtime/participant_results.py`; [contract](docs/RUNTIME_EXECUTION.md#exports) |
| GUI task lifetime through native cleanup | `gui/update_lifecycle.py`, `gui/thread_completion.py` |
| Mac source/display/input adapters | `scripts/macos-source.sh`, `runtime/macos_display.py`, `runtime/macos_session_process.py`, `engines/psychopy_macos_display.py`, `gui/local_test_display_dialog.py`, `gui/native_files.py`; [support](docs/MACOS_SUPPORT.md) |

## Dependency Rules

- Core owns compilation, frame schedules, session order and fixation realization.
  Runtime consumes compiled contracts and owns execution/scoring; engine types never
  enter project schemas or exports. Runtime imports no PySide6 widgets.
- Only engines import PsychoPy, lazily. Core and preprocessing are GUI/hardware
  independent; preprocessing owns image work and may use neutral core contracts.
- GUI delegates domain work to services. Workers retain their lifetime through native
  cleanup and never access widgets or block the GUI thread.
- Persist project-facing paths as project-relative POSIX strings. Filesystem namespace
  adaptation belongs to `core/paths.py`. App templates remain outside projects at
  `<FPVS Studio Root>/.fpvs-studio/templates/`.
- Compiled task screens and native geometry cannot change FPVS scheduling. The oddball
  marker defaults to `55`; nonstandard values require explicit user direction and
  `allow_nonstandard_oddball_trigger_code`.
- Hardware selection, transport writes, observed receiver integrity and physical
  timing are distinct evidence. Software tests never qualify wiring or EEG timing.
- The updater never edits projects. Explicit Download and Install preserves the Save
  gate and verified helper handoff; Inno owns baseline/target verification and mutation.
- `tests/unit/test_import_boundaries.py` checks internal dependency rules without
  importing production modules.

## Source-of-Truth Documents

| Concern | Current contract |
| --- | --- |
| Product and category scope | `docs/PRODUCT_SENSE.md`, `docs/EXPERIMENT_CATEGORIES.md` |
| GUI and design | `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md` |
| Compilation/session flow | `docs/RUNSPEC.md`, `docs/SESSION_PLAN.md` |
| Runtime, recording and exports | `docs/RUNTIME_EXECUTION.md` |
| Engine seam | `docs/ENGINE_INTERFACE.md` |
| Library/import/update/publishing | `docs/EXPERIMENT_LIBRARY.md` |
| Results and storage | `docs/DATA_SHARING.md`, `docs/REPORTING_STORAGE.md` |
| Diagnostics and service activation | `docs/BUG_REPORTING.md` |
| Environment, release and security | `docs/ENVIRONMENT.md`, `docs/PACKAGING.md`, `docs/SECURITY.md` |

## Task Context Recipes

Use the task index for scope guidance and contracts. Search
[optional topic recipes](docs/agent/task-recipes.md) for additional entry points.
`docs/PLANS.md` routes active work; completed plans supply history.
Use `docs/index.md` for the full map.

## Verification and Documentation Freshness

The task index owns verification routes. Types target all-source Windows first,
then secondary Mac adapters. GitHub adds macOS source and cross-OS bundle
checks alongside documentation publishing. Update this map and nearest guide when
ownership or boundaries change; keep behavior in canonical contracts. Measured debt
belongs in `docs/exec-plans/tech-debt-tracker.md`; versions live in `pyproject.toml`.
