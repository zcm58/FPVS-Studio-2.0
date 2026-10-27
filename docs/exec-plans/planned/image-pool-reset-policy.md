# Optional Image Pool Reset Policy

Status: Planned

Date: 2026-10-03

## User Decision And Scope

The user selected the existing behavior: reset image pools at the start of each
condition run. This remains the default for current studies. The user requested a
future execution plan for an optional carryover policy with visible explanations of
both approaches; implementation has not been requested. Move this plan to `active/`
when implementation is selected.

Initial scope is ordinary FPVS Oddball image conditions. Both policies sample the
Base and Oddball pools separately without replacement until their respective pool
is exhausted, then reshuffle that pool. The choice controls whether an unfinished
pool survives a boundary between repeated runs of the same condition.

## Current Evidence

- [Scheduling](../../../src/fpvs_studio/core/compiler_schedules.py),
  `build_stimulus_sequence`, owns separate seeded Base/Oddball bags. Refills happen
  only when empty; repeat repairs preserve membership of each role's pool cycle.
- [Compilation](../../../src/fpvs_studio/core/compiler.py), `compile_session_plan`,
  assigns each condition occurrence a run seed and creates fresh bags. Within-run
  `sequence_count` multiplies the continuous stream length; it is not a pool reset.
- The [RunSpec contract](../../RUNSPEC.md) owns current selection semantics.
  Runtime/engines play compiled events without making new random image selections.
- October 3 investigation: 100 seeds with 730 presentations, seven Base images and
  three Oddball images, preserved every complete pool, unique partial pools, and
  per-role counts differing by at most one. Compiler focused verification passed
  451 tests. This verifies the existing within-run behavior, not the proposed option.

## Proposed User Experience

Add an **Image pool reset** choice to the existing condition image-selection or
presentation controls. Use the current behavior by default, with concise persistent
help beside the choice and fuller accessible help for the tradeoffs. The final
placement must fit the existing Setup layout; do not introduce a new mandatory step.
Show the effective choice in Review so researchers can check it before launch.

Proposed labels and user-facing explanations:

| Choice | How it works | Advantages | Tradeoffs |
| --- | --- | --- | --- |
| **Reset each condition run (default)** | Start each run with fresh shuffled Base and Oddball pools. | Every image is eligible when a run starts; runs are easier to use independently. | Images can reappear in a later run before unused images from the previous run have been shown. Session-wide exposure counts can differ. |
| **Continue across repeated runs** | Resume each unfinished pool when the same condition runs again; reshuffle only after all its images have been used. | More even exposure across the session; every image gets a turn before reuse within its role and condition. | Later runs depend on earlier selections and can contain different subsets of images. |

Include a small example: with 100 images and 20 presentations per run, five completed
runs under carryover use every image exactly once. Resetting each run can repeat some
images and omit others. Explain that this example applies independently to each role;
Base and Oddball presentation counts differ according to the authored cadence.

Do not label either approach scientifically superior. Both use seeded sampling;
carryover improves exposure balance, while reset preserves independent run starts.
Equal exposure over a complete pool is not an identical probability for every image
on every draw: used images are ineligible, and repeat-avoidance constraints also apply.
Describe counts as planned exposure until actual playback evidence establishes display.

## Policy And Compatibility Requirements

- Represent the choice as a typed, per-condition authored policy. Missing values and
  newly created conditions default to reset. Confirm field placement, schema versions,
  and minimum supported Studio version before implementation.
- Keep separate carryover state for each condition, role, and resolved image inventory/
  variant. Sharing a source set across conditions must not consume another condition's
  pool. A pool waits while other conditions run and resumes at its next occurrence.
- Reset all state at the start of a newly compiled session; no carryover across
  participants, visits, new sessions, or application restarts. Previews must not consume
  persistent pool state. Selecting different session entries produces a newly compiled
  plan, rather than borrowing state from an earlier preview or launch.
- With reset selected, preserve existing seeded image order, condition order, run seeds,
  fixation realization, task behavior, frame timing and trigger schedules exactly.
  In carryover mode, use isolated deterministic random streams so image selection does
  not perturb condition ordering, fixation, tasks, or unrelated conditions.
