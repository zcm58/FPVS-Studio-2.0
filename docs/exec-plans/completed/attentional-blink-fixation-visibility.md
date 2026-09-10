# Attentional-Blink fixation visibility

Status: Completed

The user approved adding an option to remove the fixation cross completely from
Attentional-Blink experiments, followed by committing and pushing the branch.

- Add Show fixation cross to Setup > Fixation for both AB layouts. Default to shown
  for compatibility; leave FPVS-Oddball's authoring controls unchanged.
- Persist a separate show_cross flag in fixation settings and compile it into
  FixationStyleSpec. Hiding the cross disables color changes, accuracy responses and
  tutorial participation. Retain authored lead-in duration as a blank interval.
- Skip cross resource creation, priming and drawing in the engine when hidden,
  including pre-stream and terminal frames. Keep stimulus timing and triggers intact.
- Update preview, dependent control states and Review to describe the hidden cross.
- Verify model/persistence/compilation, fake-engine drawing and timing, and visible
  GUI on/off states at 1120x820. Run focused checks and precommit before publishing.

The commit includes the preceding authorized AB study and GUI work already present
on codex/visual-fpvs-designer. Resolve the existing controller type-narrowing error
if needed to complete the requested commit verification; preserve its behavior.

Implemented and verified on 2026-09-10. Both AB layouts expose the option; hidden
crosses have no prepared or drawn resources, fixation events, accuracy responses or
tutorial. The preview/Review and inactive controls reflect the selection. Existing
project/RunSpec payloads default to visible, and lead-in duration remains unchanged.

Verification: 34 visible GUI checks, 232 engine-focused tests, and the full precommit
gate pass (1,306 unit tests; five symlink tests skipped for Windows permissions).
Mypy passes all 151 source modules after the controller's return value was explicitly
narrowed to str. Dark/light captures inspect Fixation, Response and Review at 1120x820.
Tests use fake PsychoPy presentation and hardware; no real experimental playback or
hardware trigger run was launched. Short build-local test paths avoid Windows staging
path-length limits. The user should verify timing on the presentation machine.
