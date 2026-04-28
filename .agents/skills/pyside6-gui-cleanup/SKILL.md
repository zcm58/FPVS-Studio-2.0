---
name: pyside6-gui-cleanup
description: Use for Windows-focused PySide6 GUI cleanup, widget refactors, dialog/layout polish, QAction import fixes, design-system usage, worker/threading review, and non-blocking status or error UX in src/fpvs_studio/gui.
---

# PySide6 GUI Cleanup

## Workflow

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and `docs/GUI_WORKFLOW.md`.
2. Read any nested `AGENTS.md` in the GUI paths you touch.
3. Identify the smallest behavior-preserving GUI change that satisfies the task.
4. Keep UI code separate from core processing, runtime flow, and engine behavior.
5. Use PySide6 only; do not introduce CustomTkinter or alternate GUI fallbacks.
6. Import `QAction` only from `PySide6.QtGui`.
7. Use existing design-system helpers and theme tokens where they already apply.
8. Keep GUI errors non-blocking where the existing UX supports it, and log diagnostics
   with structured logging.
9. Do not block the UI thread. Long work must use Qt worker patterns, and workers must
   not touch widgets directly.
10. Preserve all user flows, labels that communicate current runtime limitations, project
    formats, and processing order.
11. Add or update a focused pytest-qt smoke test for changed GUI behavior when practical.
12. Run the narrowest useful verification, then broader gates when the change affects
    shared behavior.

## Output Checklist

- List exact files touched.
- State the preserved behavior or user flow.
- Report verification commands and results.
- Include manual smoke steps only when an automated pytest-qt test is not practical.
