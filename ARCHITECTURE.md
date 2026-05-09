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
- `src/fpvs_studio/assets/`: packaged static image assets used by the GUI at runtime,
  currently the shared FPVS Studio app icon.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding,
  the Home/Setup Wizard workflow, and the `gui/components.py` public component/theme
  surface. The main window also hosts lightweight in-window utilities from the `Tools`
  menu.
- `src/fpvs_studio/core/`: editable project models, validation, compilation, run/session
  contracts, project persistence, and engine-neutral domain logic.
- `src/fpvs_studio/preprocessing/`: original image import, inspection, image
  normalization, generated variants, and manifests. This layer must stay independent
  of GUI runtime and PsychoPy.
- `src/fpvs_studio/tools/`: reserved package for future Studio-native utilities.
  Historical FPVS Toolbox image-resizer references live under
  `docs/references/archive/fpvs-toolbox-image-resizer/`.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session execution, participant
  history, seed-history lookup, project-level run-log exports, and runtime flow over
  compiled contracts.
- `src/fpvs_studio/engines/`: presentation engine interface and PsychoPy implementation.
- `src/fpvs_studio/triggers/`: optional trigger backend interfaces and hardware adapter
  scaffolding used by runtime while keeping core contracts hardware-neutral.
- `src/fpvs_studio/updates/`: backend-only GitHub Releases update checks, installer
  download helpers, and explicit installer launch support for the GUI update flow.
- `tests/`: unit, integration, and pytest-qt GUI coverage.
- `packaging/`: developer packaging configuration for PyInstaller-based Windows
  executable builds.

## Documentation Freshness

When a change moves source-of-truth contracts, adds or removes top-level packages, changes
dependency boundaries, changes task context recipes, or changes supported verification
commands, update this map and the relevant nested `AGENTS.md` or deeper `docs/` page in
the same change.

Run `python -m pytest -q tests\unit\test_harness_docs.py` after harness-documentation
edits. The full quality gate also runs this check.

## Versioning And Packaging

The current app version is declared once in `pyproject.toml`. The Python distribution
name is `fpvs-studio`, while the user-facing application name remains FPVS Studio.
`src/fpvs_studio/__init__.py` derives `__version__` from installed package metadata, and
`tests/unit/test_package_metadata.py` guards the contract. Use `docs/PACKAGING.md` for
the developer version-bump and build workflow.

Local executable builds use `scripts/build_exe.ps1`, which runs the checked-in
PyInstaller spec at `packaging/pyinstaller/fpvs_studio.spec` and writes ignored build
artifacts under `build/` and `dist/`. Installer builds use `scripts/build_installer.ps1`,
which wraps the whole PyInstaller onedir folder with the checked-in Inno Setup script at
`packaging/inno/fpvs_studio.iss` and writes `dist\installer\FPVS-Studio-Setup-*.exe`.
GitHub release uploads remain a manual release step.

The shared app icon lives in `packaging/assets/fpvs-studio.ico` for release tooling and
`src/fpvs_studio/assets/fpvs-studio.ico` for GUI window icons. README/GitHub branding
images live under `docs/assets/`.

In-app update checks use `src/fpvs_studio/updates/` to query GitHub Releases, compare
against `fpvs_studio.__version__`, download the expected `FPVS-Studio-Setup-*.exe`
asset to a user-writable update cache, and launch the Inno installer only after explicit
user confirmation from `File > Check for Updates`. The GUI owns presentation and Qt
threading; the updater backend must stay free of PySide6, PsychoPy, project-folder, and
runtime dependencies.

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
- GUI workflow composition is Home-first. `main_window.py` uses a stack with a
  centered Home launch card and `setup_wizard_page.py`; `Tools > Image Resizer`
  adds a standalone in-window utility page for folder-level FPVS image optimization
  without mutating project conditions.
  `root_folder_setup_dialog.py` provides first-run and Settings-accessible guidance
  for choosing the FPVS Studio Root Folder before the native folder picker opens.
  `StudioMainWindow` owns mode-specific sizing: compact `1120x720` launch-surface
  sizing for Welcome/Home handoff, compact Setup sizing, focused utility sizing for
  lightweight tools, and larger workspace sizing for future dense tool pages.
  The wizard uses a six-step compact top-progress flow: Project, Conditions,
  Experiment, Fixation, Response, and Review. Conditions handles condition identity,
  list actions, base/oddball folder assignment, control-condition creation, and image
  normalization.
  Setup steps share a compact content surface, with the top progress stepper carrying
  complete-state feedback instead of page-wide completion bars. The setup surface is
  guarded by pytest-qt coverage that checks all six steps at `1120x720` for stable
  frame positioning, disabled vertical scrolling, and visible child-widget clipping.
  Experiment combines display and session settings in one compact centered card; session
  order is always randomized within each block using the random order seed while legacy
  fixed-order fields stay schema-compatible. Fixation handles schedule/timing, and
  Response handles accuracy tracking, response key/window, appearance, and live preview.
  Display settings are limited to refresh rate and black/dark-gray background choices. Detailed
  Conditions no longer exposes a wizard advanced editor; duty-cycle selection is
  centralized in the Project Details condition template selector. Stimuli Manager
  remains an internal support page, not a guided setup step.
