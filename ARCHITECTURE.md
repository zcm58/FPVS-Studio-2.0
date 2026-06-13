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
- `src/fpvs_studio/core/`: editable project models, validation, modality-aware stimulus
  contracts, compilation, run/session contracts, project persistence, Studio
  `.fpvsconfig` interchange export/import, and engine-neutral domain logic.
- `src/fpvs_studio/preprocessing/`: original image import, inspection, image
  normalization, generated variants, and manifests. This layer must stay independent
  of GUI runtime and PsychoPy.
- `src/fpvs_studio/tools/`: reserved package for future Studio-native utilities.
  Historical FPVS Toolbox image-resizer references live under
  `docs/references/archive/fpvs-toolbox-image-resizer/`.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session execution, participant
  history, launch-time participant metadata export, seed-history lookup, project-level
  run-log exports, and runtime flow over compiled contracts.
- `src/fpvs_studio/engines/`: presentation engine interface and PsychoPy implementation.
- `src/fpvs_studio/triggers/`: optional trigger backend interfaces and hardware adapters
  used by runtime while keeping core contracts hardware-neutral, including the
  BioSemi-compatible serial backend. BioSemi serial output writes one byte per marker
  with normal event codes `1`-`255`; code `0` is reserved for explicit manual reset.
  New projects default to BioSemi serial output on `COM3`, and the `oddball_onset`
  marker code is locked to `55` unless a nonstandard value is explicitly requested by
  the user and recorded with `allow_nonstandard_oddball_trigger_code`.
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

Keep this file as a compact router, not a monolithic manual. When updating it, put
detailed workflow, implementation, packaging, or decomposition guidance in the relevant
package `AGENTS.md`, focused `docs/` page, execution plan, or repo-local skill, then link
to that source from the package map or task recipe here. If new architecture text only
matters after an agent has matched a specific task type, it belongs in that task's deeper
doc, not in this always-read map.

Run `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py` after
harness-documentation edits. Wrapper scripts resolve `.venv3.10` first and `.venv`
second; direct documentation examples keep the canonical `.venv3.10` path. The full
quality gate also runs this check.

## Versioning And Packaging

The current app version is declared once in `pyproject.toml`. The Python distribution
name is `fpvs-studio`, while the user-facing application name remains FPVS Studio.
`src/fpvs_studio/__init__.py` reads `__version__` from source-tree `pyproject.toml`
when present and falls back to installed package metadata for bundled installs.
`tests/unit/test_package_metadata.py` guards the contract.

Use `docs/PACKAGING.md` for version bumps, executable/installer builds, bundled smoke
checks, update release requirements, and branding assets. Use `packaging/AGENTS.md` for
packaging-local boundaries before editing release tooling.

In-app update checks use `src/fpvs_studio/updates/` to query GitHub Releases, compare
against `fpvs_studio.__version__`, download the expected `FPVS-Studio-Setup-*.exe`
asset to a user-writable update cache, and launch the Inno installer only after explicit
user confirmation. The manual entry point is `File > Check for Updates`; the controller
also runs one silent startup check after the Welcome window appears and only opens the
update dialog when a newer release is available. The GUI owns presentation and Qt
threading; the updater backend must stay free of PySide6, PsychoPy, project-folder, and
runtime dependencies.

## Planned Module Decomposition

File length is a warning sign, not the architecture rule. Prefer splits when a file mixes
distinct responsibilities, forces broad context reads for narrow tasks, or makes focused
tests hard to locate. Do not split cohesive files only to satisfy a line-count target.

The preferred split pattern is a behavior-preserving move behind the current public API:
keep imports stable first, move one responsibility at a time, and run the narrow gate for
that layer after each move.

Current decomposition candidates and priority notes live in the Module Decomposition
Watchlist section of `docs/TECH_DEBT.md`. GUI workflow details live in
`docs/GUI_WORKFLOW.md`; do not duplicate wizard, launch-surface, or utility-page behavior
here.

## Task Context Recipes

Use these first reads before opening broad trees. Match one recipe, open only its
listed context first, then use search for the specific symbol or behavior under review.

Global Codex skills are workflow aids, not architecture sources. After the recipe reads,
use `diagnose` for bugs/regressions, `improve-codebase-architecture` only for requested
architecture/refactor reviews, `grill-me` for unresolved feature-plan decisions, and
`dispatching-parallel-agents` only for independent investigations with disjoint write
sets. Prefer repo-local skills in `.agents/skills/`; React, React Native, Vercel, and
web-design skills are out of scope for this desktop app unless a new surface adds them.

