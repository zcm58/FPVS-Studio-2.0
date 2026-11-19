# Participant results and question presentation

Status: Planned

Baseline reviewed: Studio 3.1.0 (2026-11-19)

## Current baseline

- **View > Open Participant Results** regenerates and opens
  `logs/participant_summary.xlsx` through the existing summary workflow. The
  workbook includes demographics, visit and fixation information and a **Task
  Answers** sheet with original question and option text where available.
  See [participant output consolidation](../completed/output-consolidation.md)
  and the [menu action](../../../src/fpvs_studio/gui/main_window.py).
- [Participant results](../../../src/fpvs_studio/runtime/participant_results.py)
  already reads compact and full records, resolves visit and answer identities,
  checks conflicting evidence and recovers retained question labels. Reuse these
  paths where their input and deduplication semantics match the viewer.
- [Masking reporting](../../../src/fpvs_studio/runtime/masking_report.py)
  records versioned trial rows and archived scene plans. Specialized aggregate
  Masking views, a filtered response viewer and an explicit export of its loaded
  selection are proposed. Optional participant question styling is a separate slice.

## Outcome and workflow

1. Add **View > Participant Responses...** for modular tasks. A read-only table
   filters by participant, visit, condition and question, showing recorded answers,
   correctness when defined, reaction time, attempts and completion status.
2. For Masking, provide **Trials**, **Participant Summary** and **Group Summary**
   views. Show the actual target, selected target, PAS, frequency, SOA, condition
   code and catch outcome. Keep missing, invalid and aborted records inspectable.
3. Export the loaded result to a user-selected Excel workbook containing answers,
   participant summaries, group summaries and inclusion/denominator notes. Loading
   never rewrites project data or regenerates existing summaries.
4. Offer an opt-in, reusable question presentation with clearer typography,
   spacing, choice boundaries and selection cues. Existing projects retain their
   current rendering unless the presentation is explicitly selected.

The current response records already contain most evidence. Existing participant
and group spreadsheets summarize fixation performance; they must not silently
become Masking summaries. Keep existing fixation and AB reporting intact.

## Data sources and historical joins

- Finalized Masking rows: `logs/masking_trials_v2.csv`; read v1 alongside it when
  present without modifying either schema. Missing historical PAS/catch fields
  remain unavailable, never zero or inferred normal trials.
- Raw modular answers: compact `logs/task_responses.csv`; full-mode session
  `task_responses.csv` and per-run response journals under the recorded output
  paths. Use session/history metadata to identify full exports, with all path
  resolution contained within the active project root.
- Interrupted evidence: full per-run `task_responses.jsonl` and compact
  `logs/.task-response-checkpoints/*.jsonl`, plus their execution metadata. Label
  checkpoint-only records incomplete. Surface malformed/truncated tails without
  repairing journals or fabricating missing answers.
- Historical Masking context: `logs/masking-scene-plans/*.json` stores the compiled
  plan and participant visit in both export modes. Full sessions additionally
  contain `session_plan.json`. Resolve variant, intended exposure, option labels
  and original questions from these archived plans, never from editable current
  condition names or current scoring settings. Plans prove intent, not playback.
- Join trial evidence using `(project_id, participant_number,
  participant_session_number, session_id, run_id)`. Join answers with the same
  execution identity plus `response_index`; retain task/step/repetition/attempt
  fields so separate responses remain distinct. Match a numbered finalized record
  to its checkpoint only with complete identity; report conflicting payloads.
  Do not collapse legacy unnumbered executions using session/run IDs alone.
- Recover original question wording and option labels from retained participant
  result definitions or archived plans wherever available. Raw task records
  carry IDs. When the original wording is unavailable, display the recorded IDs
  with an explicit unavailable-label note. Masking frequency is joined from the
  `masking-frequency` answer; PAS/identity and catch outcomes already have joined
  v2 fields. No new research measurements are proposed.

## Summary rules

