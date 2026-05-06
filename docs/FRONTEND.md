# Frontend

FPVS Studio's frontend is the Windows-focused PySide6 GUI. There is no web frontend in
the active app.

## Public GUI Surface

- Start GUI work from `../src/fpvs_studio/gui/AGENTS.md`.
- Use `../src/fpvs_studio/gui/components.py` for shared widgets, button roles, labels,
  status badges, and theme helpers.
- Use `../src/fpvs_studio/gui/design_system.py` for tokens and tiny text helpers.
- Keep detailed behavior and test guidance in `GUI_WORKFLOW.md`.

## GUI Architecture

- Home is the daily launch surface for ready projects.
- Setup Wizard is the guided setup/editing surface.
- Dense editors stay available inside wizard Advanced views when they are useful.
- GUI code may coordinate document services and runtime launches, but core validation,
  compilation, session planning, and runtime flow remain outside widgets.

## Verification

- Focused GUI changes need pytest-qt coverage or documented manual smoke steps.
- Run `.\scripts\check_gui.ps1` for GUI workflow changes.
- Run `.\scripts\check_quality.ps1` when GUI changes touch multiple layers.
