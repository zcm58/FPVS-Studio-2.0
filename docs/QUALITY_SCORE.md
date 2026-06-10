# Quality Score

This repo uses executable checks instead of a manually maintained numeric score. Treat
the current quality posture as the latest result of the standard gates.

## Standard Gates

- Harness docs: `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py`
- Docs hygiene: `.\scripts\check_docs_hygiene.ps1`
- Harness garbage collection: `.\scripts\check_gc.ps1`; docs-only checks may use
  `.\scripts\check_gc.ps1 -SkipLineCounts`
- Python lint: `.\.venv3.10\Scripts\python -m ruff check .`
- Unit suite: `.\.venv3.10\Scripts\python -m pytest -q`
- Full repo gate: `.\scripts\check_quality.ps1`

Pytest runs use the repo-level `pytest-timeout` configuration in `pyproject.toml` so
common unit and GUI runs fail boundedly instead of hanging indefinitely. Focused GUI
diagnostics may still pass an explicit `--timeout` value when a narrower limit is useful.

## Focused Gates

- GUI: `.\scripts\check_gui.ps1`
- Runtime: `.\scripts\check_runtime.ps1`
- Compiler/session: `.\scripts\check_compiler.ps1`
- Preprocessing: `.\scripts\check_preprocessing.ps1`
- Context-size report: `.\scripts\report_line_counts.ps1`

## Garbage Collection

`.\scripts\check_gc.ps1` enforces mechanical repository principles that should not drift:

- no source/script `print(...)`; use structured logging
- no CustomTkinter return path
- shared GUI styles stay in `gui/components.py`, except the documented native menu reset
- PsychoPy imports stay behind the engines boundary
- PySide6 imports stay behind the GUI package boundary
- local machine paths stay out of source, tests, and scripts
- docs root stays focused on current hubs/contracts while historical setup and audit
  docs live under `docs/references/archive/`

The standalone script also prints an advisory line-count report. The full quality gate
runs the hard garbage-collection checks without the advisory report.

When a check is skipped or fails, record the command and reason in the final work note or
the relevant execution plan.