- Bug or regression task: use `diagnose` after reading the relevant recipe below. The
  success criterion is a focused repo command that fails before the fix and passes after
  it, or a documented reason that no correct automated seam exists.
- GUI design task: use repo-local `.agents/skills/pyside6-gui-cleanup` and
  `.agents/skills/pytest-qt-smoke` first. Use `impeccable` / `delight`,
  `frontend-design`, or `ui-ux-pro-max` only to refine PySide6 layout, copy, hierarchy,
  accessibility, or interaction decisions inside the existing component surface.
- Architecture/refactor review: use `improve-codebase-architecture` only when the user
  asks for architectural review or deeper refactor candidates. Cross-check candidates
  against `docs/PLANS.md`, `docs/exec-plans/`, and package-local `AGENTS.md` files
  before proposing edits.
- Plan stress-test: use `grill-me` for unresolved feature-sized workflow, contract,
  safety, or verification decisions, then capture durable decisions in an execution plan
  when the work affects future tasks.
- Independent multi-failure investigation: use `dispatching-parallel-agents` only when
  delegation is available and the failing areas can be assigned without overlapping write
  sets. Integrate by running the relevant focused and full gates afterward.
- Skill discovery: use `find-skills` only for a missing specialized workflow. Prefer the
  repo-local skills in `.agents/skills/` for GUI, path, legacy, PsychoPy migration, and
  pytest-qt work.
- Web-only skills: `web-design-guidelines` is limited to `docs-site/` or MkDocs UI work.
  React, React Native, and Vercel skills are out of scope for the current desktop app.

- Current-state or release-readiness check: start with `git status --short --branch`,
  `git log --oneline --decorate -5`, `pyproject.toml`, `docs/PACKAGING.md`, and this
  file. Use `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_package_metadata.py`
  for version metadata drift before running packaging scripts.
- GUI task: `src/fpvs_studio/gui/AGENTS.md`,
  `docs/FRONTEND.md`, `docs/GUI_WORKFLOW.md`, the specific page/dialog module, matching
  `tests/gui/test_*.py`, and `tests/gui/helpers.py` if workflow setup matters.
- Display settings GUI task: `src/fpvs_studio/gui/runtime_settings_page.py`,
  `src/fpvs_studio/gui/run_page.py`, `src/fpvs_studio/gui/setup_wizard_page.py`,
  `tests/gui/test_setup_experiment_display.py`, and `tests/gui/test_run_page_launch.py`;
  setup shell uses `src/fpvs_studio/gui/setup_wizard_page.py`,
  `src/fpvs_studio/gui/components.py`, and `tests/gui/test_setup_wizard_shell.py`;
  condition import uses `src/fpvs_studio/gui/condition_setup_step.py`,
  `src/fpvs_studio/preprocessing/`, and `tests/gui/test_setup_conditions.py`; Home uses
  `src/fpvs_studio/gui/home_page.py`, `src/fpvs_studio/gui/run_page.py`, and
  `tests/gui/test_home_launch_surface.py`; fixation setup uses
  `src/fpvs_studio/gui/fixation_settings_page.py`, `src/fpvs_studio/gui/setup_wizard_page.py`,
  `docs/GUI_WORKFLOW.md`, and `tests/gui/test_conditions_session_fixation.py`.
- Compiler/session task: `src/fpvs_studio/core/AGENTS.md`,
  `src/fpvs_studio/core/compiler.py`, `src/fpvs_studio/core/session_plan.py`,
  `docs/RUNSPEC.md`, and `docs/SESSION_PLAN.md`.
- Project config import/export task: `src/fpvs_studio/core/AGENTS.md`,
  `src/fpvs_studio/core/project_config.py`, `src/fpvs_studio/gui/main_window.py`,
  `src/fpvs_studio/gui/controller.py`, and `docs/GUI_WORKFLOW.md`.
- Runtime task: `src/fpvs_studio/runtime/AGENTS.md`, `docs/RUNTIME_EXECUTION.md`,
  `src/fpvs_studio/runtime/launcher.py`, `src/fpvs_studio/runtime/preflight.py`,
  `src/fpvs_studio/runtime/run_worker.py`, `src/fpvs_studio/runtime/triggers.py`,
  `src/fpvs_studio/runtime/session_export.py`, `src/fpvs_studio/core/execution.py`,
  and the relevant `tests/unit/test_runtime_*.py`.
