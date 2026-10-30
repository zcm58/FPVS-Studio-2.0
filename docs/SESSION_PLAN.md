# SessionPlan Contract

`SessionPlan` is the compiled multi-condition session contract for FPVS Studio.
New ordinary FPVS sessions use schema `1.7.0` with independent randomization
provenance and pooled non-adjacent presentation ordering. Schema `1.6.0` retains
the preceding pooled-order-only contract. Historical `1.2.0` sessions remain readable; masking sessions use `1.3.0` with an
explicit authored task flow and variant-group ordering. See [Masking](MASKING.md)
for its `RunSpec`/project versions and first/last stream-group task scopes.
The original embedded `RunSpec` retains its
independent `1.1.0` timed-presentation contract. Editable `ProjectFile` uses schema
`1.3.0`. Schema `1.0.0`, `1.1.0`, and `1.2.0` projects are migrated in memory before
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
with no adjacent equal condition IDs. Counts are strict positive integers. If the
largest count `m` exceeds `N-m+1`, compilation rejects the configuration with guidance;
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

- ordinary FPVS sessions contain exact per-condition multiplicities in one pooled,
  non-adjacent order; per-condition occurrence indices are chronological within that order
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
  the whole condition with balanced seeded jitter and minimum-gap buffers
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

Editable explicit counts use Project 1.13/config 1.11; count defaults use the narrow
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
and `randomization_mode` add the other domains and one overall fixed/new reuse policy.
Legacy null settings resolve compatibly without rewriting the source project on load.
Explicit settings use Project 1.14/config 1.12 and require the complete validated triplet.

Ordinary SessionPlan 1.7 records `randomization_mode`, `randomization_seeds` and
`randomization_algorithm_version`. Each RunSpec 1.7 records its `randomization`
provenance. Derived stimulus, fixation-count and fixation-onset seeds use the domain
root, stable condition ID and one-based chronological presentation index. Participant,
visit, session/run ID and global order are excluded. Changing only condition order
preserves the corresponding condition-occurrence streams; randomized count constraints
that conflict with a seeded schedule are reported, not repaired by rerolling.

Fixed mode reuses configured roots across participants and rejects inconsistent supplied
snapshots. New mode resolves one fresh triplet per confirmed participant launch; preview
compilation uses configured values and performs no entropy generation. Pending retries
reuse their resolved snapshot. Concrete compiled schedules remain authoritative during
recovery. Native AB, specialized masking and pre/post-task randomness retain their prior
contracts and are outside these three controls.

## Saved condition arrangements

`SessionSettings.saved_condition_order` optionally retains an exact list of condition
IDs, including repeated presentations. In overall Fixed mode, core validates known
IDs, exact configured multiplicities and no adjacent duplicate conditions, then compiles
that list as SessionPlan 1.8 with `ordering_policy="saved_no_adjacent"`. RunSpec remains
single-condition with the existing independent seed provenance. Chronological within-
condition presentation indices are recomputed in the chosen global order, preserving
stimulus/fixation namespaces across moves.

New mode ignores a retained list and compiles seeded pooled ordering. A retained list
may become a stale authoring draft after condition/count edits; project validation and
compilation block an active invalid list without repairing it. Explicit order Save and
combined count/timing/order proposals validate atomically. `preview_condition_order`
uses a private copy, needs no assets/display and bounds work at 10,000 presentations.
A selected subset that removes needed separators is rejected rather than reshuffled.
Historical plans and exact-occurrence recovery retain their original order/provenance.

Saved-source fields use Project 1.15/config 1.13 and are omitted when absent. They are
project/session state, never condition-template defaults. Canonical ordering identity
includes an active exact list and ignores an inactive New-mode list.

## Simple post-question context

SessionPlan1.9 carries optional frozen `TaskModuleSpec.post_question_context` for
explicitly marked after-only questionnaires. It captures authored question versions,
original labels and chronological condition presentation identity before option shuffle.
Native or specialized sessions can carry this capability without independent-seed
metadata. Old unmarked tasks and compiled schemas retain their contracts. See
[Post-condition Questions](POST_CONDITION_QUESTIONS.md) for the canonical workflow.
