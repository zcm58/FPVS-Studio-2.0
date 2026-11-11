# SessionPlan Contract

`SessionPlan` is the compiled multi-condition session contract for FPVS Studio.
Explicit randomized-block FPVS sessions use schema `1.10.0`. Ordinary projects
without that opt-in retain schema `1.7.0` with independent randomization
provenance and pooled non-adjacent presentation ordering. Schema `1.6.0` retains
the preceding pooled-order-only contract. Historical `1.2.0` sessions remain readable; masking sessions use `1.3.0` with an
explicit authored task flow and variant-group ordering. See [Masking](MASKING.md)
for its `RunSpec`/project versions and first/last stream-group task scopes.
The original embedded `RunSpec` retains its
independent `1.1.0` timed-presentation contract. Legacy editable projects without
newer features retain ProjectFile schema `1.3.0`; explicit block designs use `1.17.0`. Schema `1.0.0`, `1.1.0`, and `1.2.0` projects are migrated in memory before
compilation and are not rewritten merely by loading or launching them. That one-time
project migration enables fixation color changes, accuracy scoring, and the participant
tutorial; once saved as `1.3.0`, later explicit user opt-outs remain authoritative.

It sits above `RunSpec`:

- `RunSpec` = one executable condition run
- `SessionPlan` = one ordered play-once session made of many `RunSpec` entries

This keeps single-run timing explicit and engine-neutral while letting runtime
own session flow and transition behavior. Core session compilation owns block
randomization so the planned order is deterministic for a given random order seed.

## Compile flow

```text
project.json -> ProjectFile
ProjectFile + refresh_hz + optional condition_ids -> compile_session_plan(...) -> SessionPlan
SessionPlan -> runtime preflight -> runtime session flow -> engine
```

When `condition_ids` is omitted, compilation includes every project condition. Passing
a subset limits the compiled pool, but does not change session semantics: every selected
condition still appears its configured total number of presentations, and its normal pre/post task
bindings, timing, validation, preflight, and execution/export contracts remain in
force. The GUI uses this input only for an accepted Experiment Test Mode launch; its
selector defaults to all conditions and is not persisted in `ProjectFile` or app
settings. No dedicated selector field is added to `RunSpec` or `SessionPlan`; the
resulting ordinary plan simply records the entries that were compiled. Production GUI
launches omit the subset and therefore include all conditions. The launch surface still
validates the full project before it offers the test-mode selector.

## Main models

### Compilation input preparation

`compiler_inputs.py` owns validation, presentation resolution, manifest presence/absence,
and stimulus pools for one compilation call. `compiler_tasks.py` similarly indexes task
definitions, checks contained task assets and streams each unique image hash once.
Linked memory tasks share one seeded realization per entry across pre/post phases.
These preparation objects never persist into a plan or survive to the next launch.

Every entry still receives independently realized schedules and mutable run/task models;
copying prepared presentation values prevents one run's edits from affecting another.
The public single-run compiler still performs validation. Preflight and later compilation
calls recheck inputs. Whole-plan seeded parity and bounded file-work regressions live in
`tests/unit/test_compiler_preparation.py`; use the compiler focused verification route.

### `InterConditionTransitionSpec`

Captures the session-level transition policy applied before each compiled run.
Current Studio-authored sessions are participant-gated:

- `manual_continue`

`continue_key` is populated with `space`. Legacy project fields may still contain
fixed-break values, but current compilation does not emit timed condition starts.

### `SessionEntry`

Represents one compiled occurrence of one condition inside the session:

- global session order index
- block index
- within-block index
- condition id and name
- deterministic `run_id`
- embedded single-condition `RunSpec`
- compiled `pre_tasks` and `post_tasks`
- whether the ordinary condition start gate remains visible
- optional one-based `condition_presentation_index` and `condition_presentation_count`

Each embedded `RunSpec` carries that condition's resolved timing template. A single
`SessionPlan` may mix continuous-image and 50% blank conditions without adding
session-level timing branches. It also carries the condition's fully resolved Base and
Oddball presentation rules and its pre-stream fixation frame count, so session runtime
does not inspect editable project presentation settings.

