# Technical Debt Tracker

This tracker keeps agent-facing debt short, ranked, and tied to executable checks.
It is intentionally not a backlog for product features.

## Current Priorities

| Rank | Area | Owner | Debt | Verification | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Harness | Repo-wide | Keep repo-level style/type/boundary/GUI smoke checks quiet so regressions are visible. | `.\scripts\check_quality.ps1` for release-sized changes; narrow gates while iterating | Active |
| 2 | PySide6 boundary | Tools/GUI | Remove, relocate, or explicitly archive `src/fpvs_studio/tools/pyside_resizer.py`; it is reference-only FPVS Toolbox code but currently violates the PySide6 import boundary. | `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_import_boundaries.py` | Failing |
| 3 | GUI tests | GUI | Keep pytest-qt tests aligned with the current Home/Setup Wizard workflow and hidden runtime controls. | `.\scripts\check_gui.ps1` | Passing |
| 4 | GUI workflow docs | Docs/GUI | Keep Welcome/Home, raw import, normalization, and runtime launch docs synchronized with the implemented GUI. | `python -m pytest -q tests\unit\test_harness_docs.py` | Passing |
| 5 | GUI module size | GUI/tests | Monitor large cohesive GUI modules and split only when responsibilities diverge or focused tests become hard to locate. | `.\scripts\report_line_counts.ps1` | Monitor |
| 6 | GUI styling | GUI | Continue replacing one-off GUI styling with helpers in `src/fpvs_studio/gui/components.py`. | Focused GUI tests plus Ruff | Monitor |

## Current Verified State

- GUI gate: `.\scripts\check_gui.ps1` passes after aligning stale asset/import and
  runtime-launch tests with the current GUI.
- Focused GUI debt cleanup: `python -m pytest -q tests\gui\test_assets_run_launch.py`
  passes.
- Harness docs: `python -m pytest -q tests\unit\test_harness_docs.py` passes.
- Harness garbage collection currently reports the known PySide6 import-boundary
  failure in `src/fpvs_studio/tools/pyside_resizer.py`.
- Lint status: Ruff is clean for the touched GUI test files.
- Full quality gate and broad suite were not rerun during this narrow debt cleanup;
  use `.\scripts\check_quality.ps1` for release-sized or cross-layer changes.
- Agent context status: GUI workflow tests and runtime launcher tests are split
  by task area; use `ARCHITECTURE.md` task recipes before broad source reads.

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
