# SessionPlan Contract

`SessionPlan` is the compiled multi-condition session contract for FPVS Studio.
Its current persisted contract is schema `1.2.0`; each embedded `RunSpec` retains its
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
condition still appears once per configured block, and its normal pre/post task
bindings, timing, validation, preflight, and execution/export contracts remain in
force. The GUI uses this input only for an accepted Experiment Test Mode launch; its
selector defaults to all conditions and is not persisted in `ProjectFile` or app
settings. No dedicated selector field is added to `RunSpec` or `SessionPlan`; the
resulting ordinary plan simply records the entries that were compiled. Production GUI
launches omit the subset and therefore include all conditions. The launch surface still
validates the full project before it offers the test-mode selector.

## Main models

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

Each embedded `RunSpec` carries that condition's resolved timing template. A single
`SessionPlan` may mix continuous-image and 50% blank conditions without adding
session-level timing branches. It also carries the condition's fully resolved Base and
Oddball presentation rules and its pre-stream fixation frame count, so session runtime
does not inspect editable project presentation settings.

Task modules are project-owned, ordered declarative workflows. Conditions bind them
to pre- or post-condition phases with one of three occurrence scopes: every session
entry, the first occurrence of that condition, or its last occurrence. Compilation
resolves each applicable binding into `TaskModuleSpec` and records deterministic item
and questionnaire-option order without changing the embedded `RunSpec`. Each
`TaskStep` also carries a closed Arial/Open Sans font-family choice into its
`TaskStepSpec`; omitted values default to Arial so existing projects retain their
rendering. This is an additive field in the existing schema `1.2.0` task/session
contract, not a schema bump or a change to the `RunSpec` frame contract.

Each module contains ordered task steps and may repeat as a group. This group repeat
keeps workflows such as Creatine's choice-grid then timed-feedback pair interleaved.
Steps may independently repeat when a single screen itself requires repetition.

### `SessionBlock`

Represents one randomized block in the session:

- `block_index`
- randomized `condition_order`
- compiled `entries`

Each block contains each selected condition exactly once.

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

- all selected conditions appear exactly once per block
- each block gets its own randomized order
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
