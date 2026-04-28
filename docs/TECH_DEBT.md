# Technical Debt Tracker

This tracker keeps agent-facing debt short, ranked, and tied to executable checks.
It is intentionally not a backlog for product features.

## Current Priorities

| Rank | Area | Owner | Debt | Verification | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Harness | Repo-wide | Keep the repo-level style/type/boundary/GUI smoke checks quiet so regressions are visible. | `.\scripts\check_quality.ps1` | Passing |
| 2 | Types | GUI | GUI typing/layout surfaces have been cleaned up; keep new PySide6 surfaces typed as they are added. | `.\.venv3.10\Scripts\python -m mypy src` | Passing |
| 3 | Boundaries | Core/runtime/engine | Import boundaries are guarded and currently pass; keep this test small and mandatory when changing package seams. | `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_import_boundaries.py` | Passing |
| 4 | GUI responsiveness | GUI | Asset refresh/materialization and runtime launch now use Qt worker patterns. Keep future long-running GUI actions off the UI thread. | Focused pytest-qt smoke from `docs/GUI_WORKFLOW.md` | Passing |
| 5 | Agent context | Tests/docs | Oversized GUI/runtime launcher tests have been split by workflow, and task recipes now point agents at narrow files first. | `.\scripts\check_gui.ps1`; `.\scripts\check_runtime.ps1` | Passing |

## Current Verified State

- Full gate: `.\scripts\check_quality.ps1` passes.
- Broad suite: `.\.venv3.10\Scripts\python -m pytest -q` passes with 185 tests.
- Focused gates: `.\scripts\check_gui.ps1`, `.\scripts\check_runtime.ps1`,
  `.\scripts\check_compiler.ps1`, and `.\scripts\check_preprocessing.ps1` pass.
- Lint/type status: Ruff is clean for `src tests`; mypy is clean for `src`.
- Agent context status: GUI workflow tests and runtime launcher tests are split
  by task area; use `ARCHITECTURE.md` task recipes before broad source reads.

## Notes

- Do not change project JSON, `RunSpec`, `SessionPlan`, or runtime export formats as part of harness cleanup.
- Prefer small mechanical fixes that reduce check noise without changing behavior.
- Keep protected legacy paths untouched unless a user explicitly asks for that risk.
- Use `.\scripts\clean_workspace.ps1` to remove generated `build/` and tool
  cache directories before broad searches or handoff.
- Narrow harness commands are documented in `ARCHITECTURE.md`; keep them in
  sync when tests move.
