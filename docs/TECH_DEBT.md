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
