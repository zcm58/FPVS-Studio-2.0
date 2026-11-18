# GUI Guidance

GUI owns PySide6 views, shallow interaction state, document/controller bindings and
app-owned jobs. Core, runtime and project services own scientific and persisted state.
Use the [Studio design guide](../../../docs/DESIGN.md#shared-openfpvs-desktop-experience)
for OpenFPVS desktop decisions.

## Workflow and Ownership

- Active Home offers Launch or Complete Setup. Completed Home offers results and
  export. See [collection workflow](../../../docs/product-specs/studio.md#collection-workflow)
  for manager tabs, the local research gate and separate website authorization.
  Preserve staged edits, category-specific editors and keyboard navigation.
  Use [Setup layout](../../../docs/GUI_WORKFLOW.md#frameless-setup-layout-and-copy),
  [order editing](../../../docs/GUI_WORKFLOW.md#choose-and-save-condition-order) or
  [categories](../../../docs/EXPERIMENT_CATEGORIES.md) for the affected workflow.
- Conditions owns modality and Base/Oddball source folders/word lists. Fresh image
  imports use workers and block navigation/disposal during mutation; normalization runs
  on leaving Conditions. There is no guided Design step or image preview. Instructions
  use Save/Cancel; empty Save clears, Cancel preserves. Keep core's nonempty name rule.
- Author tasks/modifiers through core models and staged drafts; copy task media only
  after valid Apply. Widget code never compiles timing, scores responses or sequences
  participant flow. Opening GUI alone must not create a PsychoPy window.
- `update_lifecycle.py` owns background/progress work and the presentation thread.
  macOS source playback/refresh use `runtime/macos_session_process.py` so native
  rendering runs on the child main thread; GUI workers wait without touching widgets.
  Retain workers until `thread_completion.py` confirms native cleanup; never wait on
  workers from GUI callbacks or parent them to disposable dialogs. Close/quit must
  cancel or defer teardown until cleanup completes. Workers never touch widgets.
- `data_sharing_controller.py` owns one gated uploader/startup pass. Preserve saved
  opt-out, cancellation and stale-project protection; HTTP/hashing run in workers.
  Reporting/support jobs retain their cancellation and draft/receipt contracts.
- Updater verification/launch stays in backend workers; Save/confirmation stays on the
  GUI thread. Keep newer-release visibility if trust evidence prevents installation.
- [Settings](../../../docs/GUI_WORKFLOW.md#settings-appearance-and-layout) embeds
  `RecordingSetupEditor` and distinguishes project settings from computer defaults.
  [Launch](../../../docs/GUI_WORKFLOW.md#launch) owns recorder review and readiness.
  Keep discovery checks passive and hardware receipt distinct from host evidence.
- `trigger_tester.py` owns temporary port selection, checks and digit sends. Use
  [Trigger Tester](../../../docs/GUI_WORKFLOW.md#trigger-tester) for discovery and
  reconnect behavior. Normal launch resolves saved recording settings independently.
- `image_equalizer_dialog.py` owns optional grayscale folder-pair preparation from
  the project Tools menu. Preprocessing owns matching and files. Use the
  [Image Equalizer contract](../../../docs/product-specs/image-equalizer.md).

## Design and Acceptance

- Use `gui.components` and [shared text roles](../../../docs/FRONTEND.md#shared-text-hierarchy).
  The [layout review](../../../docs/design-docs/agent-ui-design.md) covers substantial changes.
  Keep essential instructions, status and recovery beside the decision.
- Check for clipping at minimum/default size with realistic long values. Keep the full
  value accessible when elided. Preserve drafts, selection, tab order and shortcuts.
  [Frontend acceptance](../../../docs/FRONTEND.md#verification) covers states and sizing.

## Verification

Register GUI modules in `tests/qt_test_files.txt`. Stub file/message dialogs, network
and runtime launch; prefer deterministic state assertions. Check child bounds and
non-elided label widths at minimum/default size with long values and relevant states.
Run `./scripts/verify.ps1 -Scope gui -Tier focused` and document a visible smoke path.
Run Qt only with user approval for a safe visible environment, never offscreen. When
performed, report observed sizes/themes/scaling; source checks are not visual proof.
No fallback application mode, real modal/test launch or direct PsychoPy import.
