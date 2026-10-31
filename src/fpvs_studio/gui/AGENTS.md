# GUI Guidance

GUI owns PySide6 views, shallow interaction state, document/controller bindings and
app-owned jobs. Domain/persisted truth remains in backend services. Read one relevant
`docs/GUI_WORKFLOW.md` section; design contracts live in `docs/FRONTEND.md`.

## Workflow and Ownership

- Preserve Home as the launch surface and guided Setup for detailed editing. The eight
  steps are Project, Conditions, Timing & Display, Session, Image Size (Character Size
  for native AB), Fixation, Response, Review, fitting `1120x820` without required scroll.
  Timing retains `experiment`/timing/display/runtime aliases; `session` opens Session.
  Frequency/duration/counts/display stay on Timing; seeds/order/totals on Session.
- Preserve Edit Setup/Complete Setup and earliest-incomplete navigation. Manual creation
  offers FPVS Oddball and disabled Standard FPVS; Library uses reviewed bundle import.
  Categories are locked. Retain standalone image/native AB editors outside guided
  Setup; use `docs/EXPERIMENT_CATEGORIES.md` for current/retired behavior.
- Conditions owns modality and Base/Oddball source folders/word lists. Fresh image
  imports use workers and block navigation/disposal during mutation; normalization runs
  on leaving Conditions. There is no guided Design step or image preview. Instructions
  use Save/Cancel; empty Save clears, Cancel preserves. Keep core's nonempty name rule.
- Author tasks/modifiers through core models and staged drafts; copy task media only
  after valid Apply. Widget code never compiles timing, scores responses or sequences
  participant flow. Opening GUI alone must not create a PsychoPy window.
- `update_lifecycle.py` owns background/progress work and the presentation thread.
  Retain workers until `thread_completion.py` confirms native cleanup; never wait on
  workers from GUI callbacks or parent them to disposable dialogs. Close/quit must
  cancel or defer teardown until cleanup completes. Workers never touch widgets.
- `data_sharing_controller.py` owns one gated uploader/startup pass. Preserve saved
  opt-out, cancellation and stale-project protection; HTTP/hashing run in workers.
  Reporting/support jobs retain their cancellation and draft/receipt contracts.
- Updater verification/launch stays in backend workers; Save/confirmation stays on the
  GUI thread. Keep newer-release visibility if trust evidence prevents installation.
- Recording Apply atomically saves project override and selected BioSemi port; Cancel
  preserves drafts. Explicit project choice overrides computer defaults. Recorder
  readiness runs in the launch worker; metadata discovery/access checks send no bytes.
  Do not add a manual Unicorn checkbox or claim hardware receipt. See Recording and
  launch sections in `docs/GUI_WORKFLOW.md` before changing this surface.

## Design and Acceptance

- Use `gui.components` for shells, cards, labels, semantic button roles and shared
  styles; no one-off shared-concept `setStyleSheet` rules. Preserve established visual
  identity. Use [UI design guidance](../../../docs/design-docs/agent-ui-design.md)
  for substantial layout work without adding an approval stage.
- Keep headings, fields, essential status and actionable errors visible. Optional
  explanation belongs in tooltips. Preserve participant instructions and decision
  information; do not add routine subtitles, footer guidance or Setup Advanced buttons.
- No clipping: budget the minimum/default size for longest realistic content. Use
  wrapping/responsive layout or intentional elision with full-value tooltip/copy access.
  Never require enlarging a window to reach required controls.
- Cover empty, busy, invalid, failed, successful and unsaved states. Preserve drafts
  and selection during recovery. Retain Tab order, shortcuts and accessible names;
  pair status colors with text/symbols. Find Action remains File > Find Action, Ctrl+F.

## Verification

Register GUI modules in `tests/qt_test_files.txt`. Stub file/message dialogs, network
and runtime launch; prefer deterministic state assertions. Check child bounds and
non-elided label widths at minimum/default size with long values and relevant states.
Run `./scripts/verify.ps1 -Scope gui -Tier focused` and document a visible smoke path.
Run Qt only with user approval for a safe visible environment, never offscreen. When
performed, report observed sizes/themes/scaling; source checks are not visual proof.
No fallback application mode, real modal/test launch or direct PsychoPy import.