- Preserve settings in save/reopen, supported templates/configs, and Library/bundle
  round trips. Older clients must reject unsupported policy-bearing schemas instead
  of silently interpreting carryover as reset. Export sufficient policy/seed provenance
  to interpret the compiled and executed design through existing core-owned contracts.
- Preserve existing image identity (resolved project-relative path). Identical pixels
  in separate files remain separate entries; do not silently deduplicate research data.
  Define duplicate references to the same canonical path explicitly: preserve authored
  multiplicity or reject malformed inventories, rather than silently deduplicating them.
- Preserve the current on-screen adjacency rule. Prohibiting the same Oddball at the
  end of one pool and the start of the next, despite intervening Base images, is a
  separate feature and is not implied by this option. Singleton pools necessarily repeat.
  Repeat repair may reorder eligible entries, but must never discard leftovers or
  rebuild an unfinished pool to avoid a boundary repeat.
- Resolve abort, skip and retry semantics before implementation. A compiled selection
  is not proof that an image appeared. Define whether a resumed workflow reuses its
  saved plan or starts a new session; never claim actual exposure balance for incomplete
  runs or introduce runtime resampling to compensate for missed/aborted presentations.

## Ownership And Implementation Steps

1. Finalize the authored field, applicable condition types, UI placement, interchange
   compatibility, and interrupted-session semantics. Capture fixed-seed legacy fixtures.
2. Extend the existing core scheduler and session compiler with compilation-local pool
   state for the optional policy. Keep standalone run compilation meaningful and
   deterministic, and retain `RunSpec` as a single-condition contract. Reuse existing
   shuffled-bag and path-resolution owners instead of adding a second sampler.
3. Add the explicit GUI choice, inline pros/cons, accessible example, and Review summary
   using shared components. Unsupported condition types must not offer a control that
   has no effect. Compile previews in workers through existing GUI-neutral services.
4. Complete persistence/provenance and verification, then update `ARCHITECTURE.md`,
   the agent index, and the canonical RunSpec/SessionPlan/GUI workflow contracts.
   Archive this plan only after the option and its acceptance checks are complete.

Runtime continues to execute the compiled session; engines only render its events.
Any state needed for a supported resume workflow belongs to existing runtime/session
contracts, not global compiler variables or widget-owned lists. Preserve the Library
compilation limits and cancellation behavior for both policies.

## Verification And Acceptance

- Default/migrated reset projects retain exact fixed-seed schedules. Test the difference
  between continuous within-run repetitions and separate condition runs.
- For carryover, concatenate each condition's per-role selections across completed runs:
  every complete pool must contain each authored entry once, and a final partial pool
  must not reuse an authored entry. Compare authored multiplicities when paths repeat;
  this does not promise unique pixels. Cover uneven pool sizes, runs shorter/longer than a
  pool, singleton pools, overlapping roles, variants, and interleaved conditions.
- Verify deterministic replay, independent role/condition streams, reordered conditions,
  selected subsets, new-session resets, and the agreed abort/retry/resume rules. Never
  report a compiled but undisplayed image as an actual exposure.
- Verify source data and unrelated timing/trigger/task/fixation contracts are unchanged;
  add config/bundle/template and saved-project round trips, including old-schema defaults.
- Add registered GUI tests for defaults, policy changes, applicability, persistence,
  explanatory text, Review, keyboard access, and no clipping at the current documented
  Setup minimum/default size. Use existing `pyside6-gui-cleanup` and `pytest-qt-smoke`
  skills when implementing the GUI.
- Run compiler, core/project-io, and safe GUI focused routes, then repo precommit.
  Run Qt and manual display acceptance only in an explicitly approved safe visible
  environment. No local offscreen Qt execution.
- Planning-only verification: `./scripts/verify.ps1 -Scope docs -Tier focused`.

## Related Plans And Exclusions

Coordinate presentation and seed compatibility with
[Explicit session-design controls](explicit-session-design-controls.md); condition
order and image-pool reset are separate choices and need not ship together.
[Stimulus comparison](stimulus-comparison-and-preprocessing-previews.md) owns proposed
duplicate-file reporting. This plan does not change Masking target reuse or Base/mask
sampling, native AB character streams, word scheduling, image transformations, image
bytes, participant scoring, or scientific preprocessing.