- GUI project management uses `manage_projects_dialog.py` as a themed component-layer
  surface while `controller.py` owns disk-backed project discovery, recent-project
  settings, app-level condition-template storage under
  `<FPVSRoot>/.fpvs-studio/templates/`, and Recycle Bin confirmation/deletion side
  effects.
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
- Display settings GUI task: `src/fpvs_studio/gui/runtime_settings_page.py`,
  `src/fpvs_studio/gui/run_page.py`, `src/fpvs_studio/gui/setup_wizard_page.py`,
  and `tests/gui/test_layout_dashboard.py`.
- Fixation Cross setup task: `src/fpvs_studio/gui/fixation_settings_page.py`,
  `src/fpvs_studio/gui/setup_wizard_page.py`, `docs/GUI_WORKFLOW.md`, and
  `tests/gui/test_conditions_session_fixation.py`.
- Compiler/session task: `src/fpvs_studio/core/AGENTS.md`,
  `src/fpvs_studio/core/compiler.py`,
  `src/fpvs_studio/core/session_plan.py`,
  `docs/RUNSPEC.md`, and `docs/SESSION_PLAN.md`.
- Runtime task: `docs/RUNTIME_EXECUTION.md`,
  `src/fpvs_studio/runtime/launcher.py`,
  `src/fpvs_studio/runtime/preflight.py`,
  `src/fpvs_studio/runtime/participant_history.py`,
  `src/fpvs_studio/runtime/session_export.py`,
  `src/fpvs_studio/core/execution.py`, and the relevant
  `tests/unit/test_runtime_*.py` file.
- Preprocessing task: `src/fpvs_studio/preprocessing/`,
  `src/fpvs_studio/core/models.py`, `tests/unit/test_preprocessing_assets.py`,
  and `tests/unit/test_preprocessing_inspection.py`.
- Image Resizer utility task: `docs/exec-plans/completed/fpvs-toolbox-image-prep-tool.md`,
  `docs/references/archive/fpvs-toolbox-image-resizer/`,
  `src/fpvs_studio/preprocessing/`,
  `src/fpvs_studio/gui/components.py`, `src/fpvs_studio/gui/image_resizer_page.py`,
  and `src/fpvs_studio/gui/AGENTS.md`.
- Docs-only task: `AGENTS.md`, this file, `docs/index.md`, and the doc being edited.
  Avoid source reads unless the doc describes a concrete contract.
- Packaging task: `docs/PACKAGING.md`, `pyproject.toml`,
  `packaging/pyinstaller/fpvs_studio.spec`, `packaging/inno/fpvs_studio.iss`,
  `scripts/build_exe.ps1`, `scripts/build_installer.ps1`,
  `tests/unit/test_package_metadata.py`, and this file.
- Feature-sized workflow task: read `docs/PLANS.md` and `docs/exec-plans/README.md`,
  create or update an active plan under `docs/exec-plans/active/`, then read the
  related package docs and tests.
- Docs garbage-collection task: read `docs/exec-plans/plan-review-workflow.md`, run
  `.\scripts\check_docs_hygiene.ps1`, then update plan status or move stale docs.

## Contract Flow

`ProjectFile` models compile into single-condition `RunSpec` entries. Session settings and
ordered conditions compile into a `SessionPlan` that owns realized fixation target-count
selection and randomized block order for the current random order seed. Runtime consumes
`RunSpec` or `SessionPlan` and produces core-owned execution results. Exporters serialize
those results without moving contracts into engine code; `runs/` remains the detailed
artifact source, while `logs/session_condition_history.csv` is a runtime-owned reporting
index.

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
- Local Windows executable build: `.\scripts\build_exe.ps1`
- Local Windows installer build: `.\scripts\build_installer.ps1`
- Line-count report: `.\scripts\report_line_counts.ps1`
- Workspace cleanup: `.\scripts\clean_workspace.ps1`

## Deeper Docs

- Docs entry point: `docs/index.md`
- Product and v1 scope: `docs/PRODUCT_SENSE.md`, `docs/product-specs/`, and
  `docs/FPVS_Studio_v1_Architecture_Spec.md`
- Design docs: `docs/DESIGN.md` and `docs/design-docs/`
- Packaging developer builds: `docs/PACKAGING.md`
- Feature execution plans: `docs/PLANS.md` and `docs/exec-plans/`
- GUI behavior and smoke-test guidance: `docs/FRONTEND.md` and `docs/GUI_WORKFLOW.md`
- Quality, reliability, and security: `docs/QUALITY_SCORE.md`, `docs/RELIABILITY.md`,
  and `docs/SECURITY.md`
- Engine boundary: `docs/ENGINE_INTERFACE.md`
- Run contract: `docs/RUNSPEC.md`
- Session contract: `docs/SESSION_PLAN.md`
- Runtime/export flow: `docs/RUNTIME_EXECUTION.md`
