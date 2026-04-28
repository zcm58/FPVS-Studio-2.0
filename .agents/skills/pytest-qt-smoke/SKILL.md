---
name: pytest-qt-smoke
description: Use when adding or updating pytest-qt smoke tests for changed PySide6 widgets, dialogs, windows, signals, controller bindings, enabled states, status text, or non-blocking GUI behavior.
---

# pytest-qt Smoke

## Workflow

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and `docs/GUI_WORKFLOW.md`.
2. Inspect existing tests under `tests/gui/` before adding new patterns.
3. Instantiate the changed widget, dialog, or window directly when possible.
4. Register widgets with `qtbot.addWidget`.
5. Use fake controllers, monkeypatches, or lightweight signals for dependencies.
6. Do not open real `QFileDialog` or `QMessageBox`; monkeypatch modal interactions.
7. Do not launch the real PsychoPy runtime from GUI tests.
8. Use `tmp_path` for project files and generated data.
9. Assert user-visible state such as labels, enabled state, tooltips, status text, or
   signal outcomes.
10. Keep the smoke test focused on the changed behavior, not the full application.

## Environment

Prefer the headless pattern from `docs/GUI_WORKFLOW.md`:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
python -m pytest --disable-plugin-autoload -p pytestqt.plugin -p pytest_timeout tests\gui
```

## Output Checklist

- Name the changed GUI behavior covered by the smoke test.
- List monkeypatched dialogs, runtime calls, or controllers.
- Report the exact pytest command and result.
