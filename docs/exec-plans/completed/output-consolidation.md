# Participant output consolidation

Status: Completed

## Outcome and user workflow

The user requested an output audit and fewer Excel/CSV files, and selected one
Excel workbook with tabs for demographics, fixation accuracy/response times and
task answers. `View > Open Participant Results` opens the project-owned
`logs/participant_summary.xlsx`. Keep its existing Participant Summary sheet and
headers; add Demographics, Fixation by Condition, Fixation Responses and Task Answers
sheets with units, recorded status and original question meaning.
Research tabs prioritize measures/answers, freeze participant/visit columns and open
on Fixation by Condition when history exists. Task Answers distinguishes question
answers, other responses and completed task activity, with answers listed first.

Fresh GUI preferences use compact output. Existing saved full/compact choices
remain in effect. Detailed run folders stay available through Settings for
timing, trigger and stimulus inspection. The standalone runtime launch API's
existing full-output default remains compatible.

The user subsequently authorized consolidating the existing spread of result
workbooks into this format and cleaning up redundant outputs afterwards. This
adds an explicit, one-time migration of existing participant results; ordinary
runtime refresh still does not delete or move historical files.

## Audit findings

- Ordinary Full output previously emitted eight session CSVs, six CSVs per run
  and three shared project tables: `11 + 6N` files, or 71 for ten runs, before
  category-specific reports and manual exports.
- Compact output previously emitted three shared tables; the participant CSV
  duplicated the participant workbook. Questions could add a raw response CSV
  and a separate readable post-condition CSV.
- The existing participant workbook combines demographics and session-level
  fixation measures, but condition measures and task answers require other files.
- Raw pre-task answers do not retain original wording or option labels in the
  compact CSV. A current editable question is not evidence of its earlier wording.

## Implementation boundaries

- Runtime owns the consolidated workbook and participant research snapshots.
  `runtime/participant_results.py` retains minimal original compiled pre/post
  definitions, task answers, individual fixation responses and response/run identity
  in private JSON records under `logs/.participant-results/`; it does not copy
  frame/event arrays.
- Checkpoint completed/partial results before later screens and capture terminal
  state before derived workbook generation. Retain response/repetition/attempt
  identity and submitted answers after a later abort or error.
- Historical full output resolves labels from contained archived plans. Historical
  compact post answers additionally recover original wording/labels read-only from
  retained typed post-condition contexts and journals. Answers without original
  evidence explicitly report unavailable labels; never substitute current editable
  project definitions or rewrite original sources during loading.
- Stop automatically generating the duplicate `participant_summary.csv`.
  Group export consumes participant rows calculated directly from canonical condition
  history without refreshing the complete workbook; an Excel lock or malformed raw
  task source cannot block this separate fixation-only export. Automatic runtime
  refresh preserves existing files. The explicitly requested migration/cleanup
  phase below separately governs historical outputs.
- Preserve `session_condition_history.csv`, raw task CSV/journals, category-specific
  reports, numbering, recovery and data-sharing commit proof. Detailed full-mode
  session/run CSV schemas remain compatible.
- The Participant Summary sheet remains free of raw answers. Task Answers is an
  explicitly identified participant research sheet, excluded from authored
  bundles/configs and data-sharing payloads.
- Research sheets distinguish Test Participant (reserved IDs `0`/`00`) from
  recorded Test Mode and Pilot Mode flags. Missing historical flags remain
  unavailable, and original Participant Summary inclusion rules stay unchanged.
- GUI access refreshes results in a worker, opens the workbook through the desktop
  service, and presents useful no-data or Excel-lock recovery messages. Workers
  do not touch widgets.

Compact mode no longer automatically derives `post_condition_responses.csv`.
Existing files remain untouched, and retained original contexts/journals support
explicit Rebuild responses in either mode. Full diagnostics preserves its legacy
automatic post-condition CSV projection. Ordinary compact output now maintains
two shared CSV/Excel files, or three with recorded task answers; category-specific
AB/Masking reports remain separate.

## Existing-output consolidation and cleanup

Status: Completed; all 13 projects with participant output consolidated and verified.

