# Architecture

This file is the compact map for agent work. Keep detailed design decisions in `docs/`
and update this map when package boundaries or source-of-truth contracts move.

## Application Shape

FPVS Studio is a Windows-focused PySide6 desktop authoring app. The GUI creates and edits
project models, compiles them into neutral execution contracts, and launches runtime flows.
Timing-critical presentation is isolated behind runtime and engine interfaces; only engine
code may lazily import PsychoPy.

## Package Map

- `src/fpvs_studio/app/`: application entry points and startup wiring.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding,
  the Home/Setup Wizard workflow, and the `gui/components.py` public component/theme
  surface.
- `src/fpvs_studio/core/`: editable project models, validation, compilation, run/session
  contracts, project persistence, and engine-neutral domain logic.
- `src/fpvs_studio/preprocessing/`: original image import, inspection, image
  normalization, generated variants, and manifests. This layer must stay independent
  of GUI runtime and PsychoPy.
- `src/fpvs_studio/tools/`: imported/reference tool code for future Studio-native
  utilities. Current files from FPVS Toolbox are planning ground truth for the image
  preparation tool and must be adapted before user-facing integration.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session execution, participant
  history, and runtime flow over compiled contracts.
- `src/fpvs_studio/engines/`: presentation engine interface and PsychoPy implementation.
- `src/fpvs_studio/triggers/`: optional trigger backend interfaces and hardware adapter
  scaffolding used by runtime while keeping core contracts hardware-neutral.
- `tests/`: unit, integration, and pytest-qt GUI coverage.

## Documentation Freshness

When a change moves source-of-truth contracts, adds or removes top-level packages, changes
dependency boundaries, changes task context recipes, or changes supported verification
commands, update this map and the relevant nested `AGENTS.md` or deeper `docs/` page in
the same change.

Run `python -m pytest -q tests\unit\test_harness_docs.py` after harness-documentation
edits. The full quality gate also runs this check.

## Planned Module Decomposition

File length is a warning sign, not the architecture rule. Prefer splits when a file mixes
distinct responsibilities, forces broad context reads for narrow tasks, or makes focused
tests hard to locate. Do not split cohesive files only to satisfy a line-count target.

The preferred split pattern is a behavior-preserving move behind the current public API:
keep imports stable first, move one responsibility at a time, and run the narrow gate for
that layer after each move.

Current planned seams:

- `src/fpvs_studio/gui/document.py` remains the GUI-facing `ProjectDocument` facade.
  Focused helper modules own document support types/defaults
  (`document_support.py`), condition mutation (`document_conditions.py`), stimulus import
  and manifest sync (`document_stimuli.py`), and validation/compilation/preflight/launch
  coordination (`document_runtime.py`).
- `src/fpvs_studio/core/compiler.py` keeps the public `compile_run_spec` and
  `compile_session_plan` entry points stable. Focused helper modules own shared compiler
  support/errors/ids (`compiler_support.py`), condition selection and validation
  (`compiler_conditions.py`), manifest/filesystem image-path resolution
  (`compiler_assets.py`), stimulus/trigger/transition schedules
  (`compiler_schedules.py`), and fixation target/event planning
  (`compiler_fixation.py`).
- `src/fpvs_studio/engines/psychopy_engine.py` keeps the `PsychoPyEngine` public
  surface and main frame loop stable. Focused helper modules own lazy PsychoPy loading
  (`psychopy_loader.py`), text-screen rendering (`psychopy_text_screens.py`), stimulus
  preparation/draw decisions (`psychopy_stimuli.py`), timing configuration/QC
  (`psychopy_timing.py`), runtime metadata (`psychopy_metadata.py`), window/fixation
  stimulus construction (`psychopy_window.py`), and trigger lookup/emission
  (`psychopy_triggers.py`).
- GUI session/fixation authoring uses `session_pages.py` as a compatibility export
  facade. Session structure editing lives in `session_structure_page.py`; fixation-task
  controls live in `fixation_settings_page.py` because fixation behavior is expected to
  evolve independently.
- GUI component/theme work starts from `src/fpvs_studio/gui/components.py`. It re-exports
  shared page/card/status/path widgets, owns reusable button roles and stylesheets, and
  keeps raw design tokens in `design_system.py`.
- GUI workflow composition is Home-first. `main_window.py` uses a stack with Home and
  `setup_wizard_page.py`; the wizard uses a six-step top-progress flow with a
  simplified Conditions setup step where users assign base/oddball image folders and
  can optionally create derived-variant control conditions. Detailed Conditions,
  Runtime, Session, and Fixation widgets stay internal for step-level advanced access
  rather than visible top-level tabs; Stimuli Manager remains an internal support page,
  not a guided setup step.
- GUI project management uses `manage_projects_dialog.py` as a themed component-layer
  surface while `controller.py` owns disk-backed project discovery, recent-project
  settings, and Recycle Bin confirmation/deletion side effects.
- Condition-template profile management keeps `condition_template_manager_dialog.py` as
  the manager dialog and compatibility import point. The profile editor dialog lives in
  `condition_template_profile_editor_dialog.py`.