Task modules are project-owned, ordered declarative workflows. Conditions bind them
to pre- or post-condition phases with four occurrence scopes: every session
entry, the first occurrence of that condition, its last occurrence, or the first
entry of the entire compiled session. The latter is evaluated after ordering and
condition selection. Counting modules carry optional typed settings; compilation
generates their ordinary screens and links the load start/report realization. See
[Cognitive Load FPVS](COGNITIVE_LOAD_FPVS.md). Compilation
resolves each applicable binding into `TaskModuleSpec` and records deterministic item
and questionnaire-option order without changing the embedded `RunSpec`. Each
`TaskStep` also carries a closed Arial/Open Sans font-family choice into its
`TaskStepSpec`; omitted values default to Arial so existing projects retain their
rendering. This is an additive field in the existing schema `1.2.0` task/session
contract, not a schema bump or a change to the `RunSpec` frame contract.

Project-owned condition modifiers group those ordered bindings. Selected counting
assignments request one compatible baseline, injected into the first actual entry
without persisted baseline bindings on no-load conditions. Linked image-memory
modules share validated target identities and independently seeded task order.
Compiled provenance identifies the modifier and session baseline; neither operation
changes the existing FPVS or fixation RNG streams. Legacy standalone task bindings
retain their previous occurrence behavior. See [Condition modifiers](CONDITION_MODIFIERS.md).

Each module contains ordered task steps and may repeat as a group. This group repeat
keeps workflows such as Creatine's choice-grid then timed-feedback pair interleaved.
Steps may independently repeat when a single screen itself requires repetition.

### `SessionBlock`

Represents one randomized block in the session:

- `block_index`
- randomized `condition_order`
- compiled `entries`

Ordinary FPVS sessions resolve each optional `Condition.presentation_count` or inherit
`SessionSettings.block_count` as a total (never as another multiplier). Core pools
all occurrences into one compiled block and uses a deterministic constrained order
with no adjacent equal condition IDs when the selected pool has two or more conditions.
A pool containing one condition retains every requested presentation consecutively,
including when compilation selects only that condition from a larger project. Counts
are strict positive integers. For multi-condition pools, if the largest count `m`
exceeds `N-m+1`, compilation rejects the configuration with guidance;
no count, adjacency rule or stream duration is silently changed. `core/session_ordering.py`
owns count resolution, feasibility and bounded arrangement.

Native AB retains its existing `SessionSettings.randomize_across_blocks=True` path,
which repeats the selected condition pool `block_count` times and shuffles it into a
single compiled block. Specialized masking retains its grouped scheduling and rejects
unsupported authored presentation-count overrides. New AB burst studies use this mode: authored `block_count` is
**Bursts per SOA**, while the compiled plan's `block_count` is one. Each entry
is one five-second burst, and `global_order_index + 1` identifies its chronological
burst number. Saved sessions default this additive setting to false.

### `SessionPlan`

Top-level session fields:

- session id
- project id and project name
- random order seed
- refresh rate used during compilation
- block count
- transition spec
- compiled blocks
- total run count

## Randomization rules

The current v1 policy is:

- explicit randomized-block FPVS sessions present every eligible condition once per
  block; legacy ordinary sessions retain exact multiplicities in one pooled order.
  Both separate equal conditions for multi-condition selections, and condition
  occurrence indices remain chronological
- sessions opting into randomization across blocks shuffle the complete balanced
  repeated pool; this removes three-condition block boundaries from AB burst order
- current Studio GUI/runtime behavior does not honor legacy fixed-order settings
- session compilation stores the random order seed for reproducibility
- the same project + same seed + same refresh rate produces the same block
  order
- fixed fixation target-count mode uses the configured count for every run;
  randomized mode realizes one count per ordered run from the session seed while
  preserving no-immediate-repeat constraints when enabled
