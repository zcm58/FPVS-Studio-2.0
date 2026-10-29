# Per-Condition Presentation Counts and Shuffled Ordering

Status: Planned

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`. Implementation has not
started. Make the number of complete presentations independently editable for each
FPVS image or word condition in Timing & Session, beside its frequency and duration.

A 60-second condition with a presentation count of 3 means **three separate
60-second presentations**, each using the normal instructions/tasks/transition flow.
It does not mean one uninterrupted 180-second stream. Use labels that make total
presentations clear rather than implying additional repeats after an initial run.

Pool all requested presentations and shuffle the whole session. Do not force balanced
rounds or require every condition to have the same count. Prevent adjacent presentations
of the same condition. Report impossible configurations instead of relaxing that rule,
changing counts or retrying indefinitely.

Image order and fixation timing vary between a condition's repeats, while the
corresponding repeat matches across participants in fixed-seed mode. The
[randomization plan](reproducible-randomization-controls.md) owns those schedules.

## Current evidence and ownership

- `SessionSettings.block_count` currently supplies one global count for every
  selected condition; Timing & Session labels it `Repeats per condition`.
- `core/compiler.py` builds blockwise runs or a repeated pooled session depending
  on `randomize_across_blocks`. Ordinary block shuffling is currently unconditional.
- `Condition.sequence_count` is a multiplier inside a single continuous RunSpec,
  not a separate-presentation count. It must not be reused with a different meaning.
- Task bindings already track per-condition occurrence indices/counts, including
  first-only and last-only behavior; compiler/session/runtime own those semantics.
- `gui/session_structure_page.py`, `gui/runtime_settings_page.py`,
  `gui/setup_wizard_page.py` and `core/session_plan.py` own the affected UI/contracts.

## Implementation sequence

1. Introduce a compatible, explicit per-condition presentation count. Preserve old
   projects' authored counts and legacy continuous stream durations. Avoid multiplying
   new per-condition counts by the former global block count a second time.
   Counts remain positive integers; do not reinterpret zero or fractional values as
   condition exclusion or partial presentations.
2. Build the pool from the exact requested condition multiplicities. Preserve stable
   condition identity and assign chronological occurrence indices per condition.
3. Validate no-adjacent-repeat feasibility before participant flow or output creation.
   For counts with maximum `m` and total `N`, require `m <= N - m + 1` when repeated
   conditions must be separated. A single condition requested more than once is
   impossible under this rule and needs an actionable explanation.
4. Implement a deterministic seeded arrangement respecting exact counts and adjacency
   without unbounded rejection sampling. Do not promise a different order for every
   seed when the constraints leave only one valid arrangement.
5. Reuse existing session execution, start gates, transitions, scoring and task binding
   occurrence policies. Each separate presentation produces its normal run records.
6. Replace/reconcile the old global-repeat UI in the shared timing table and show
   per-condition totals plus total session presentations/stimulation time. Preserve
   readable historical compiled plans and define legacy ordering migration explicitly.

## Acceptance and verification

- A=3 and B=2 produces exactly five runs without adjacent equal conditions. Under
  this constraint A-B-A-B-A is the only possible condition-label order.
- A=3 and B=1 is rejected with guidance to reduce A or add other presentations.
  No fallback inserts a break, drops a run or permits adjacent duplicates.
- Duration is per presentation: 3 x 60 seconds yields 180 seconds of stimulation
  across three separate run entries, with normal per-entry flow.
- First-only/last-only task bindings remain correct with unequal counts. Cancellation,
  interruption/recovery, exports and participant histories retain occurrence identity.
- Fixed condition-order seed reproduces the constrained order; fresh mode can generate
  a new valid order while preserving counts. Existing scientific scheduling guards stay.
- Cover persistence/config/bundle migration, compiler/run totals and runtime fake-engine
  flow. Add registered GUI cases at `1120x820` in both themes.
- Run core/compiler/runtime/gui/project-I/O focused routes and repo precommit; retain
  existing opt-in rules for visible Qt and hardware tests.

## Scope limits

This is complete-condition repetition, not repeats per image, continuous sequence
count, repeat participant visits or task-module repetition. Native AB burst counts are
outside this feature and keep their existing contracts. Specialized masking/catch
grouping must retain its scientific rules; report incompatible overrides rather than
silently changing those rules.
