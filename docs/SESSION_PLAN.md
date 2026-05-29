# SessionPlan Contract

`SessionPlan` is the compiled multi-condition session contract for FPVS Studio.

It sits above `RunSpec`:

- `RunSpec` = one executable condition run
- `SessionPlan` = one ordered play-once session made of many `RunSpec` entries

This keeps single-run timing explicit and engine-neutral while letting runtime
own session flow and transition behavior. Core session compilation owns block
randomization so the planned order is deterministic for a given random order seed.

## Compile flow

```text
project.json -> ProjectFile
ProjectFile + refresh_hz -> compile_session_plan(...) -> SessionPlan
SessionPlan -> runtime preflight -> runtime session flow -> engine
```

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

Each embedded `RunSpec` carries that condition's resolved timing template. A single
`SessionPlan` may mix continuous-image and 50% blank conditions without adding
session-level timing branches.

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

## Runtime responsibilities

Runtime consumes `SessionPlan` and:

- preflights all referenced assets before launch
- validates display timing across every embedded `RunSpec`
- opens one engine session/window for the whole plan
- runs the participant fixation tutorial once before the first condition when compiled
  fixation accuracy and tutorial settings are enabled
- shows a Space-required start screen before every condition run, using generic
  headings such as `Condition 1 of 4` when the embedded `RunSpec` disables
  participant-facing condition titles
- iterates `SessionEntry.run_spec` in order
- aggregates run execution results into a `SessionExecutionSummary`

Engines still consume one `RunSpec` at a time.

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

That split keeps planning and execution artifacts distinct.

The session exports should preserve:

- the stored random order seed
- the planned block order for each block
- the ordered `run_results` matching `SessionPlan.ordered_entries()`
