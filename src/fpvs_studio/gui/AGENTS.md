# AGENTS.md

## Scope of this directory

`src/fpvs_studio/gui/` contains the Phase 5 PySide6 authoring application.

The GUI is now a real user-facing workflow, but it still must remain thin and
backend-driven.

## Requirements

- Reuse core, preprocessing, and runtime services instead of duplicating domain
  logic in widgets.
- Keep GUI-only state shallow; persistent truth should remain in backend models.
- Route validation, compilation, materialization, preflight, and launch through
  the existing backend seams.
- Preserve the Home/Setup Wizard workflow: Home is the returning-user launch surface;
  detailed setup widgets should be reached through the guided wizard, not new top-level
  tabs.
- Keep fixation accuracy-task controls in the Fixation/Session UI as model-bound settings only; compile-time realization, runtime scoring, and participant feedback flow must remain outside widget code.
- Keep PsychoPy startup lazy; opening the GUI alone must not create a PsychoPy window.
- Keep runtime launch messaging honest about the currently supported test-mode
  path.
- Surface user-facing errors clearly, but keep the application recoverable.
- Use `fpvs_studio.gui.components` as the public component/theme surface for shared
  page shells, section cards, status/path labels, button role helpers, and reusable
  styles.
- Avoid ad hoc `setStyleSheet(...)` in page or dialog modules for shared concepts;
  add or reuse a named helper in `gui.components` instead.

## Hard restrictions

- Do not import PsychoPy directly anywhere in this package.
- Do not move preprocessing, compiler, or runtime logic into Qt widgets.
- Do not create end-user fallback modes around missing PySide6.
- Do not let GUI tests or helper paths launch real modal dialogs or the real
  runtime unless explicitly intended.

## Testing guidance

- Keep GUI tests headless and deterministic.
- Stub `QFileDialog`, `QMessageBox`, and runtime-launch calls in tests.
- Prefer direct state assertions over window-exposure assumptions.
- Run one GUI test node at a time when iterating on failures.
