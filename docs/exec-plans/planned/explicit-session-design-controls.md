# Explicit Session Design Controls

Status: Planned

The user endorsed this direction as future work on 2026-09-05. Implementation has
not started. This plan does not expand the current active Setup UX refinement;
move it to `active/` when implementation is selected and resolve the decisions below.

## Problem And Proposed Alternative

Researchers can change project-wide base frequency and oddball cadence, but guided
Setup does not directly expose each condition's acquisition length. Repetitions are
presented through a single session-wide value, and every block uses randomized order.
This makes it awkward to express unequal exposure lengths, fixed sequences, or
participant groups with deliberately balanced condition order.

Add a Session design table with condition, acquisition duration, condition-run count,
and order information. Support explicit random, fixed, and counterbalanced policies.
Show requested and realized duration, the number of whole oddball cycles, and a
read-only order preview for the selected participant assignment. Keep the actual
compiled plan as the source of the preview and the eventual execution order.

Direct controls make the study design inspectable before launch. Explicit policies
support a wider range of image and word oddball studies without requiring template
workarounds. These are expected usability benefits, to be checked in visible review;
the interface must not claim that one counterbalancing method suits every study.

## Current Evidence

Evidence was inspected on 2026-09-05; symbols remain the reference if line numbers move.

- [`Condition`](../../../src/fpvs_studio/core/models.py), lines 684–685, already owns
  `sequence_count` and `oddball_cycle_repeats_per_sequence`. These multiply into one
  continuous compiled condition; they are distinct from repeated condition runs.
- [`compile_run_spec`](../../../src/fpvs_studio/core/compiler.py), lines 95–103,
  reads the project protocol and derives total cycles, stimuli, and frames. Duration
  support already exists; a GUI control should use that owner.
- [`ConditionSetupStep`](../../../src/fpvs_studio/gui/condition_setup_step.py),
  form construction near line 524, exposes identity, appearance, tasks, mode, and
  instructions. Cycle controls exist in the compatibility
  [`ConditionsPage`](../../../src/fpvs_studio/gui/condition_pages.py), lines 151–161,
  and the [template editor](../../../src/fpvs_studio/gui/condition_template_profile_editor_dialog.py),
  lines 95–96, rather than the guided condition form.
- [`SessionStructureEditor`](../../../src/fpvs_studio/gui/session_structure_page.py),
  lines 135–138 and 209–215, exposes uniform repeats and writes automatic randomization.
  [`compile_session_plan`](../../../src/fpvs_studio/core/compiler.py), line 333,
  unconditionally shuffles each block. The retained `randomize_conditions_per_block`
  model field does not establish an implemented fixed-order option.
- [`SessionPlan`](../../../src/fpvs_studio/core/session_plan.py) already records ordered
  blocks, entries, and seeds. The [run page](../../../src/fpvs_studio/gui/run_page.py),
  lines 977–993, can display compiled order. Reuse these contracts and presentation seams.

## Decisions Required Before Coding

1. Define acquisition duration as stimulus-stream time, clearly separating pre-stream
   fixation, pre/post tasks, manual gates, and breaks. Decide whether seconds or whole
   oddball cycles are the authored value, and how requested seconds round to complete
   cycles. Retain exact requested/realized values without competing persisted truth.
2. Define condition-run count versus the existing within-stream cycle multiplier and
   session block count. Specify whether unequal run counts form partial blocks or an
   explicit entry list, and how task occurrence rules apply to that representation.
3. Select the supported counterbalance algorithm and its validity conditions, including
   odd/even condition counts, unequal repeats, and multiple blocks. Specify the actual
   generated sequences; do not use “counterbalanced” as an unspecified promise.
4. Decide how participant/session identity maps to an assignment, where assignments
   persist, and how aborted launches, retries, revisits, and simultaneous launches
   affect assignment consumption. Preview must not consume an assignment or seed.
5. Define fixed-order editing, randomization scope, and whether constraints such as no
   repeated condition across a block boundary are offered. Reject impossible requested
   designs explicitly instead of silently switching order policy.
