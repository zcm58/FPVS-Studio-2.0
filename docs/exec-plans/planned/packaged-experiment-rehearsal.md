# Rehearsal In The Installed Application

Status: Planned

The user endorsed this direction on 2026-09-05 and requested a separate future
execution plan. Implementation has not started. Move this plan to `active/` when
the work is scheduled; this document does not change current launch behavior.

## Problem And Intended Outcome

Experiment Test Mode can already launch one condition or the full session, but
`gui/controller.py:experiment_test_mode_available()` excludes packaged builds.
Researchers using the installer therefore cannot access the same rehearsal workflow
available in a source checkout. Checking instructions, appearance, responses, and
pre/post tasks is an ordinary authoring activity.

Provide a visible **Rehearse** action in installed and source builds. It must explain
the selected condition scope, identify rehearsal outputs, and state which recording
checks will be skipped. Researchers should be able to inspect the experiment without
connecting recording hardware or entering real participant details.

This improves iteration, training, and adoption in labs that use the installer.
It is an authoring check, with an explicit distinction from acquisition readiness.

## Existing Owners And Evidence

- `src/fpvs_studio/gui/controller.py`: source-only availability and app preference.
- `src/fpvs_studio/gui/run_page.py`: existing scope selector, acknowledgment, and
  participant/test launch coordination.
- `src/fpvs_studio/gui/main_window.py`: Home launch entry point and completion UX.
- `src/fpvs_studio/gui/document_runtime.py`: explicit serial, refresh-verification,
  and graphics-verification options passed through the document launch adapter.
- `src/fpvs_studio/runtime/launcher.py` and `run_worker.py`: runtime launch settings
  and session flow; `core/execution.py` owns result metadata.
- [Runtime behavior](../../RUNTIME_EXECUTION.md#session-mode) documents reserved
  participant ID `0`, normal compilation, existing test exports, and skipped checks.

The legacy `RuntimeMetadata.test_mode` field is currently always false. It must not
be treated as a reliable rehearsal classifier or restored as a runtime control gate.

## Scope And User Workflow

1. From Home, choose Rehearse for the open project.
2. Select all conditions or one stable condition ID. Show configured repetitions,
   presentation mode, and whether pre/post tasks are included.
3. Present a short acknowledgment identifying null-trigger output and any skipped
   connected-display or graphics qualification checks. No actual recording gate or
   real participant intake is required for this explicitly selected action.
4. Run through the existing compiler, worker, and engine path. Keep fullscreen
   playback, frame timing, warmup/QC, assets, fixation behavior, and task flow.
5. Label completion and output locations as rehearsal. Keep normal participant
   summaries and inclusion decisions separate from test activity.

The first release preserves current selected-condition semantics: it runs once per
configured block and retains authored tasks and timing. It does not silently shorten
conditions, edit the project, or change which conditions a later normal launch runs.

## Implementation Sequence

1. **Define launch intent and provenance.** Map both existing launch entry points and
   write the rehearsal/normal behavior matrix. Resolve how launch intent and skipped
   checks are represented in core-owned execution metadata and persisted output.
   Prefer an additive, versioned field where existing data cannot express the fact;
   specify legacy-reader behavior before changing exports. Do not rely on PID alone.
2. **Unify launch preparation.** Reuse the existing compiler and runtime adapter.
   Keep normal production checks unchanged; rehearsal options are explicit per launch.
   Preserve full-project validation before the existing condition selector initially.
3. **Expose the user action.** Add Rehearse using shared button/dialog components.
   Adapt the source-only preference without leaving competing paths with different
   semantics. Retain cancellation and worker-lifecycle handling.
4. **Integrate result feedback.** Show session scope, completion/abort status, skipped
   checks, and output links. Use the future session-quality report when available;
   provide truthful completion feedback independently of that plan.
5. **Verify installed behavior.** Exercise the actual packaged executable without
   serial hardware and confirm normal Launch still performs its configured checks.

## Boundaries And Decisions

- Machine launch options remain outside `RunSpec` and `SessionPlan`; core owns any
  new execution-result provenance. Runtime continues to own participant/session flow.
- Do not add a second playback engine or a non-GUI application mode. PsychoPy imports
  stay lazy and confined to the engine package; use workers for launch/preflight.
- Explicitly resolve export labeling, existing source-preference migration, and
  whether a later rehearsal variant may also qualify connected hardware. Initial
  rehearsal must not claim checks that it skips.
- Reserve test identity consistently and retain exclusion from participant summaries;
  preserve real-participant seed history and repeat-participant behavior.
- New trigger drivers, shortened runs, windowed timing qualification, and changes to
  scientific scheduling or participant-intake schemas are outside this plan.

## Acceptance And Verification

- Installed and source builds expose the same Rehearse workflow. All/one-condition
  selection preserves configured repetitions and tasks without persisting selection.
- Cancel leaves document settings, participant metadata, and launch policy unchanged.
- Rehearsal opens no serial port, does not ask for Sophia confirmation, and cannot
  later disable checks for a normal launch. Output records identify skipped checks.
- Compile/preflight failures, aborts, and successful completion retain useful feedback;
  real participant statistics are not polluted by rehearsal records.
- Add unit/integration coverage for availability, explicit launch settings, output
  provenance, legacy metadata, history handling, and normal/rehearsal separation.
- Register pytest-qt coverage with fake launch workers/dialogs and no real PsychoPy
  playback. Budget Home at its existing compact size and any new dialog at an explicit
  minimum/default size, including long condition names and warning text.
- Run GUI and runtime focused verification, packaging focused checks for packaged
  exposure, and repo precommit for shared changes. Qt execution requires a user-approved
  safe visible environment; do not use local offscreen Qt.
- Record a visible manual smoke of installed Rehearse, cancellation/abort, task flow,
  output labeling, and a subsequent normal launch with its checks intact.

## Dependencies And Completion

Coordinate with [recording setup](lab-independent-recording-setup.md) on launch-option
ownership and [session quality reporting](persistent-session-quality-report.md) on
rehearsal labels. Neither plan must be implemented first to expose the existing flow.
When [session-design controls](explicit-session-design-controls.md) add persisted
counterbalance assignments, rehearsal must use an explicit rehearsal assignment and
must not consume or change a real participant's assignment.

Update `docs/GUI_WORKFLOW.md`, `docs/RUNTIME_EXECUTION.md`, `docs/PACKAGING.md`, and
affected execution-contract guidance when behavior lands. Complete this plan only
after installed-build and normal-launch regression acceptance is recorded.
