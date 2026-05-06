# AGENTS.md

## Repo purpose

FPVS Studio is a Windows-focused PySide6 desktop authoring application for FPVS
experiments, with PsychoPy isolated behind runtime/engine boundaries.

## Context map

- Start with `ARCHITECTURE.md` for the current package and dependency map.
- Use the "Task Context Recipes" in `ARCHITECTURE.md` before opening broad
  source or test trees.
- Use `docs/FPVS_Studio_v1_Architecture_Spec.md` for product and protocol scope.
- Use `docs/index.md` as the structured docs entry point and `docs/PRODUCT_SENSE.md`
  for the current user-workflow framing.
- Use `docs/DESIGN.md` and `docs/FRONTEND.md` for GUI design and PySide6 frontend
  conventions.
- Use `docs/GUI_WORKFLOW.md` for supported GUI behavior and GUI test guidance.
- Use `docs/RUNSPEC.md`, `docs/SESSION_PLAN.md`, and `docs/RUNTIME_EXECUTION.md`
  for compiled execution contracts.
- Use `docs/PLANS.md` and `docs/exec-plans/` for feature-sized work that changes
  user workflows, public contracts, or multiple layers.
- Use `docs/QUALITY_SCORE.md`, `docs/RELIABILITY.md`, and `docs/SECURITY.md` for
  quality, reliability, and local security guardrails.
- Use repo skills in `.agents/skills/` for repeatable GUI, path, legacy-boundary,
  and pytest-qt workflows.

## Repository guardrails

- Read this file and any nested `AGENTS.md` files in directories you touch before editing.
- Update `ARCHITECTURE.md`, relevant nested `AGENTS.md` files, and deeper docs
  when package boundaries, source-of-truth contracts, task recipes, verification
  commands, or supported workflows change.
- Keep recursive searches narrow; exclude `.venv*`, `build`, `.pytest_cache`,
  `.ruff_cache`, `.mypy_cache`, and `.tmp` unless the task is explicitly about
  generated or cached output.
- Preserve existing functionality, processing order, persisted formats, and export formats.
- Make surgical changes: do not refactor adjacent code or reformat unrelated files.
- Prefer simple direct changes over speculative abstractions or hidden fallback behavior.
- Treat `Main_App/Legacy_App/**` and `Tools/SourceLocalization/**` as protected
  legacy boundaries if present; do not edit them without an explicit user request.
- Keep editable project models in `src/fpvs_studio/core/models.py`.
- Keep the compiled execution contract in `src/fpvs_studio/core/run_spec.py`.
- Keep the compiled multi-condition session contract in `src/fpvs_studio/core/session_plan.py`.
- Keep execution-result/export contracts in `src/fpvs_studio/core/execution.py`.
- The compiler must transform project models into `RunSpec`; runtime and engines consume `RunSpec`, not `ProjectFile`.
- Session compilation must transform project models/session settings into `SessionPlan`; runtime consumes `SessionPlan` and iterates its ordered `RunSpec` entries.
- Session compilation owns realized fixation target-count selection for each ordered run (including randomized/no-immediate-repeat behavior when enabled); do not move that logic into GUI or runtime.
- Runtime execution must transform `RunSpec` / `SessionPlan` playback into core-owned execution-result contracts; exporters serialize those contracts without moving them into engine code.
- Runtime-only launch or machine options must stay outside `RunSpec`.
- Runtime owns inter-condition and inter-block session flow; engines render instruction, break, and completion screens.
- Runtime owns fixation-accuracy scoring and condition-level participant feedback flow; engines render the feedback screen content.
- Only code under `src/fpvs_studio/engines/` may import PsychoPy, and those imports must stay lazy inside the engine implementation.
- The PySide6 GUI is a first-class application surface in this phase; do not add end-user dependency fallbacks or alternate non-GUI modes around missing GUI dependencies.
- PySide6 GUI code must stay PySide6-only; do not introduce CustomTkinter.
- Import `QAction` from `PySide6.QtGui`.
- Do not block the UI thread; long work belongs in Qt worker patterns such as `QThread`
  or `QRunnable` with `QThreadPool`.
- Use structured logging for application diagnostics, not `print`.
- All project file I/O must use the active project root and preserve existing formats.
- Preprocessing owns validated assets/manifests and must not depend on PsychoPy or runtime/engine code.
- `RunSpec` must remain single-condition. Do not merge multiple conditions into one `RunSpec`.
- Represent execution timing in frames inside `RunSpec`; do not reintroduce sleep-based timing abstractions.
- Fixation accuracy behavior is an engagement task; it must not alter FPVS base/oddball scheduling.
- GUI launch flows must stay honest about the currently supported runtime path; if launch remains test-mode oriented, keep that reflected in labels and help text.
- Fullscreen presentation behavior belongs to runtime launch settings and engine window creation, not widget logic.

## Standard verification

- Run `python -m pytest -q tests\unit\test_harness_docs.py` after changing
  `AGENTS.md`, `ARCHITECTURE.md`, `.agents/skills/`, docs task recipes, package
  boundaries, or harness scripts.
- Run `python -m pytest -q` for broad behavior changes.
- Run `python -m ruff check .` after Python edits when available.
- Run `python -m mypy src` after typed contract or boundary changes when available.
- Use `.\scripts\check_quality.ps1` as the repo gate when touching multiple layers.
- Use `.\scripts\check_gc.ps1` for harness garbage-collection checks that catch
  mechanical drift such as forbidden GUI frameworks, source `print(...)`, stylesheet
  drift, boundary leaks, and committed local paths.
- Use `.\scripts\check_docs_hygiene.ps1` to review planned/active/completed execution
  plans and keep stale setup or audit docs out of the docs root.
- Use `.\scripts\check_gui.ps1`, `.\scripts\check_runtime.ps1`,
  `.\scripts\check_compiler.ps1`, or `.\scripts\check_preprocessing.ps1` for
  narrower cleanup passes.
- Use `.\scripts\report_line_counts.ps1` as an advisory context-size report before
  planning more module decomposition; split by responsibility, not by line count alone.
- GUI changes need a focused pytest-qt smoke test, or documented manual smoke steps if
  automation is impractical.
- Done means relevant checks pass, or every skipped/failing check is explained with the
  command and failure.
