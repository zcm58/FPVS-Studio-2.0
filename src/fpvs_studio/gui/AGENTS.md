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
- View > Data Sharing & Comparison uses `data_sharing_controller.py` with app-owned
  jobs and neutral backend contracts. First enrollment defaults sharing on; preserve saved
  opt-out/backlog release, cancellation, stale-project guards and descriptive cohort
  limits. Its sequential known-project startup pass shares the presentation gate
  with project-open/after-run jobs; do not create a competing uploader. Hash assets
  and call HTTP only in workers. See `docs/DATA_SHARING.md`.
- Preserve the Home/Setup Wizard workflow: Home is the returning-user launch surface;
  detailed setup widgets should be reached through the guided wizard, not new top-level
  tabs.
- Keep the seven guided steps in order: Project, Conditions, Timing & Session,
  Image Size, Fixation, Response, Review. Budget all steps for `1120x820` without required
  scrolling. Timing retains the `experiment` navigation key for internal callers.
- Preserve Home setup actions: ready projects expose `Edit Setup`, incomplete projects
  expose `Complete Setup`, and first-time setup opens at the earliest incomplete step
  without enabling arbitrary step jumps.
- New-experiment Setup offers manual creation or Library download. Manual creation asks
  for category, then name/folder/template; Library downloads reuse bundle import. Manual
  category choices are FPVS Oddball Paradigm and disabled Standard FPVS Coming soon.
  Category is locked after creation. Conditions provides per-condition Base/Oddball
  folder selection without image previews or cycle editing. There is no guided
  Design step. Retain the standalone image designer and native AB editor source
  separately; do not expose an AB editing replacement as part of this workflow.
  Saved AB rates, character pools, SOAs, burst settings and legacy streams remain
  unchanged. Core still guards default five-second or explicitly repeated-target
  timing and category rules. View > T1 and T2 Accuracy reads runtime-owned SOA/trigger summaries and
  chronological burst records, with worker-backed Excel export and busy-close guards.
  Other categories retain View > Fixation Task Accuracy.
- Keep condition modality and Base/Oddball image-folder authoring in Conditions;
  oddball word conditions keep typed base/oddball word-list editors in Conditions.
  Image imports use fresh project-owned pools on workers and block navigation while
  mutating sources; normalization occurs when leaving Conditions. Participant
  instructions use an Edit Instructions dialog with Save/Cancel; empty Save clears
  them and Cancel preserves them. Do not reject default or short condition names
  through a custom descriptive-name rule; retain core's nonempty name schema.
  Character Size replaces Image Size for native AB. See
  `docs/EXPERIMENT_CATEGORIES.md` for shared surfaces and legacy repair.
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
  Ordinary background/progress tasks and the reusable presentation thread use the same
  shutdown owner. Keep worker wrappers until `thread_completion.py` confirms native
  cleanup; its join monitor never waits on the GUI thread or accesses widgets.
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

## Design quality

- For substantial layout work, use the short brief and review criteria in
  [agent UI design guidance](../../../docs/design-docs/agent-ui-design.md).
  Record decisions in the current plan or task notes; a new approval stage is unnecessary.
- Build hierarchy with existing typography, spacing, alignment and semantic button
  roles. Keep related fields together and emphasize the next meaningful action.
  Preserve the established shells and section cards; avoid adding decorative containers.
- Put frequent commands near their task and occasional commands in existing menus.
  Find Action belongs in File with Ctrl+F, not a permanent main-window button.
  Reuse QAction enabled/visible state and existing navigation guards.
- Keep headings, field labels, essential status and actionable errors visible.
  Optional explanation belongs in tooltips; do not add routine subtitles or help
  paragraphs. Preserve participant instructions and decision-critical information.
- Account for applicable empty, populated, busy, disabled, invalid, failed, successful
  and unsaved states. Provide a useful next action and preserve drafts during recovery.
- Retain logical keyboard focus, Tab order, shortcuts and accessible names. Pair
  status colors with text or symbols; prefer native controls and existing icons.
- When visible verification is authorized, inspect the actual rendered changes,
  correct concrete hierarchy/layout/interaction defects and recheck affected states.
  Report the sizes, themes and scaling observed; source checks alone are not visual proof.

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

Settings > Recording edits the active project's BioSemi ActiveTwo/ActiveThree,
Brain Products TriggerBox or Unicorn choice through a staged
Recording Setup dialog; Apply saves project recording fields and the selected BioSemi
trigger port together, and Cancel preserves
the previous choice. A separate typed computer default is chosen after Root Folder
setup; unset projects inherit it, while saved project choices take precedence.
Settings can edit the default without a project or reset only a project's override.
Ignore obsolete global transport keys and retain unrelated drafts. Snapshot effective
hardware for runtime handoff without inserting it into portable authoring state.
Home and Run validate configuration before participant collection, then run automatic
Recorder readiness in the existing launch worker before presentation.
Do not ask for a manual Unicorn recording checkbox or run OS probes on the GUI thread.
Successful readiness allows normal Unicorn marker output; full receiver/timing
validation remains pending metadata. Test/Pilot sends no markers and skips Recorder
checks. Sophia confirmation remains specific to the two BioSemi selections.
TriggerBox exposes detected/manual COM ports and project amplifier/rate/pulse settings;
BioSemi ActiveTwo/ActiveThree expose a project serial-port selector backed by existing
trigger settings. Metadata listing never identifies generic ports as BioSemi; Check
Port checks only the selection on a worker without marker bytes. Computer defaults
do not own BioSemi COM fields. Preserve selected hardware identity on
Home independently of transport.
Parallel-port actiCHamp uses its own address selector with metadata-only detection,
manual hexadecimal entry and the shared rate/pulse controls. Do not infer an attached
amplifier from a listed LPT device or load hardware drivers during dialog validation.
See `docs/GUI_WORKFLOW.md`.