The maintenance CLI is `scripts/consolidate_existing_results.py --root <root>`
(dry-run), with explicit `--apply` for changes. It creates verified per-project ZIP
archives under `logs/.output-archives/`, retains minimal legacy research snapshots
before CSV retirement, and verifies the workbook rebuild after cleanup. Its contract
and invocation live in [Runtime Execution](../../RUNTIME_EXECUTION.md#existing-output-maintenance).
The migration retired 8,165 redundant CSVs and two covered backup workbooks across
13 projects with output; two empty projects were untouched. Thirteen verified ZIP
archives retain 8,180 original entries, including previous participant workbooks,
totalling 830,386,236 bytes. CRC and SHA-256 checks matched their exact original bytes.

- Inventory participant result workbooks/CSVs under the configured FPVS Studio
  Root Folder and associate each file with its owning project. Keep projects and
  their participant/visit identities separate; do not merge projects into a
  combined workbook.
- Inspect existing workbook sheets, row coverage and custom/manual content before
  replacement. Filenames alone do not establish redundancy. Preserve annotations,
  custom columns, formulas or specialty measurements by carrying them forward
  explicitly or retaining their original workbook; do not silently discard them.
- Regenerate each project's unified workbook through the native runtime exporter,
  using canonical recorded sources and original question contexts. Do not invent
  unavailable historical labels, timing, demographics or mode flags.
- Record source paths and SHA-256 hashes before mutation. Compare participant,
  visit, condition, task/response and fixation coverage with the generated workbook,
  including partial/aborted records and meaningful zeros. Resolve or record every
  discrepancy before classifying an original as redundant.
- Keep canonical project history/raw response logs/journals, recovery/acquisition
  records, project-level specialty reports and stimulus/input spreadsheets in place.
  Known detailed run CSVs, including timing/trigger evidence, may retire only into
  verified archives after private research materialization and workbook parity.
  Unknown CSVs remain untouched.
- Archive redundant originals reversibly only after their project's workbook
  passes parity checks. Preserve source-relative paths and original bytes, with
  a manifest containing source paths, sizes, hashes, CSV row counts and workbook
  sheet counts/content hashes. The previous workbook is also archived exactly.
  Verify resolved move targets remain within the explicitly named source/archive
  directories and verify archived hashes; do not delete original data permanently.
- Produce a per-project migration record with workbook location, matched coverage,
  preserved exceptions, archived originals and validation outcome. Do not report
  cleanup complete while parity checks or source identity remain unresolved.

## Verification and acceptance

Implementation, existing-output consolidation and final verification completed on
2026-11-04:

- Runtime tests: workbook tabs and numeric units, demographics/visit identity,
  original pre/post labels, historical missing labels, abort/partial answers,
  numbered retry deduplication, individual fixation hit/miss RTs and unmatched
  keypresses in compact captures, read-only historical post-label recovery,
  test-participant versus launch-mode flags, formula-safe text and contained paths.
- Group summary tests: results-workbook locks and malformed raw task sources do not
  block fixation-only group export or recreate the retired participant CSV.
- Fault-injection checks retain prior workbook bytes and canonical research data
  when export fails, with original execution errors preserved.
- Registered GUI tests: direct action/palette entry, background refresh/open,
  no-data/error states and saved export preference compatibility. Registered Qt
  execution was not performed; no safe visible Qt environment was approved.
- Safe verification passed: runtime focused 1000 passed/4 skipped; GUI focused
  164 passed; docs focused 13 passed; data sharing 40 passed; latest focused
  regressions 28 passed; maintenance CLI tests eight passed. Harness CheckConfig
  passed for all 15 scopes. Final repo precommit passed: 5211 passed/32 skipped.
  An initial unrelated Windows `WinError 5` while renaming temporary bundle staging
  in `test_import_project_bundle_never_overwrites_existing_project_folder` passed
  its isolated retry (one test) and the subsequent full precommit run.
- All 13 native workbooks retained 146 Participant Summary rows, 188 Demographics
  rows, 1900 Fixation by Condition rows, 9351 Fixation Responses rows and 1228 Task
  Answers rows. Rebuilds before/after archival preserved the same recorded values,
  with the final answer-first Record Type presentation also verified.
- Active result areas now contain 16 canonical CSVs and 13 unified workbooks.
  Whole project trees contain 101 CSVs and 90 workbooks because 85 input CSVs and
  77 input workbooks were intentionally preserved. No projects were combined.
- Final migration verification reported zero issues: 17,157 numeric measure cells,
  12,813 text participant-ID cells, no formula/error cells and valid archive hashes.
  It recorded 5,799 current research-source fingerprints; this current-state
  inventory is not an independent pre-migration hash baseline.
- All six workbook tabs were visually reviewed through artifact renders, including
  the final Task Answers presentation. This was document rendering, not native
  Excel or Qt execution. Detailed external evidence remains outside the repository
  at `.fpvs-studio/results-consolidation/verification-20261104T135550Z.json` beneath
  the configured Studio root.
- Remaining optional visible smoke path, not executed: launch a compact session
  with before/after questions,
  open Participant Results, inspect all tabs and units, repeat a visit, and retry
  after closing an Excel-locked workbook. Verify Settings can opt into detailed
  run CSVs and existing saved Full preferences still work.

No presentation timing, scoring rules, question controls, hardware behavior,
release or publication changes are part of this work.
