# Typed Attentional Blink recall and readiness gates

Status: Completed

## User workflow

Continue the burst study with two typed recall questions. Enter or the Next
button submits each answer. Require Space before every burst, with
"Press space when you're ready to continue." Apply the participant-flow changes
to new built-in AB studies and the existing MSMS attentional blink project.

The user initially requested 12 Hz, then explicitly retained 10 Hz to preserve
the exact 100/300/500 ms SOAs. Five-second duration, 24 configurable bursts per
SOA, randomized order, colors and trigger codes remain unchanged.

Test-mode sessions must record and display the same independent T1/T2 accuracy,
with test sessions identified in the dedicated results view and workbook.

## Implementation boundaries

- Core owns typed question definitions, compiled target answer keys and gates.
- Runtime scores and checkpoints raw typed responses and reports test accuracy.
- Engine renders a text field and Enter/Next submission without timing ownership.
- Update only the named study's required configuration; preserve experiment
  identity, unrelated settings and historical runs/logs. Back up its project JSON.
- Keep legacy clicked recall projects executable and old response records readable.

## Verification

1. Typed correct/incorrect/unknown/aborted answers and immediate T1 checkpoint.
2. Enter and Next fake-renderer submission, including per-screen input reset.
3. Space gate before all compiled entries and no burst until Space is received.
4. Test-mode answers, SOA accuracy, explicit session identification, full/compact export.
5. Validate and compile the updated MSMS project; verify unrelated data unchanged.
6. Focused checks and repo non-Qt precommit; document native GUI/hardware limits.

## Progress

- Located the configured study through Studio's user settings.
- Confirmed the main checkout still matches the previous verified delivery.
- Added typed recall answer keys and Next labels to the existing task contracts.
- Kept old single-choice tasks readable and executable. Whole typed answers are
  compared after trimming spaces; raw text is retained and unknown answers are wrong.
- Required the Space readiness gate before every recall burst. Fake presentation
  checks cover Enter, Next, separate inputs and rejection of stale keys at the gate.
- Included completed test sessions in dedicated recall accuracy and identified them
  in the GUI, CSV and Excel, including old test-session journal records.
- Validated the named MSMS study update: 72 five-second entries, 144 typed questions,
  72 Space gates, unchanged 10 Hz/SOAs/triggers. Only recall task, instructions and
  metadata update time change. Delivery backs up its project JSON and verifies all
  54 historical/other files against their previous hashes.

## Verification result

- Repo precommit passed: 1,580 tests passed and seven Windows symlink tests skipped;
  Ruff, compilation, mypy and repository documentation/architecture audits passed.
- Added registered Qt coverage; native Qt/PsychoPy window and physical EEG/display
  checks were not run. The visible smoke path is in `docs/GUI_WORKFLOW.md`.
- No installer build or publication was requested or performed.