- The observation is one sequence/run and its questions. Forty repeated flashes
  are exposure information, not forty independent answers.
- Group by recorded variant and SOA, retaining requested/achieved SOA and trigger
  code for inspection. Missing variant metadata stays visibly unclassified.
- Identity accuracy: correct valid, non-aborted identity answers divided by valid,
  non-aborted identity answers on non-catch runs with target-exposure evidence.
  Show partial exposure separately; a later question/session abort does not erase
  an already valid answer. Catch identity correctness remains undefined.
- PAS and frequency: distributions of valid, non-aborted ratings, each with its
  own answered/missing counts. Preserve the existing numerical scale meanings.
- Detection: use the recorded Masking hit/miss/correct-rejection/false-alarm
  outcome. Catch false-alarm rate is false alarms divided by false alarms plus
  correct rejections; the current runtime assigns catch outcomes only after full
  stream exposure and valid PAS. Do not substitute fixation false alarms.
- Participant summaries retain visit identity. Group results summarize participant
  rates within each variant/SOA, with contributing participant and answer counts;
  pooled trial totals are separately labeled. If multiple visits are included,
  combine within participant before computing the group mean, so extra visits
  do not silently increase that participant's group weight.
- Explicit filters identify test participants, partial exposure and incomplete
  visits; display the active inclusion rule and export it. No inferred inclusion
  policy from the general fixation workbook. One catch per variant/participant
  means catch-by-SOA results will be sparse; always show their denominator.

## Ownership and reusable paths

- Keep typed, read-only task loading and explicit workbook export in runtime.
  Reuse the existing identity, provenance and contained-path logic from
  `participant_results.py` where compatible. Keep Masking joins and summary rules
  alongside the runtime reporting code and expose typed results to the GUI.
- Add a result dialog and `gui/main_window.py` entry point. Follow the loading,
  error, empty and busy-close patterns in `attentional_blink_data_dialog.py`.
- Question presentation stays in `engines/psychopy_tasks.py`, through an explicit
  shared task presentation setting if the existing task layout cannot express it.
  Runtime/core continue to own task resolution, validation and scoring.

Preserve PAS 1-4 and frequency 1-5 labels/IDs, question order, randomized identity
positions, stimulus colors and geometry, submission mode, required-answer rules,
and response/scoring semantics. Do not add correctness feedback or alter EEG
stream timing. Any additive presentation contract defaults to the existing style
and needs the usual backward-compatibility guards; decide its smallest shape
after reviewing a concrete preview.

## Implementation sequence and verification

1. Audit representative 3.1.0 and legacy projects for the fields and identity
   needed by each view and export. Implement typed read-only loading and joins;
   define how unavailable fields appear. Test full/compact equivalence,
   numbered visits, unnumbered ambiguity, finalized/checkpoint deduplication,
   truncated journals, v1/v2 data, missing plans and labels, and contained paths.
2. Implement and test summaries and explicit workbook export before binding the
   viewer. Cover denominators with missing/invalid answers, catches, partial exposure and
   later aborts. Assert 40 flashes produce one answer; repeated visits do not
   multiply participant weight; no catch identity score is invented. Verify
   known workbook values and that reads leave all source hashes unchanged.
3. Add the viewer and export using background workers. Register GUI tests for
   filters, export cancellation/failure, busy-close guards, no-data/error states,
   and accessible long values at minimum/default size. Use existing AB/fixation
   dialog tests as patterns; keep their behavior unchanged.
4. Review a concrete preview as a separate styling slice. If selected, use
   fake-engine tests in the modular task suite to verify identical selected IDs,
   ratings, scoring and submission behavior. Cover the longest labels, all three
   Masking identity grids and existing project rendering. Record visible
   participant-screen acceptance separately.

Run the narrow runtime/GUI/engine verification routes for changed owners, then
repo precommit for shared changes. No Qt execution without an approved safe
visible environment. Release/version/library publication decisions are a later,
explicit scope decision, not part of this proposal.
