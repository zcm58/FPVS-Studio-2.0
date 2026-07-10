---
name: pyside6-gui-cleanup
description: Use for Windows-focused PySide6 GUI cleanup, widget refactors, dialog/layout polish, clipping prevention, QAction import fixes, design-system usage, worker/threading review, and non-blocking status or error UX in src/fpvs_studio/gui.
---

# PySide6 GUI Cleanup

## Workflow

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and `docs/GUI_WORKFLOW.md`.
2. Read any nested `AGENTS.md` in the GUI paths you touch.
3. Identify the smallest behavior-preserving GUI change that satisfies the task.
4. Set the documented minimum/default surface size and budget the layout against
   realistic longest labels, paths, validation messages, and every visible state before
   implementation. No clipping or unintended truncation is acceptable by default.
5. Keep UI code separate from core processing, runtime flow, and engine behavior.
6. Use PySide6 only; do not introduce CustomTkinter or alternate GUI fallbacks.
7. Import `QAction` only from `PySide6.QtGui`.
8. Use existing design-system helpers and theme tokens where they already apply.
9. Keep GUI errors non-blocking where the existing UX supports it, and log diagnostics
   with structured logging.
10. Do not block the UI thread. Long work must use Qt worker patterns, and workers must
   not touch widgets directly.
11. Preserve all user flows, labels that communicate current runtime limitations, project
    formats, and processing order.
12. Prefer responsive sizing and wrapping. Use elision only intentionally, preserve the
    complete value through a tooltip or copy action, and test that access path.
13. Add or update focused pytest-qt coverage for geometry and text clipping at the
    documented minimum/default size; do this during the initial implementation, not as
    a later visual-polish pass.
14. Run the narrowest useful verification, then broader gates when the change affects
    shared behavior.

## Output Checklist

- List exact files touched.
- State the preserved behavior or user flow.
- Confirm the tested minimum/default size and no-clipping coverage.
- Report verification commands and results.
- Include manual smoke steps only when an automated pytest-qt test is not practical.