6. Agree on schema versions, config/bundle compatibility, export provenance, and RNG
   behavior. Legacy projects with the same explicit seed must preserve their current
   order, run seeds, stimulus schedules, and realized fixation targets.

## Ownership And Preservation

- Core models own persisted design settings and neutral assignment identifiers.
  Core compilation owns ordered `SessionPlan` entries and frame-based `RunSpec` timing.
  Resolve duration using the existing frame/timing and fixation-feasibility services.
- Runtime owns participant/session assignment coordination, launch lifecycle, ordered
  execution, and core-owned execution results. Exporters serialize the selected policy,
  assignment, effective order, duration, and seed provenance from those results.
- GUI edits models, explains effective values, and displays backend-generated previews.
  It must not implement its own ordering algorithm or perform compilation on the UI
  thread. Engines continue rendering one compiled run and existing transition screens.
- Preserve image/word schedules, presentation-mode restrictions, trigger semantics,
  display verification, task occurrence semantics, fixation realization/scoring,
  explicit saving, and existing project paths. Keep legacy randomization available.
- Save session designs through the existing canonical config/bundle services; do not
  introduce a second serialization or scheduling implementation. A separate full-study
  template feature is not a prerequisite or part of these five accepted plans.

## Implementation Phases

### 1. Specify contracts and preserve the baseline

Record the decisions above with examples for equal repeats, unequal repeats, one
condition, and counterbalanced groups. Capture deterministic legacy compile fixtures
before changes. Design additive defaults/migrations and document what older config or
project versions can represent. Specify whether older exporters reject unsupported
designs or emit a versioned representation; never silently discard design settings.

### 2. Add duration authoring through existing timing owners

Provide core conversion/validation for requested duration and complete oddball cycles.
Expose realized seconds and frames, including approximate refresh/base ratios and
blank-50 parity restrictions. Keep fixation feasibility and stimulus-repeat guidance
connected to the resulting duration. Add the Session table with clear run-count labels
and explicit reset-to-default behavior; preserve per-condition overrides on unrelated edits.

### 3. Compile order policies and coordinate assignments

Implement fixed and selected counterbalanced policies through session compilation.
Preserve the legacy random code path and RNG consumption for migrated projects.
Implement runtime assignment persistence using the agreed lifecycle rules, and return
assignment/provenance in neutral contracts. Ensure preview and launch consume the same
resolved design; invalidate stale previews when settings or assignments change.

### 4. Integrate preview, interchange, exports, and Review

Show block/run order, assignment, effective acquisition time, and known added timed
segments; identify manual waits as variable. Include an explicit policy summary in
Review and launch preparation. Extend config/bundle round trips and execution exports
through their canonical owners. Document the workflow and migrate the plan to completed
only after its implementation and acceptance criteria have been met.

## Verification And Acceptance

- Core tests cover requested/realized duration, whole-cycle boundaries, supported
  refresh rates/modes, unequal lengths, and fixation infeasibility without timing drift.
- Deterministic session tests cover every supported ordering policy, assignment balance,
  invalid designs, equal/unequal repeats, and task occurrence behavior. Legacy fixtures
  assert unchanged order, run seeds, stimulus events, and fixation events for fixed seeds.
- Persistence/runtime tests cover old-project migration, config/bundle round trips,
  saved/reopened designs, assignment retries/aborts/concurrency, stale preview rejection,
  and exports sufficient to reconstruct the executed design.
- Register GUI tests for table edits, selection, alternate policies, long names, readable
  errors, keyboard access, and no clipping at `1120x720`. Use shared components and
  deterministic controller/runtime stubs; do not launch PsychoPy from GUI tests.
- Run the relevant focused verification scopes and repo precommit when implemented.
  Qt tests remain excluded by default: use an explicitly approved safe visible Windows
  session for Qt and manual acceptance, never local offscreen execution.

## Out Of Scope

Per-condition base frequency or oddball cadence requires a separately approved scope;
this plan retains the project-wide protocol. Adaptive/random oddball placement,
changes to fixation scoring, new trigger backends, and engine-level scheduling changes
are also excluded. Planning creates no new behavior and does not change current studies.
