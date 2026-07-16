# AGENTS.md

## Scope of this directory

`src/fpvs_studio/gui/` contains the current PySide6 authoring application.

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
- Preserve Home setup actions: ready projects expose `Edit Setup`, incomplete projects
  expose `Complete Setup`, and first-time setup opens at the earliest incomplete step
  without enabling arbitrary step jumps.
- Keep condition modality authoring in the guided Conditions step. Image conditions use
  base/oddball image source cards; word conditions use typed base/oddball word-list
  editors, and image-only actions stay disabled for word conditions.
- Do not reintroduce Setup Wizard Advanced buttons or generic footer/status copy
  without an explicit workflow plan.
- Keep fixation accuracy-task and participant-tutorial controls in the Fixation/Session
  UI as model-bound settings only; compile-time realization, runtime scoring, and
  participant feedback flow must remain outside widget code.
- Keep PsychoPy startup lazy; opening the GUI alone must not create a PsychoPy window.
- Keep runtime launch messaging honest about fullscreen display verification and
  timing-QC behavior.
- Surface user-facing errors clearly, but keep the application recoverable.
- Use `fpvs_studio.gui.components` as the public component/theme surface for shared
  page shells, section cards, status/path labels, button role helpers, and reusable
  styles.
- Avoid ad hoc `setStyleSheet(...)` in page or dialog modules for shared concepts;
  add or reuse a named helper in `gui.components` instead.
- Treat no clipping as a baseline design requirement. Establish the surface's
  minimum/default size and budget layouts for realistic longest content before coding.
  Prefer responsive sizing, wrapping, or intentional elision with a tooltip/copy path;
  never depend on the user enlarging a window to reveal required controls or text.

## Hard restrictions

- Do not import PsychoPy directly anywhere in this package.
- Do not move preprocessing, compiler, or runtime logic into Qt widgets.
- Do not create end-user fallback modes around missing PySide6.
- Do not let GUI tests or helper paths launch real modal dialogs or the real
  runtime unless explicitly intended.

## Testing guidance

- Keep registered CI GUI tests deterministic.
- Stub `QFileDialog`, `QMessageBox`, and runtime-launch calls in tests.
- Prefer direct state assertions over window-exposure assumptions.
- Show changed surfaces at their documented minimum/default size, process Qt events,
  and assert both visible child bounds and non-elided label widths. Exercise realistic
  long paths, names, status messages, and validation text, not only short fixtures.
- Register Qt modules in `tests/qt_test_files.txt`. Run
  `./scripts/verify.ps1 -Scope gui -Tier focused` plus a visible manual
  smoke path locally; leave Qt execution to CI unless the user approves a safe visible
  environment.