- each embedded `RunSpec` then distributes the realized fixation targets across
  the whole condition with balanced seeded jitter and minimum-gap buffers; an
  optional `FixationTaskSettings.target_onset_window` instead samples exactly one
  fixed target inside the inclusive window before that entry's stream offset.
  Each repetition is realized independently from its run seed. The window remains
  an authored setting; compiled entries retain concrete frame events. See the
  [FixationEvent contract](RUNSPEC.md#fixationevent) for validation and edge buffers.
- task option randomization uses a task-specific deterministic seed namespace and
  records stable item/option ids in the compiled task spec
- AB recall answer keys are resolved from the actual T1/T2 events for each entry;
  the built-in recall task requires one unique identity per target phase and the
  declared number of presentations. Explicit repeated-target bursts reuse that
  pair; default bursts present it once.

## Runtime responsibilities

Runtime consumes `SessionPlan` and:

- preflights all referenced image paths for project-relative existence before launch
- validates display timing across every embedded `RunSpec`
- opens one engine session/window for the whole plan
- runs the participant fixation tutorial once before the first condition when compiled
  fixation accuracy and tutorial settings are enabled
- normally shows a Space-required start screen before a condition run, using generic
  headings such as `Condition 1 of 4`; a pre-task binding may explicitly replace this
  gate when the authored workflow already contains its own reminder/acknowledgement
- every AB recall entry requires Space before its burst, including entries with
  pre-task bindings that would ordinarily replace the start gate; the prompt is
  "Press space when you're ready to continue."
- new AB recall tasks ask for typed answers on two separate screens, each submitted
  with Enter or Next; there are no extra pauses after each three-condition group
- iterates `SessionEntry.run_spec` in order
- executes compiled pre-tasks before the optional condition start gate and post-tasks
  immediately after the timed stream, before fixation feedback or block/session
  transitions
- lets the engine render the compiled fixation-only lead-in after the Space gate and
  before stream frame zero; the condition trigger and first stimulus remain aligned on
  frame zero
- aggregates run execution results into a `SessionExecutionSummary`

Engines still consume one `RunSpec` at a time.

Task clocks and responses stay outside the stream frame clock. A task cannot schedule
an FPVS trigger, fixation target, or stimulus event. The engine renders one neutral
compiled task step and returns neutral participant input. Runtime preserves the
compiled step font on `ResolvedTaskStep` while owning repetition, validation, retries,
bounded forward branching, aborts, and incremental response checkpointing.

## Relationship to execution results

`SessionPlan` is the compiled plan.

`SessionExecutionSummary` in `core.execution` is the realized execution result.
It stores:

- random order seed
- realized block order
- runtime metadata
- ordered run results
- abort/completion state
- warnings
- per-run task response records and task-flow completion/abort metadata

That split keeps planning and execution artifacts distinct.

The session exports should preserve:

- the stored random order seed
- the planned block order for each block
- the ordered `run_results` matching `SessionPlan.ordered_entries()`

### Presentation-count compatibility and recovery

Editable explicit counts use Project 1.13; historical configs introduced them in
1.11. Current configs share the [revision-2 envelope](PROJECT_CONFIG.md).
Count defaults use the narrow
template-library 1.4 schema. Omitted counts preserve saved global totals without
rewriting source projects merely on load. Fresh ordinary compilation applies the new
ordering rule even to inherited totals. Historical compiled plans retain their stored
order. Exact-occurrence recovery keeps the original condition presentation index/count
(e.g. presentation 3 of 3), even when its retry plan contains only that entry.
Task-module repetition indices remain separate from condition presentations.

## Independent randomization

`core/randomization.py` resolves a frozen `RandomizationSeeds` snapshot with
condition-order, stimulus-order and fixation roots. `SessionSettings.session_seed`
remains the configured condition-order seed; optional `stimulus_seed`, `fixation_seed`
and `randomization_mode` add the other roots and the historical overall fixed/new policy.
Optional `randomization_modes` records independent `condition_order`, `stimulus` and
`fixation` choices. Absent category choices inherit the overall mode. The overall mode
is fixed only when all categories are fixed; otherwise it is new.
Legacy null settings resolve compatibly without rewriting the source project on load.
Explicit settings use Project 1.14 and require the complete validated triplet.
Historical configs added them in 1.12; current configs retain them in revision 2.

Ordinary SessionPlan 1.7 records `randomization_mode`, `randomization_seeds` and
`randomization_algorithm_version`, plus optional `randomization_modes`. Each RunSpec 1.7
records matching optional `randomization.modes` alongside its `randomization`
provenance. Derived stimulus, fixation-count and fixation-onset seeds use the domain
root, stable condition ID and one-based chronological presentation index. Participant,
visit, session/run ID and global order are excluded. Changing only condition order
preserves the corresponding condition-occurrence streams; randomized count constraints
that conflict with a seeded schedule are reported, not repaired by rerolling.

Fixed mode reuses configured roots across participants and rejects inconsistent supplied
snapshots for each fixed category. A confirmed participant launch resolves fresh roots
only for new categories and preserves configured roots for fixed categories; preview
compilation uses configured values and performs no entropy generation. Pending retries
reuse their resolved snapshot. Concrete compiled schedules remain authoritative during
recovery. Native AB, specialized masking and pre/post-task randomness retain their prior
contracts and are outside these three controls.

## Explicit randomized condition blocks

`SessionSettings.condition_ordering="randomized_blocks"` selects the explicit block
experiment design in Project `1.17.0`. Historical configs introduced it in `1.15.0`;
current configs retain it in the shared revision-2 format. Absence preserves the legacy
pooled design and is omitted during serialization. Existing `block_count` remains the
fallback total for conditions without an authored `presentation_count`; it is never
multiplied into explicit totals. Native AB rejects this ordinary-FPVS setting. Masking
retains its specialized grouping: an existing ordinary block setting remains dormant
after a masking modifier is assigned, survives interchange, and becomes applicable
again only to an ordinary selection. Existing saved ordinary arrangements and explicit
independent-randomization controls retain their masking restrictions.

Block k contains each selected condition whose presentation total is at least k,
exactly once. Unequal totals therefore produce smaller later blocks. Compilation
records real `SessionBlock`s and occurrence indices; a new condition-order seed changes
the block permutations, while Pseudorandom reuses the configured seed. Global
no-adjacent ordering also applies at block boundaries. With multiple conditions, totals
must satisfy `largest <= second-largest + 1`; two or more trailing singleton blocks
would otherwise repeat the same condition. A single-condition project keeps all
requested presentations. Feasibility errors require an explicit count correction.

Automatic block order uses policy `randomized_blocks`; an active saved arrangement
uses `saved_randomized_blocks` and must obey both the same block membership and
no-adjacent rules. Both compile as SessionPlan `1.10.0`, including plans carrying
simple post-question context, and execute as result schema `1.5.0`. Config completed
snapshots retain actual policy and block orders separately from current editable
settings. Clearing a saved arrangement keeps the explicit block design. The atomic
`propose_condition_timing`/document binding can opt into the design alongside pending
count edits and a saved order. Fingerprints distinguish this design from the legacy
pool even when one generated flattened order happens to match.

Per-condition/presentation stimulus, fixation count and fixation-onset seed namespaces
are unchanged (randomization algorithm version 1). Reordering block positions therefore
does not reroll corresponding occurrences. Exact recovery copies an original RunSpec
and its original presentation index into a one-entry retry plan; generic contract and
runtime validation permit that partial plan instead of demanding complete original
blocks. Runtime does not add block-break screens for these ordinary block policies;
existing participant condition gates and tasks remain authoritative.

Registered safe coverage is in `tests/unit/test_block_ordering_contracts.py` for project
and config roundtrips, legacy omission, fingerprints, atomic design edits, completed
snapshots, exact recovery, runtime result/export policies and full/compact execution
without extra break screens.

## Saved condition arrangements

`SessionSettings.saved_condition_order` optionally retains an exact list of condition
IDs, including repeated presentations. When condition order is fixed, core validates known
IDs, exact configured multiplicities and no adjacent duplicate conditions in pools with
two or more conditions. For the legacy pooled design, that list compiles as SessionPlan
1.8 with `ordering_policy="saved_no_adjacent"`; explicit block designs instead use
SessionPlan 1.10 with `saved_randomized_blocks`, as described above. RunSpec remains
single-condition with the existing independent seed provenance. Chronological within-
condition presentation indices are recomputed in the chosen global order, preserving
stimulus/fixation namespaces across moves.

New condition-order mode ignores a retained list and compiles the explicitly selected
block design or legacy pooled ordering.
A retained list may become a stale authoring draft after condition/count edits; project validation and
compilation block an active invalid list without repairing it. Explicit order Save and
combined count/timing/order proposals validate atomically. Saving an arrangement fixes
condition order while preserving the stimulus and fixation reuse choices.
`preview_condition_order` uses a private copy, needs no assets/display and bounds work
at 10,000 presentations.
A selected subset with two or more conditions that removes needed separators is
rejected rather than reshuffled. A single-condition subset retains every occurrence.
Historical plans and exact-occurrence recovery retain their original order/provenance.

Saved-source fields use Project 1.15 and are omitted when absent. Historical configs
introduced them in 1.13; current configs retain them in revision 2. They are
project/session state, never condition-template defaults. Canonical ordering identity
includes an active exact list and ignores an inactive New-mode list.

## Simple post-question context

SessionPlan1.9 carries optional frozen `TaskModuleSpec.post_question_context` for
explicitly marked after-only questionnaires. It captures authored question versions,
original labels and chronological condition presentation identity before option shuffle.
Native or specialized sessions can carry this capability without independent-seed
metadata. Old unmarked tasks and compiled schemas retain their contracts. See
[Post-condition Questions](POST_CONDITION_QUESTIONS.md) for the canonical workflow.