- Trigger or launch-hardware task: read `src/fpvs_studio/triggers/AGENTS.md`,
  `src/fpvs_studio/triggers/`, `src/fpvs_studio/runtime/triggers.py`,
  `src/fpvs_studio/runtime/run_worker.py`, `docs/RUNTIME_EXECUTION.md`,
  `tests/unit/test_runtime_launcher_flow.py`, and
  `tests/unit/test_runtime_preflight.py` before broad runtime searches.
- Preprocessing task: `src/fpvs_studio/preprocessing/`, `src/fpvs_studio/core/models.py`,
  `tests/unit/test_preprocessing_assets.py`, and
  `tests/unit/test_preprocessing_inspection.py`.
- PsychoPy migration task: `.agents/skills/fpvs-psychopy-migration/SKILL.md`,
  `.agents/skills/fpvs-psychopy-migration/references/migration-guide.md`,
  `src/fpvs_studio/core/AGENTS.md`, `src/fpvs_studio/preprocessing/AGENTS.md`,
  `docs/FPVS_Studio_v1_Architecture_Spec.md`, `docs/RUNSPEC.md`, and
  `docs/GUI_WORKFLOW.md`.
- Image Resizer utility task: `docs/GUI_WORKFLOW.md`, `docs/FRONTEND.md`,
  `docs/references/archive/fpvs-toolbox-image-resizer/`,
  `src/fpvs_studio/preprocessing/`, `src/fpvs_studio/gui/components.py`,
  `src/fpvs_studio/gui/image_resizer_page.py`, `src/fpvs_studio/gui/AGENTS.md`, and
  `tests/gui/test_image_resizer_page.py`.
- Architecture/refactor/decomposition task: `docs/PLANS.md`, `docs/TECH_DEBT.md`,
  `docs/exec-plans/`, the relevant package `AGENTS.md`, and focused tests for the
  touched layer.
- Docs-only task: `AGENTS.md`, this file, `docs/index.md`, and the doc being edited.
  Avoid source reads unless the doc describes a concrete contract. Verify with
  `.\scripts\check_docs_hygiene.ps1`,
  `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py`, and
  `.\scripts\check_gc.ps1 -SkipLineCounts` when the edit changes agent routing.
- Packaging task: `docs/PACKAGING.md`, `pyproject.toml`,
  `packaging/pyinstaller/fpvs_studio.spec`, `packaging/inno/fpvs_studio.iss`,
  `scripts/build_exe.ps1`, `scripts/build_installer.ps1`, and
  `tests/unit/test_package_metadata.py`.
- Feature-sized workflow task: `docs/PLANS.md`, `docs/exec-plans/README.md`, an active
  plan under `docs/exec-plans/active/`, then related package docs and tests.
- Docs garbage-collection task: `docs/exec-plans/plan-review-workflow.md`,
  `.\scripts\check_docs_hygiene.ps1`, then update plan status or move stale docs.

## Contract Flow

`ProjectFile` models compile into single-condition `RunSpec` entries. Stimulus modality is
explicit in editable stimulus sets, compiled condition specs, and each stimulus event.
Session settings and ordered conditions compile into a `SessionPlan` that owns realized
fixation target-count selection and randomized block order for the current random order
seed. Runtime consumes `RunSpec` or `SessionPlan` and produces core-owned execution
results. Exporters serialize those results without moving contracts into engine code;
`runs/` remains the detailed artifact source, while `logs/session_condition_history.csv`
is a runtime-owned reporting index and `logs/participant_summary.csv` is the compact
human-facing participant/session summary.

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
- Common pytest runs are bounded by `pytest-timeout` through `pyproject.toml`.
- Full gate: `.\scripts\check_quality.ps1`
- Harness garbage collection: `.\scripts\check_gc.ps1`; use `.\scripts\check_gc.ps1 -SkipLineCounts`
  for docs-focused checks when the advisory line-count report is not needed.
- Docs hygiene: `.\scripts\check_docs_hygiene.ps1`
- GUI smoke/workflow: `.\scripts\check_gui.ps1`
- Runtime: `.\scripts\check_runtime.ps1`
- Compiler/session: `.\scripts\check_compiler.ps1`
- Preprocessing: `.\scripts\check_preprocessing.ps1`
- Local Windows executable build: `.\scripts\build_exe.ps1`
- Local Windows installer build: `.\scripts\build_installer.ps1`
- Packaged app smoke check: `.\scripts\smoke_packaged_app.ps1`
- Line-count report: `.\scripts\report_line_counts.ps1`
- Workspace cleanup: `.\scripts\clean_workspace.ps1`

## Deeper Docs

Use `docs/index.md` as the structured entry point for deeper docs. Keep topic-specific
details there or in the focused docs linked from the task recipes above, not duplicated
in this architecture map.
