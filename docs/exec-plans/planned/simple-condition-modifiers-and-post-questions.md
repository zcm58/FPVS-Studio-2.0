# Simplified Condition Modifiers and Readable Post-Question Responses

Status: Planned

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`. This is the fifth
feature plan on the branch; implementation has not started.

Simplify the main **FPVS Condition Modifiers** workflow around straightforward
Counting, Memory, Masking and **Post-condition Questions** actions. Keep detailed
custom editing available separately. Adding a simple question must not require users
to understand task modules, IDs, technical option syntax or before/during/after plumbing.

The user confirmed:

- Assigned questions appear after **every presentation** of the selected conditions,
  including repeats. They run outside FPVS stream timing.
- The simple editor defaults to Yes/No and also offers the existing other response
  types. Support an ordered question list rather than limiting a condition to one question.
- Participants select or enter an answer, can revise it, then explicitly press **Continue**.
  Selection alone does not commit the answer or advance the question.
- New questions default to required, self-paced answers with no time limit and no
  correctness scoring unless the author explicitly configures it. No is a valid
  answer, never an implicit error or missing response.
- Write one cumulative CSV directly in the experiment's project folder, across
  participant sessions. Use a **column-based layout**: one row per condition
  presentation with assigned questions, with one answer column per question.

Example question: **Did you see a fearful face?** Example path:
`<FPVS Studio Root>/<experiment project>/post_condition_responses.csv`.
The active project root is authoritative, including projects opened from other locations.

## Current evidence and reuse

- `gui/condition_modifier_dialog.py` already owns detached drafts, Apply/Cancel,
  assignment, shared settings/copies and access to advanced custom tasks.
- `gui/condition_task_dialog.py::QuestionnaireEditor` supports single/multiple
  choice, text, numeric and rating questions. The current advanced path exposes
  technical option fields and defaults to Option 1/Option 2; there is no simple Yes/No preset.
- `core/task_models.py::TaskQuestion`, `TaskModule` and post-condition `TaskBinding`
  already represent these questions. Yes/No is a single-choice question with stable
  option identities. Do not add a second answer engine or a new boolean response type.
- `ConditionModifier` currently requires both before and after module references.
  An after-only questionnaire fits an ordinary post-task binding; do not add a dummy
  before step or force questions into a sustained modifier group.
- `core/compiler_tasks.py` and `runtime/task_runner.py` already compile and present
  questions individually, validate replies and journal each submitted response.
  `TaskStep.submission_mode` and `submit_label` already support explicit Continue.
- Existing exports use per-run/session `task_responses.csv` files in full mode and
  cumulative `logs/task_responses.csv` in compact mode. Generic raw records lack
  question wording and readable answer-label snapshots.
- `TaskResponseRecord.repetition_index` is a task-module repeat, not a condition
  presentation count. The readable CSV must use the original SessionPlan occurrence.

## Proposed authoring and participant flow

1. Open the existing modifier entry point from Conditions. Show assigned activities
   and a concise ordered before/during/after flow, with obvious common add/edit actions.
   Retain current names, participant instructions, media, presets and assignment rules.
2. Choose Post-condition Questions, type the question and accept the Yes/No default,
   or select another supported response type. Generate stable IDs and ordinary option
   rows automatically; technical IDs are not required author input.
3. Add/reorder questions and explicitly choose their conditions. Default assignment
   to the condition being edited; make shared versus condition-specific edits clear.
   Reuse a shared question identity across conditions assigned the same questionnaire.
4. Offer a participant preview and an explicit Apply/Cancel draft lifecycle. Preview
   creates no participant data, consumes no execution seed and launches no PsychoPy window.
5. Run the assigned questions after each completed FPVS presentation using the existing
   post-task flow. Preserve modifier-owned post-steps such as counting endpoints and
   memory recognition; show their ordering rather than silently moving or replacing them.
   Required questions cannot continue until answered; Escape retains its abort behavior.
6. Add a project-aware **Open Responses Folder** action beside the question/output
   summary, available in both full and compact modes. Show the exact CSV filename/path
   with accessible full-value details; do not depend on Open Run Folder or full output mode.

## CSV contract and durability

- Use `post_condition_responses.csv` under the active project root in both export
  modes. Creation is automatic when this question flow produces data; do not create
  output merely by opening, previewing, applying or saving authoring settings.
  Its scope is the newly assigned Post-condition Questions flow. Do not automatically
  assimilate unrelated modifier, legacy, AB or advanced custom-task answers; their
  existing exports remain intact.
- Put readable participant number, numbered session/visit, condition name and condition
  presentation number first, followed by question answer columns. Response-time and
  per-question completion/status columns can follow. Retain stable project/session/
  run/question identities needed to distinguish executions and rebuild the view.
- Resolve condition names, original question text and displayed answer labels from
  the original compiled execution context. Never reinterpret old answers from today's
  editable question definitions. Preserve that context with existing neutral/recovery
  records when needed for crash recovery; do not invent unavailable historical labels.
- Use module + question + definition-version identity for columns: question IDs are
  unique only inside a module, and private copies can retain their question IDs.
  Questions shared across
  conditions reuse their columns. Distinct questions with the same wording must not
  merge accidentally. Define safe additive column/version handling for questions
  added or edited after data collection; never silently rename or reinterpret old data.
- Unassigned, unanswered, timed-out, aborted and not-presented values remain distinct
  from No and zero. Earlier submitted answers survive a later question/session abort.
  Include response/task/run/session completion information with its actual meaning.
  After a hard interruption, no journaled answer does not prove that a question was
  never displayed. Use unknown/interrupted status unless durable question-start
  evidence supports a more specific presentation status.
  Create a row from the compiled assignment even if an earlier modifier post-step
  aborts before these questions start; known skipped question phases can be marked
  not presented. Do not rely solely on answer records to discover expected rows.
- Keep detailed raw responses and all attempts in their existing journals/exports.
  The friendly wide CSV is a derived readable view, not a replacement source of truth.
  New simple questions have one final answer after Continue. Do not flatten complex
  saved repeated/branched tasks into this initial view. If advanced editing makes a
  new question flow incompatible with one answer per question/presentation, surface
  that incompatibility rather than silently discarding attempts or changing row meaning.
- Reuse runtime export helpers, project reporting locks, atomic replacement and
  complete execution identities. Do not deduplicate by participant, question or seed
  alone: fixed-seed runs and repeated visits must retain separate rows.
- Project the answers after each presentation and during abort/failure finalization.
  Existing per-answer journals remain the first durable write. Address the current
  mid-questionnaire exception gap by reconciling already journaled answers with the
  original execution context; do not build a second competing capture pipeline.
- If Excel locks the CSV or an output write fails, retain durable answers and report
  an actionable retry/rebuild path. Do not silently lose a response or corrupt prior rows.
- Preserve CSV quoting, Unicode and existing formula protection for user-authored
  question/answer/header text. Clearly label response-time units and their existing
  measurement meaning; do not confuse export time with answer time or FPVS onset RT.

## Ownership and compatibility boundaries

GUI owns the simpler editor, previews, scope and folder action using existing components
and workers. Core owns authored questions, stable identities, validation and compiled
contracts. Runtime owns collection, durability and the readable CSV projection; engines
only render participant steps and return responses. No widget-owned answer files.

Use the existing active-root/path helpers and reject redirected paths. Project display
renaming must not move/recreate the response file or change captured identities.
Ordinary bundles already admit only project.json and stimuli; clean Library preparation
copies contracts and declared images. Preserve those positive inventories and verify the
root response CSV is excluded. Do not add a blanket CSV ban that would remove legitimate
stimulus CSVs, and do not put raw participant answers into app logs or generic summaries.

Complex saved custom tasks must remain editable without flattening their branching,
scoring, layouts, media, attempts or ordering. Shared modules must not be changed in
other conditions without an explicit scope action. Keep all media staging and Cancel
preservation guarantees. Native AB recall/reporting and specialized masking behavior
retain their existing contracts.

## Acceptance and verification

- A user can add the example question without visiting the advanced task editor,
  assign it to selected conditions, preview, Apply, save/reopen and see the same setup.
- Yes/No needs a deliberate selection and Continue; the answer can be changed before
  Continue. Required self-paced and unscored defaults work, and other supported types
  remain available without demanding technical pipe-separated option syntax.
- A condition with three presentations asks its assigned questions three times. Each
  presentation's answers occupy one CSV row with the correct chronological occurrence,
  independently of task-module repeat indices or shuffled global position.
- Full and compact runs populate the same root CSV schema. Two participants and a
  repeat visit append distinct rows, including when their three execution seeds match.
- Correct readable labels and answers survive question/condition edits, aborts,
  post-questionnaire exceptions, restart/recovery and a temporarily locked CSV.
- New question columns preserve existing rows; question identity/version conflicts are
  reported explicitly. Test commas, quotes, multiline text, Unicode and formula-like text.
- Existing counting, memory, masking, presets, complex custom tasks and other conditions
  remain intact through open/Apply/Cancel, shared-edit scope and copied questionnaires.
- Verify the response CSV stays within the active project, survives display-name rename,
  and is absent from bundles and Library/upload payloads. Legitimate stimulus CSVs stay.
- Define the simplified dialog's size budget before implementation, starting from the
  existing `1100x720` minimum / `1120x760` default and Conditions at `1120x820`.
  Register both-theme tests for empty/populated/invalid/shared/preview/busy/error states,
  long questions/answers/paths and no clipping. Do not run Qt without approved visibility.
- Run core/compiler/project-I/O/runtime/engine/gui focused routes and repo precommit.
  Participant-screen acceptance requires the intended presentation environment.

## Related work and exclusions

Coordinate occurrence identity with [presentation counts](../completed/per-condition-repeat-counts.md)
and preserve [stream-duration boundaries](../completed/per-condition-stream-duration.md). New question
authoring must not consume the stimulus/condition/fixation RNG domains in the
[seed plan](reproducible-randomization-controls.md).

The older [participant results and question presentation proposal](participant-results-and-question-presentation.md)
remains separate: a results browser, Masking/group statistics, Excel workbooks and a
general participant-screen restyle are not added by this plan. Reuse compatible
provenance/export work rather than introducing parallel answer stores.
