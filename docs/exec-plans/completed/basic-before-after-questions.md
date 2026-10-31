# Simple before and after condition questions

Status: Completed

Date: 2026-10-31

## User workflow and acceptance

In Setup > Conditions, select a condition and open FPVS Condition Modifiers.
The primary actions add a question before or after that condition. The simple
question editor starts with a blank Yes/No question, shows when and where it runs,
and supports additional questions and existing response types. Each phase has its
own ordered question list: Add Question appends another question, and Up/Down moves
the selected question. Saving and compilation must preserve both independent orders.
Added questions remain editable from the condition's list. Counting, Memory, Masking, presets and
custom task details belong under Advanced modifiers.

The author can add, edit, preview, remove, cancel and apply either phase without
using the advanced module editor. Assignments default to the selected condition;
shared assignments remain explicit and private edits preserve other conditions.
Existing activities, task ordering, authored metadata and saved projects remain intact.

## Implementation boundaries

- Reuse the existing simple question dialog and questionnaire editor for both phases.
  Use ordinary unmarked pre-condition task modules; preserve the existing marked
  after-question and readable CSV contracts. Add no serialized field or schema version.
- Accept only compatible single-screen, self-paced pre questionnaires in the basic
  editor. Complex, typed, modifier-owned and specially scoped tasks remain Advanced.
  Do not flatten or silently convert imported tasks.
- Insert new before questions ahead of protected counting/memory start screens;
  preserve unrelated binding order and metadata. Keep after questions' current order.
- Keep all edits in the detached modifier draft until Apply. Preserve compiler,
  runtime, engine, exports and presentation ownership.
- Use existing components and dimensions: modifier dialog minimum `1100x720`, default
  `1120x760`; question dialog minimum `1000x680`, default `1060x740`; Setup `1120x820`.
  Fit long condition names and before/after states in both themes without clipping.

## Verification

- Baseline GUI-focused route and focused question/modifier unit tests.
- Core tests for before/after placement, protected ordering, shared/private edits,
  removal, metadata preservation and serialization/compilation with existing tasks.
- Registered GUI tests for direct basic actions, one blank question on add, editing,
  phase/scope visibility, cancel/apply/save, Advanced-only activity creation and layout.
- Run focused GUI/core/docs checks and appropriate precommit checks. Visible Qt
  verification uses the user's existing approval and isolated test profiles; no
  offscreen Qt, real presentation or hardware output.
- Record any broad-suite limitation separately from targeted results. The previous
  unrelated broad-suite failures and retirement stress timeout remain unclassified.

## Evidence

- Basic Add opens a blank Yes/No question in the selected phase. Repeated Add and
  the numbered list's Up/Down controls support independent before/after orders.
  Three questions in each phase were reordered through real GUI buttons, applied,
  saved/reopened and compiled with exact identities and order preserved.
- Registered visible Qt coverage: 209 distinct tests passed across the basic
  question, modifier, masking and detailed task-editor modules. Layout coverage
  includes both themes and documented minimum/default sizes, long text, all response
  types, shared/private assignments, cancel/apply, busy/error and Advanced states.
- Native visual smoke used a synthetic project in an isolated profile at modifier
  `1100x720` and question `1000x680`, Windows scaling 100%, in both themes. Three
  before and three after questions were reordered and inspected. Add Question fits
  its full-width row; technical response maintenance stays hidden until Advanced.
  Cancel left the source unchanged. No real presentation or hardware output ran.
- Core/compiler/export/lifecycle checks passed 151 tests with one existing Windows
  symlink-privilege skip; the later independent ordering/roundtrip test passed with
  the complete 45-case question unit module. Project formats and after-only readable
  CSV contracts remain unchanged.
- An existing detailed-editor Add Text/Image defect was reproduced by two new GUI
  cases: incomplete option rows emitted changes before their alignment controls
  existed. Blocking notifications during each row's construction changed both cases
  from failing to passing, retained the final notification, and restored all 27
  detailed-editor tests. No missing-widget fallback was introduced.
- Clean-checkout non-Qt precommit passed: 4,390 tests, 24 subtests and 13 Windows
  symlink-privilege skips. Ruff, compilation, mypy, GC and harness/docs checks passed.
  The unchanged 1,500-session retirement stress test was explicitly deselected after
  the prior run's 600-second timeout; it is not claimed verified by this task.
- Later changes were limited to GUI recovery/layout, ordering coverage and docs;
  final focused and static checks cover the resulting source. Local screenshots,
  test logs and QA snapshots remain under ignored task-owned `build/` directories.
