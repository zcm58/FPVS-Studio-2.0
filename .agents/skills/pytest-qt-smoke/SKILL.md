---
name: pytest-qt-smoke
description: Use when adding or updating pytest-qt smoke tests for changed PySide6 widgets, dialogs, windows, layout or text clipping, signals, controller bindings, enabled states, status text, or non-blocking GUI behavior.
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
10. For every new or changed surface, show it at its documented minimum/default size and
    process Qt events before checking layout. Use realistic longest content and assert:
    visible children remain within their parents; labels intended to show complete text
    are at least `fontMetrics().horizontalAdvance(label.text())` wide; wrapped labels have
    sufficient height; and intentional elision exposes the complete value by tooltip or
    copy action. Reuse `tests.gui.helpers.assert_visible_children_within_parent`.
11. Exercise important alternate states that change copy or controls, including busy,
    validation, error, empty, and completion states when the surface supports them.
12. Keep the smoke test focused on the changed behavior, not the full application.

## Environment

Prefer the headless pattern from `docs/GUI_WORKFLOW.md`:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
.\.venv3.10\Scripts\python -m pytest --disable-plugin-autoload -p pytestqt.plugin -p pytest_timeout tests\gui
```

## Output Checklist

- Name the changed GUI behavior covered by the smoke test.
- Report the minimum/default size and clipping states covered.
- List monkeypatched dialogs, runtime calls, or controllers.
- Report the exact pytest command and result.
