# Plain-language session randomization

Status: Completed

## Workflow and acceptance

Researchers choose Randomized (new for each participant) or Pseudorandom (same for
every participant) independently for image/word order, condition order and fixation
color-change timing. Session replaces numeric seed entry with three labeled choices
and concise explanations of the selected effect. Condition order remains editable.
Repeatability applies to corresponding condition presentations with unchanged inputs;
different source pools/durations do not imply identical schedules across conditions.

The existing Session form is 760 px wide inside the 1120x820 Setup minimum/default.
All choices, explanations, saved-order actions, errors and session totals must fit
without scrolling. Review must describe the three choices without seed jargon.

## Boundaries and compatibility

Core owns independent policies and resolution; the document resolves one snapshot per
participant/visit and reuses it for retries. Preserve existing roots, scheduling
algorithms, balanced orders, task randomness and AB/masking boundaries. Optional
per-category policies extend existing formats; their absence preserves the old overall
policy. Compiled/run/result/config provenance carries mixed policies and exact roots.
Saving a condition arrangement fixes only condition order; historical saved projects
retain their overall-policy interpretation until explicitly edited.

## Verification

- Core tests cover all eight combinations, fixed-domain override rejection, repeated
  compilation, saved order, persistence/config/result provenance and protocol identity.
- Registered Qt tests cover three independent controls, reopen, failure recovery,
  Review and no clipping at 1120x820 in both themes.
- Run focused GUI/compiler checks and repository precommit. Qt/visual execution is
  deferred unless the user approves a safe visible environment.

## Progress

- Baseline GUI focused verification: 136 passed.
- Implemented the three choices, category-specific explanations, seed-free Review,
  independent resolution, saved-order behavior and matching artifact provenance.
- Final GUI focused verification: 136 passed; compiler focused: 783 passed.
- Changed-file Ruff/compilation and source mypy passed. Repository precommit passed:
  4597 tests passed, 13 Windows symlink tests skipped. Documentation focused: 13 passed.
- Project/config and history export entry points retain the active project root and
  existing path owners; this change introduces no new filesystem destination.
- Registered Qt coverage is updated in the existing registry modules. Dialogs,
  workers, runtime calls and filesystem operations use the existing test doubles.

## Visible smoke path (not performed)

Open a normal visible Windows session, open a project and select Setup > Session at
1120x820 in both themes. Change each choice separately, check its explanation, save
and reopen. Verify the choices in Review. Save a condition arrangement and confirm
only condition order becomes Pseudorandom; switch it to Randomized and check the
inactive arrangement message. Check all controls and wrapped labels remain visible.
The separate condition-order dialog retains 700x520 minimum and 780x620 default.
Qt execution still requires explicit approval for a safe visible environment.