- Large GUI page modules are acceptable when they model one cohesive page or editor. Split
  them only when a subcomponent has an independent lifecycle, test surface, or reusable
  responsibility.
- Large GUI tests should be split by workflow when they become hard to run or review
  narrowly; production-module splits take priority over test-file line-count cleanup.

Refactor priority:

1. Keep the `ProjectDocument` helper split cohesive as GUI document behavior evolves.
2. Keep compiler helper modules cohesive as compile behavior evolves.
3. Keep the PsychoPy engine helper split conservative. Move playback-loop code only when
   a tested seam is clear; frame-accurate behavior is easier to preserve when the loop
   stays readable and contiguous.
4. Keep future fixation-task GUI work in `fixation_settings_page.py` unless it changes
   model compilation or runtime scoring, which remain core/runtime responsibilities.

## Task Context Recipes

Use these first reads before opening broad trees:

- GUI task: `src/fpvs_studio/gui/AGENTS.md`,
  `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, the specific page/dialog module, matching
  `tests/gui/test_*.py`, and `tests/gui/helpers.py` if workflow setup matters.
- Compiler/session task: `src/fpvs_studio/core/AGENTS.md`,
  `src/fpvs_studio/core/compiler.py`,
  `src/fpvs_studio/core/session_plan.py`,
  `docs/RUNSPEC.md`, and `docs/SESSION_PLAN.md`.
- Runtime task: `docs/RUNTIME_EXECUTION.md`,
  `src/fpvs_studio/runtime/launcher.py`,
  `src/fpvs_studio/runtime/preflight.py`,
  `src/fpvs_studio/core/execution.py`, and the relevant
  `tests/unit/test_runtime_*.py` file.
- Preprocessing task: `src/fpvs_studio/preprocessing/`,
  `src/fpvs_studio/core/models.py`, `tests/unit/test_preprocessing_assets.py`,
  and `tests/unit/test_preprocessing_inspection.py`.
- Image preparation tool task: `docs/exec-plans/planned/fpvs-toolbox-image-prep-tool.md`,
  `src/fpvs_studio/tools/`, `src/fpvs_studio/preprocessing/`,
  `src/fpvs_studio/gui/components.py`, and `src/fpvs_studio/gui/AGENTS.md`.
- Docs-only task: `AGENTS.md`, this file, `docs/index.md`, and the doc being edited.
  Avoid source reads unless the doc describes a concrete contract.
- Feature-sized workflow task: read `docs/PLANS.md` and `docs/exec-plans/README.md`,
  create or update an active plan under `docs/exec-plans/active/`, then read the
  related package docs and tests.
- Docs garbage-collection task: read `docs/exec-plans/plan-review-workflow.md`, run
  `.\scripts\check_docs_hygiene.ps1`, then update plan status or move stale docs.

## Contract Flow

`ProjectFile` models compile into single-condition `RunSpec` entries. Session settings and
ordered conditions compile into a `SessionPlan` that owns realized fixation target-count
selection. Runtime consumes `RunSpec` or `SessionPlan` and produces core-owned execution
results. Exporters serialize those results without moving contracts into engine code.

## Dependency Rules

- GUI may use core services and runtime launch APIs, but must not own compilation,
  fixation scoring, or session flow.
- Runtime may consume compiled contracts and coordinate flow, but must not depend on
  PySide6 widget code.
- Engines render presentation screens and may use PsychoPy lazily inside engine modules.
- Core and preprocessing must remain engine-neutral.

## Harness Commands

- GitHub Actions CI: `.github/workflows/ci.yml` runs `.\scripts\check_quality.ps1`
  on Windows for pushes and pull requests.
- Full gate: `.\scripts\check_quality.ps1`
- Harness garbage collection: `.\scripts\check_gc.ps1`
- Docs hygiene: `.\scripts\check_docs_hygiene.ps1`
- GUI smoke/workflow: `.\scripts\check_gui.ps1`
- Runtime: `.\scripts\check_runtime.ps1`
- Compiler/session: `.\scripts\check_compiler.ps1`
- Preprocessing: `.\scripts\check_preprocessing.ps1`
- Line-count report: `.\scripts\report_line_counts.ps1`
- Workspace cleanup: `.\scripts\clean_workspace.ps1`

## Deeper Docs

- Docs entry point: `docs/index.md`
- Product and v1 scope: `docs/PRODUCT_SENSE.md`, `docs/product-specs/`, and
  `docs/FPVS_Studio_v1_Architecture_Spec.md`
- Design docs: `docs/DESIGN.md` and `docs/design-docs/`
- Feature execution plans: `docs/PLANS.md` and `docs/exec-plans/`
- GUI behavior and smoke-test guidance: `docs/FRONTEND.md` and `docs/GUI_WORKFLOW.md`
- Quality, reliability, and security: `docs/QUALITY_SCORE.md`, `docs/RELIABILITY.md`,
  and `docs/SECURITY.md`
- Engine boundary: `docs/ENGINE_INTERFACE.md`
- Run contract: `docs/RUNSPEC.md`
- Session contract: `docs/SESSION_PLAN.md`
- Runtime/export flow: `docs/RUNTIME_EXECUTION.md`
