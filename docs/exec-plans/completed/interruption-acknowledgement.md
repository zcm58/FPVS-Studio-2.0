# Acknowledge incomplete sessions once

Status: Completed

Date: 2026-10-27

## Authorized outcome and user flow

Stop repeatedly warning about the same incomplete participant session whenever its
project opens. The operator explicitly chooses **Acknowledge and Continue**, then
returns to their work. Original incomplete-session evidence and results remain
intact. New interruptions still prompt; acknowledgements travel with project logs.

## Boundaries and implementation

- Runtime owns versioned acknowledgement records under
  `logs/.condition-recovery/acknowledgements/`, separate from checkpoint/acquisition
  records and project authoring settings. Scope them to an execution and run.
- Discovery remains read-only. Automatic opening excludes acknowledged interruptions
  and their missing-plan notices; manual **View > Interrupted Sessions** retains
  history and existing explicit rerun safeguards.
- The primary dialog action acknowledges all shown pending records. Window X,
  Escape and Close do not count as acknowledgement. Saving runs on an app-owned
  worker; show busy state, retain the dialog on failure and allow retry. No research
  result is changed to complete and no acknowledgement starts an experiment.
- Preserve the dialog's 640x440 minimum and 760x520 default, both palettes, long
  participant/condition content, and keyboard/late-result/project-close safety.

## Acceptance and verification

1. Runtime tests prove explicit persistence, read-only discovery, idempotence,
   new-execution/run reminders, legacy acquisition support and preservation of all
   original evidence. Reject stale/foreign/live evidence and unsafe/corrupt state.
2. Registered Qt tests cover primary acknowledgement, automatic versus manual
   history, saving/failure/retry, passive dismissal, stale jobs and minimum geometry.
   Use the safe visible Windows session approved earlier in this conversation;
   never offscreen execution or actual participant/hardware presentation.
3. Run focused recovery/GUI/runtime checks and repository precommit for the shared
   workflow. Report platform skips and intermittent Windows filesystem failures
   explicitly. No release build/publication was requested by this change.

## Progress

- Baseline is clean synchronized master at `597636e`.
- Existing controller remembers shown records only for one window's lifetime, which
  explains repeated prompts after reopening. Runtime has no persistent acknowledgement.

## Completed behavior

- Runtime now stores schema-versioned acknowledgement sidecars with a stable
  execution/run filename hash. Records bind project, participant/visit/session,
  occurrence, relative evidence path and reviewed evidence timestamp. Duplicate
  acknowledgement preserves the original timestamp; updated evidence stays pending.
- Automatic queries skip acknowledged snapshots and their missing-plan warnings
  before opening large saved plans. Manual queries retain acknowledgement timestamps
  and existing recovery behavior. Plan availability and acknowledgement metadata do
  not invalidate otherwise unchanged evidence or existing rerun dialogs.
- The primary action acknowledges all currently shown pending notices. Save work
  runs off the GUI thread; success closes the notice after worker completion, while
  failure retains a retryable view. Passive dismissal never acknowledges. Busy/hidden
  launch completion, project teardown and late results cannot leave a stuck Saving
  view or affect another project. New snapshots can prompt within the same window.
- The dialog distinguishes unconfirmed completion from confirmed incompleteness.
  The rerun confirmation is explicitly labelled as a prerequisite for rerunning,
  separate from acknowledgement. The footer uses two rows to fit all button text.
- Path checks reject redirected, unknown-reparse and multiply linked acknowledgement
  paths while supporting ordinary OneDrive cloud placeholders. Discovery creates no
  files, and no original checkpoint, acquisition, plan or research result is modified.

## Verification results

- Final repository precommit passed Ruff, compilation, mypy for all 243 source files,
  harness/documentation checks and 3,589 non-Qt tests, with 12 Windows symlink-permission
  skips and 24 passing subtests, in 498.92 seconds. No broad-suite failure remained.
- Visible registered Qt coverage: all 53 recovery-dialog/controller tests passed.
  Real rendered captures cover pending, multiple, saving and error states at 640x440
  and acknowledged history at 760x520, with light/dark palettes and device pixel
  ratio 1.0. Root and GUI agent inspected the corrected renders without clipping.
- Safe GUI focused route: 83 passed. Its first run exposed two stale fake-controller
  fixtures missing the new acknowledgement-job attribute; the fixtures were updated
  and the full focused route passed. Production behavior was not weakened.
- Baseline recovery tests passed 44 with one symlink skip. Expanded backend coverage
  passed 60 with one skip before the final added cases; all seven final targeted
  cases passed, and the final broad suite covered every expanded case together.
- Independent review found no remaining material data-loss, suppression, worker-state
  or rerun regression. Evidence and synthetic captures remain under ignored
  `build/interruption-acknowledgement-evidence/`.

## Concurrent upstream changes

The first push was rejected because another PC advanced master with Welcome-screen
copy changes `08ea16a` and `fff2b77`. These merged cleanly in `3d7470d`, retaining
the interruption fix `ed3ca56` and the other PC's removal of routine Welcome hints.
No force push or overwrite was used.

After the merge, mypy again passed all 243 source files, relevant Ruff checks passed,
and the safe GUI focused route passed all 83 tests. The combined visible recovery,
Welcome, default-hardware and component run initially hit an existing clipboard
integration test: Windows returned `OleSetClipboard` / `0x800401d0 OpenClipboard
Failed`, also stalling Qt shutdown. The exact Welcome test reproduced that platform
failure. No clipboard production behavior or assertions were changed to hide it.

The post-merge visible run passed 189 cases with the two clipboard-dependent cases
explicitly deselected. It includes every interruption-dialog check. The excluded
cases were `test_manage_projects_dialog_lists_projects_from_saved_root` and
`test_source_details_exposes_and_copies_full_long_path`; their platform limitation
and the interrupted attempt remain in the retained evidence logs.

## Delivery boundary

This is a source fix. No release version, installer, real participant session or
hardware setting was changed; the published 2.5.0 binaries retain their recorded
source. A subsequent installer build is needed to deliver this behavior to installed
application users.
