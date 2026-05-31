# Technical Debt Tracker

This tracker keeps agent-facing debt short, ranked, and tied to executable checks.
It is intentionally not a backlog for product features.

## Current Priorities

| Rank | Area | Owner | Debt | Verification | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Harness | Repo-wide | Keep repo-level style/type/boundary/GUI smoke checks quiet so regressions are visible. | `.\scripts\check_quality.ps1` for release-sized changes; narrow gates while iterating | Active |
| 2 | GUI tests | GUI | Keep pytest-qt tests aligned with the current Home/Setup Wizard workflow and hidden runtime controls. | `.\scripts\check_gui.ps1` | Passing |
| 3 | GUI workflow docs | Docs/GUI | Keep Welcome/Home, raw import, normalization, and runtime launch docs synchronized with the implemented GUI. | `python -m pytest -q tests\unit\test_harness_docs.py` | Passing |
| 4 | GUI module size | GUI | Monitor large cohesive GUI source modules and split only when responsibilities diverge or focused tests become hard to locate. | `.\scripts\report_line_counts.ps1` | Monitor |
| 5 | GUI styling | GUI | Continue replacing one-off GUI styling with helpers in `src/fpvs_studio/gui/components.py`. | Focused GUI tests plus Ruff | Monitor |

## Module Decomposition Watchlist

Use this section after matching an architecture, refactor, or decomposition task in
`../ARCHITECTURE.md`. File length is a signal, not the rule: split only when a module
mixes responsibilities, forces broad context reads for narrow work, or makes focused
tests hard to locate.

Preferred split pattern:

- Preserve the current public API first.
- Move one responsibility at a time.
- Run the narrow gate for the touched layer after each move.

Current watchlist:

- `src/fpvs_studio/gui/document.py` remains the GUI-facing `ProjectDocument` facade.
  Focused helpers own document support/defaults, condition mutation, stimulus import
  and manifest sync, and validation/compilation/preflight/launch coordination.
- `src/fpvs_studio/core/compiler.py` keeps the public `compile_run_spec` and
  `compile_session_plan` entry points stable. Helper modules own shared compiler
  support, condition selection, asset resolution, schedules, and fixation planning.
- `src/fpvs_studio/engines/psychopy_engine.py` keeps the `PsychoPyEngine` public
  surface and main frame loop stable. Helper modules own lazy PsychoPy loading,
  text-screen rendering, stimulus preparation, timing QC, metadata, window/fixation
  construction, and trigger emission.
- GUI session/fixation authoring uses `session_pages.py` as a compatibility export
  facade. Session structure editing lives in `session_structure_page.py`; fixation-task
  controls live in `fixation_settings_page.py`.
- GUI component/theme work starts from `src/fpvs_studio/gui/components.py`, with raw
  design tokens in `src/fpvs_studio/gui/design_system.py`.
- GUI workflow details live in `GUI_WORKFLOW.md`. Do not duplicate the Home/Setup
  Wizard, Image Resizer, root-folder setup, or compact `1120x720` setup behavior in
  `../ARCHITECTURE.md`.
- GUI project management keeps `manage_projects_dialog.py` presentation-only while
  `controller.py` owns disk-backed discovery, recent-project settings, template storage
  under `<FPVSRoot>/.fpvs-studio/templates/`, and Recycle Bin side effects.
- Condition-template profile management keeps `condition_template_manager_dialog.py` as
  the manager dialog and compatibility import point. The profile editor dialog lives in
  `condition_template_profile_editor_dialog.py`.
- Large GUI page modules are acceptable when they model one cohesive page or editor.
  Split only when a subcomponent has an independent lifecycle, test surface, or reusable
  responsibility.
- Large GUI tests should be split by workflow when they become hard to run or review
  narrowly; production-module splits take priority over test-file line-count cleanup.

Refactor priority:

1. Keep the `ProjectDocument` helper split cohesive as GUI document behavior evolves.
2. Keep compiler helper modules cohesive as compile behavior evolves.
3. Keep the PsychoPy engine helper split conservative. Move playback-loop code only when
   a tested seam is clear.
4. Keep future fixation-task GUI work in `fixation_settings_page.py` unless it changes
   model compilation or runtime scoring.

## Current Verified State

- Quality gate: `.\scripts\check_quality.ps1` passes after the current GUI/config
  import-export work and GUI workflow test split.
- GUI gate: `.\scripts\check_gui.ps1` passes after splitting the former layout/dashboard
  coverage into focused workflow files.
- Harness garbage collection: `.\scripts\check_gc.ps1` passes after moving preview
  dialog styling into `gui/components.py`.
- Lint status: `python -m ruff check src tests` passes.
- Type status: `python -m mypy src` currently needs the Windows/PsychoPy verification
  environment; the macOS source environment reports missing optional PsychoPy imports
  and Windows-only `ctypes.windll`.
- Agent context status: the former large GUI layout/dashboard test file is split by
  workflow; use `ARCHITECTURE.md` task recipes before broad source reads.

## Notes

- Do not change project JSON, `RunSpec`, `SessionPlan`, or runtime export formats as part of harness cleanup.
- Prefer small mechanical fixes that reduce check noise without changing behavior.
- Keep protected legacy paths untouched unless a user explicitly asks for that risk.
- Raw stimulus-folder import is intentionally permissive; inconsistent image sizes are
  handled through guided normalization before launch instead of being blocked at folder
  selection time.
- Serial trigger model fields remain in backend contracts, but serial/display launch
  controls are not exposed in the current GUI.
- Use `.\scripts\clean_workspace.ps1` to remove generated `build/` and tool
  cache directories before broad searches or handoff.
- Narrow harness commands are documented in `ARCHITECTURE.md`; keep them in
  sync when tests move.
