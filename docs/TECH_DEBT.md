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

## Notes

- Do not change project JSON, `RunSpec`, `SessionPlan`, or runtime export formats as part of harness cleanup.
- Prefer small mechanical fixes that reduce check noise without changing behavior.
- Keep protected legacy paths untouched unless a user explicitly asks for that risk.
