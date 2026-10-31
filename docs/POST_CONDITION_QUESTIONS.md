# Post-condition Questions

The FPVS Condition Modifiers dialog makes simple before and after questions its
primary actions. Counting, Memory, Masking, presets and custom tasks stay in the
collapsible Advanced modifiers section. Questions reuse ordinary task modules and
do not alter the FPVS image stream, presentation frequency or fixation schedule.

## Authoring and participant flow

Each add action opens the simple builder directly with one blank, required,
self-paced, unscored Yes/No question. Phase and condition scope remain visible;
editing an existing questionnaire adds no question. Use **Add Question** repeatedly
to add multiple questions, then select a numbered question and use **Up/Down** to
choose display order. Before and after lists are independent; saving and compilation
preserve each phase's authored question order without using Advanced. Other existing
response types remain available. Participants can change their selection
before pressing Continue. Selecting No is a valid answer.

Assignments default to the selected condition. Before questions run ahead of protected
counting/memory start screens; after questions run after every presentation, following
the existing modifier-owned post-task steps. Shared questionnaires retain one identity
across their assigned conditions;
private copies have separate module identities. Apply and Cancel retain the existing
detached modifier draft lifecycle. Preview creates no participant results.

Basic before editing accepts compatible single-screen, self-paced questionnaires in
ordinary unmarked pre-condition modules. Complex, specialized, modifier-owned and specially
scoped tasks remain Advanced; opening the dialog never flattens or converts them.
Before answers retain ordinary task journals and exports and do not enter the
after-only readable CSV below. No serialized field or schema version is added.

`core/post_questions.py` owns basic question factories and assignments, plus marked
after-question definition versions. `PostQuestionsDialog` selects the phase and
defaults to after-condition for existing callers. `TaskModule.simple_post_questions`
explicitly identifies the after-only readable flow.
Unmarked advanced, legacy, counting, memory and AB responses retain their existing
exports and are not automatically included in the readable view. A marked flow must
remain a single pass with explicit submission, without branching, repeats or retries.
Incompatible advanced changes are reported rather than flattened.

Session compilation attaches a frozen `PostQuestionnaireContext` to each marked
`TaskModuleSpec`. It captures original condition names, one-based chronological
condition presentation number/count, authored question definitions and answer labels.
It does not use the task-module repetition index as a condition presentation number.
Definition versions hash the authored question before any option shuffle. Columns
are identified by module, question and definition version, so participant seeds and
option shuffles do not change their meaning.

## Readable CSV

The active project owns `post_condition_responses.csv` directly in its folder,
in both full and compact export modes. The GUI's Open Responses Folder action uses
that project folder independently of any detailed run folder. Open Responses Folder
and Rebuild responses appear only while Advanced modifiers is expanded. The folder
button's tooltip and accessible description expose the CSV filename and full path.

Each attempted condition presentation with assigned questions occupies one row.
Participant, numbered session/visit, original condition name and presentation number
come first. Question answer columns follow, then response-time and status columns.
Stable execution, session, run and condition identities distinguish fixed-seed runs,
different participants and repeat visits. Never-started future presentations do not
produce rows. Authoring, preview and saving settings do not create the CSV.
`FPVS stream completed` records Yes, No or Unknown separately from later question
and session completion; a question abort does not erase completed stream evidence.

Headers combine the original prompt with a module/question/version suffix. Equal
prompts from different questionnaires are distinct. Editing a question adds a column;
unchanged questions keep their columns. New columns are additive and earlier rows
retain their original meanings. A suffix collision or conflicting definition produces
an explicit error. Unicode, quoting and multiline values use ordinary CSV encoding.
Spreadsheet formula protection applies to all authored text, including headers.
Unrecognized manually added CSV columns stop rebuilding and preserve the annotated
file for review rather than silently blanking those values.

Answers use original displayed labels such as Yes and No, entered text or numeric
values. Zero remains a real answer. A partial unsubmitted selection is not accepted
as an answer. Status distinguishes answered, unanswered, not assigned, not presented,
aborted, timed out, invalid and interrupted values. Missing responses after abrupt
loss are conservatively interrupted; absence of a journaled answer alone never proves
that a question was not displayed. `not_presented` requires an orderly terminal flow
that did not start that questionnaire. `not_finalized` means the session has no
durable terminal status; the last recorded stage does not prove a process is live.

RT columns are seconds using the existing question-response clock, from the question
screen to submission. They are not stimulus-onset RTs or export timestamps.
Detailed correctness, scores and all raw attempts remain in the ordinary task exports.

## Durability, recovery and privacy

The existing per-answer task journal is the canonical first durable answer write.
Unexpected task exceptions reconcile already journaled answers into ordinary raw
exports. Full-mode journals remain in run folders; question-bearing compact journals
are retained under `logs/.task-response-checkpoints/`, with execution identity preventing
same-plan visits from sharing an answer journal.

`runtime/post_condition_responses.py` retains a small original context and stage
snapshot under `logs/post-condition-responses/`. It contains definitions and original
journal paths, not a second copy of participant answers. It survives completion and
cancellation, unlike temporary condition-recovery plans. Rebuilding reads these
snapshots and original journals, without consulting today's editable questions.
An unfinished final journal fragment preserves its valid prefix; malformed complete
records are reported for review.

Projection runs outside frame playback, after presentations and during orderly
abort/error finalization. It uses the project reporting lock and existing atomic CSV
writer. If Excel locks the CSV, the prior file remains intact and the durable answers
and context remain available. Close the CSV in Excel, then use Rebuild responses to
retry. A derived-view failure must not discard canonical answers or prevent ordinary
research export finalization.

Paths resolve beneath the active project and reject escaped or redirected CSV
targets. Changing the project display name does not move the file. Ordinary bundles
and clean Library preparation keep their positive content inventories; root response
CSVs and research logs are excluded. Legitimate stimulus CSVs remain eligible for
ordinary bundles. Raw answers do not enter application logs, generic summaries or
the authored project/config.

## Visible acceptance

In an approved visible session, open Conditions at 1120x820, then the modifier
dialog at its 1100x720 minimum and 1120x760 default. In both themes, add long
questions/answers in each phase, verify one blank question on add and no addition on
Edit, add and reorder multiple questions independently in each phase, assign shared
conditions, make a private copy, preview, cancel, reopen and apply. Check numbered
order after save/reopen and compilation, and response-tool visibility when Advanced
is collapsed/expanded.
The simple question editor uses a 1000x680 minimum and 1060x740 default; its
participant preview uses a 700x500 minimum and 760x560 default.
Check validation, empty/populated and rebuild busy/error states, full path tooltips,
and no unintended clipping. Run a short intended-machine presentation to confirm
selection can change before Continue and Escape preserves earlier answers.
Registered Qt coverage is maintained; normal local verification excludes Qt.
