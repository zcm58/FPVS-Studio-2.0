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
- Keep the eight guided steps in order: Project, Conditions, Design, Timing & Session,
  Image Size, Fixation, Response, Review. Budget all steps for `1120x820` without required
  scrolling. Timing retains the `experiment` navigation key for internal callers.
- Preserve Home setup actions: ready projects expose `Edit Setup`, incomplete projects
  expose `Complete Setup`, and first-time setup opens at the earliest incomplete step
  without enabling arbitrary step jumps.
- New-experiment Setup offers manual creation or Library download. Manual creation asks
  for category, then name/folder/template; Library downloads reuse bundle import. Category
  is locked after creation. FPVS is disabled Coming soon. Reuse the visual editor in
  Design; image-pair AB and its ISI editor are retired. Attentional-Blink letter
  streams expose a shared presentation rate, character pools and onset-to-onset SOAs.
  New burst studies expose Bursts per SOA in Design and Timing & Session, with EEG time
  and total burst count in Design. Rate/source/SOA/burst-count drafts apply atomically;
  core guards five-second burst timing and category rules. Legacy stream pools remain
  unchanged. View > T1 and T2 Accuracy reads runtime-owned SOA/trigger summaries and
  chronological burst records, with worker-backed Excel export and busy-close guards.
  Other categories retain View > Fixation Task Accuracy.
- Keep condition modality authoring in Conditions. Image folders belong in Design;
  oddball word conditions keep typed base/oddball word-list editors in Conditions.
  Native AB digit/T1/T2 sources belong in Design, with Character Size replacing Image
  Size. See `docs/EXPERIMENT_CATEGORIES.md` for shared surfaces and legacy repair.
- Present Sinusoidal Contrast Modulation as the third image presentation mode alongside
  Continuous Display and 50% Blank. Do not offer it for word conditions, and expose
  Neutral Gray as the required project background without changing existing modes.
- Do not reintroduce Setup Wizard Advanced buttons or generic footer/status copy
  without an explicit workflow plan.
- Keep fixation accuracy-task and participant-tutorial controls in the Fixation/Session
  UI as model-bound settings only; compile-time realization, runtime scoring, and
  participant feedback flow must remain outside widget code.
- Keep reusable pre/post-condition task authoring in the Conditions workflow as a thin
  editor over core task models. Import task media through the core task-asset service;
  do not copy assets until the user applies a valid dialog draft.
- Keep PsychoPy startup lazy; opening the GUI alone must not create a PsychoPy window.
- Keep runtime launch messaging honest about fullscreen display verification and
  timing-QC behavior.
- Surface user-facing errors clearly, but keep the application recoverable.
- File > Report a Bug and Request a Feature use the app-owned coordinator and GUI-neutral
  support package. Keep service activation outside project settings. Report draft
  persistence may use `finish_on_shutdown` jobs; network operations must remain
  cancelable. See `docs/BUG_REPORTING.md` for the offline workflow and API contract.
- Route updater work through the application-owned `update_lifecycle.py` coordinator.
  Keep offline startup cache housekeeping independent of root-folder setup and metadata
  checks. Dialog close/app quit must cancel or defer teardown until worker threads really
  finish; never wait on a worker from the GUI thread or parent it to a disposable dialog.
  Keep cache hashing, trusted-installer checks, and final launch in backend worker calls;
  confirmation and project Save prompts stay on the GUI thread. Preserve newer-release
  visibility when a missing trusted digest prevents in-app installation.
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

- Keep registered GUI tests deterministic.
- Stub `QFileDialog`, `QMessageBox`, and runtime-launch calls in tests.
- Prefer direct state assertions over window-exposure assumptions.
- Show changed surfaces at their documented minimum/default size, process Qt events,
  and assert both visible child bounds and non-elided label widths. Exercise realistic
  long paths, names, status messages, and validation text, not only short fixtures.
- Register Qt modules in `tests/qt_test_files.txt`. Run
  `./scripts/verify.ps1 -Scope gui -Tier focused` plus a visible manual
  smoke path locally. Run the optional `full` Qt tier only when the user approves a
  safe visible environment; GitHub does not run it automatically.


AB-only Pilot Study Mode is an app Settings preference, defaults off and takes
precedence over Test Mode for AB. Reuse the standard demographics/visit flow; document
launch settings alone select local hardware checks. See `docs/GUI_WORKFLOW.md`.
