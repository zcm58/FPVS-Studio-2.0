# Attentional Blink burst recall study

Status: Completed

## User workflow and acceptance

New built-in Attentional Blink studies present five-second bursts at 10 Hz.
White letters fill the stream; each burst has one randomized green T1 digit and
one different white T2 digit. The three onset-to-onset SOAs are 100, 300, and
500 ms, with condition trigger codes 1, 3, and 5. Each SOA has 24 bursts by
default (120 seconds of EEG per SOA); the GUI exposes bursts per SOA and the
resulting duration. Burst order is randomized with balanced SOA totals.

Each burst is followed by "What was the green number?" and "What was the
second number?" Responses and independent T1/T2 correctness must be linked
to the actual presented targets, SOA, participant/visit, and chronological
burst number. Researchers can inspect accuracy by SOA and over time in the
GUI, retain machine-readable data, and export a dedicated Excel workbook.

## Boundaries and assumptions

- Core owns defaults, exact frame timing, seeded randomization and compiled tasks.
- Runtime owns answers, scoring, incremental persistence and reporting.
- GUI edits persisted settings and presents the shared reporting result using workers.
- Preserve existing saved studies and unrelated Oddball behavior.
- The five seconds describes stimulus presentation; participant response time is extra.
- Use 24 bursts per SOA to meet the user's requested 100–120 seconds per SOA.
- No installer release or remote publication is part of this implementation request.

## Work and verification

1. Update defaults, burst compilation and GUI settings. Verify exact 50-character
   streams at 10 Hz, one target pair, SOAs, markers, shuffled balanced counts,
   seed repeatability, changed seed variation, and persistence.
2. Record and score both answers. Verify against actual targets, retain partial
   answers on abort, and verify both full and compact exports.
3. Add GUI results and Excel export. Verify typed summaries, chronological rows,
   participant/visit separation, and workbook values with non-Qt tests; register
   Qt coverage and document visible acceptance.
4. Run focused checks and repository precommit, review the complete diff, and
   integrate the verified change into the user's checkout.

## Implementation and validation

- Core defaults compile 72 shuffled entries with one T1/T2 pair per five-second
  burst. GUI count and rate edits remain atomic and persist through project,
  configuration and portable-bundle round trips.
- Runtime checkpoints target context and each answer in both export modes;
  partial T1 answers remain available after T2/session abort. The read-only
  Tools dialog and dedicated Excel writer share typed summaries.
- Simulated PsychoPy playback verifies all three SOAs, target colors, condition
  codes 1/3/5, target codes 55/56 and the complete 300-frame stream at 60 Hz.
- Repository precommit passed: Ruff, compilation, mypy (169 source files),
  architecture/docs audits and 1,558 non-Qt tests. Seven Windows symlink tests
  were skipped because the account lacks symlink privileges.
- Windows verification needed Python 3.10 on PATH, ordinary named-pipe process
  permissions and a short forward-slash pytest basetemp. Long-path test failures
  from an incorrectly escaped basetemp disappeared after correcting that invocation.
- Final registered GUI coverage is retained; it was not run locally. Visible
  Setup/dialog and physical timing/trigger acceptance remain documented in
  `docs/GUI_WORKFLOW.md`. No installer build or release was performed.

## Verification limits

Native GUI and physical display/trigger acceptance must be reported separately
from automated non-Qt tests. Local offscreen Qt execution is prohibited.
