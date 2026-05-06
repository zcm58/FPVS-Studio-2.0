# Quality Score

This repo uses executable checks instead of a manually maintained numeric score. Treat
the current quality posture as the latest result of the standard gates.

## Standard Gates

- Harness docs: `python -m pytest -q tests\unit\test_harness_docs.py`
- Python lint: `python -m ruff check .`
- Unit suite: `python -m pytest -q`
- Full repo gate: `.\scripts\check_quality.ps1`

## Focused Gates

- GUI: `.\scripts\check_gui.ps1`
- Runtime: `.\scripts\check_runtime.ps1`
- Compiler/session: `.\scripts\check_compiler.ps1`
- Preprocessing: `.\scripts\check_preprocessing.ps1`
- Context-size report: `.\scripts\report_line_counts.ps1`

When a check is skipped or fails, record the command and reason in the final work note or
the relevant execution plan.
