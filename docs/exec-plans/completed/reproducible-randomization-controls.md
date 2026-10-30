# Reproducible Randomization with Three Seeds

Status: Completed

## Purpose and confirmed decisions

Planning branch: `feat/condition-timing-and-reproducibility`. Implemented on this feature branch. For FPVS image and word conditions, expose **three independently editable
seeds**: stimulus order, condition order and fixation schedule.

Use **one overall fixed/new switch for all three areas**, rather than three separate
reuse-mode switches. Fixed mode reuses the configured seeds so corresponding condition
presentations match across participants. New mode generates fresh resolved seeds for
each participant session; preserve today's fresh-randomization default for existing
projects unless explicitly changed. Place the controls in Timing & Session alongside
the condition timing table. Call the modes plainly so users understand seed reuse.

Repeated presentations vary their image/word order and fixation schedules within a
session, while the corresponding repeat stays identical across participants in fixed
mode. The fixation seed controls both randomized target counts and onset timing.
If fixed schedules conflict with the existing no-equal-neighbor-count rule, report
the conflict rather than silently changing the fixed schedule.

The condition-order seed governs the fully pooled, no-adjacent-repeat order in the
[presentation-count plan](../completed/per-condition-repeat-counts.md). Existing stimulus balance,
repeat avoidance and fixation feasibility rules remain applicable.

## Current evidence and ownership

- `SessionSettings.session_seed` in `core/models.py` is the only stored session seed.
- `core/compiler.py` currently shares a session RNG across condition shuffles,
  run-seed generation and randomized fixation counts. These domains are coupled.
- `core/compiler_schedules.py` derives role-specific balanced stimulus bags from run
  seeds; `core/compiler_fixation.py` realizes fixation schedules before playback.
- `gui/document.py` generates new seeds on project opening and prevents completed
  seed reuse before normal compilation; masking also refreshes on compile attempts.
  `gui/main_window.py` coordinates deferred/background seed preparation.
- `gui/session_structure_page.py` has hidden seed controls and a static randomized
  order label. Merely showing the existing field would not implement fixed mode.
- Execution/config exports record session/run seeds under labels that do not describe
  the current fixation coupling. `core/data_sharing.py` deliberately strips existing
  execution seeds from protocol fingerprints.

## Implementation sequence

1. Define persisted seed reuse policy and three validated seed values, with compatible
   loading for existing projects. Preserve historical compiled artifacts and replay.
2. Create independent deterministic RNG domains. Derive per-condition schedules from
   domain seed, stable condition ID and chronological occurrence index, not participant
   number, run ID, session ID or global session position. Order changes must not
   accidentally reroll image/word or fixation streams through shared RNG consumption.
3. Preserve balanced base/oddball source selection and fixation timing realization in
   core compilation. Do not add runtime randomness or alter base/oddball scheduling.
4. In fixed mode, opening/reopening, previewing, compiling, completed-seed history and
   launching another participant must not replace the configured seeds. Prevent late
   background generation results from overwriting a newly selected policy or seed.
5. In new mode, resolve and record a fresh triplet for a new participant session. Keep
   a pending launch/retry internally consistent rather than silently rerolling it at
   each preflight step. Recovery replays the originally compiled schedules.
6. Show the overall switch and three clearly labeled seed fields, with explicit seed
   editing/generation behavior and unambiguous configured versus resolved values.
7. Record policy and resolved seed provenance in compiled/session results, full and
   compact exports, completed configs and interchange. Decide protocol-fingerprint
   treatment intentionally and test it; do not accidentally include/exclude new fields.

## Acceptance and verification

- With the same project inputs, effective refresh rate, policy and seeds, two different
  participants receive the same constrained condition order and corresponding
  condition-occurrence stimulus identities and fixation count/onset frames.
- Repeats use distinct occurrence namespaces. A nondegenerate acceptance fixture must
  demonstrate different stimulus and fixation schedules between A's repeats, while A's
  first chronological occurrence matches every other participant's first A occurrence.
  When constraints admit only one valid schedule, report that limitation rather than
  promising impossible variation.
- Changing one domain seed does not consume another domain's RNG or silently alter
  its schedules. A changed order that violates fixed fixation count constraints is
  explicitly rejected, not repaired by changing the fixation realization.
- Fixed seeds survive project reload, compilation, completed-session history and stale
  asynchronous callbacks. New mode produces/records fresh triplets without requiring
  different outputs when a domain's constrained solution space has only one result.
- Cover image and word bags, fixation fixed/randomized counts, unequal repeats,
  adjacency constraints, launch/recovery, persistence and full/compact/config exports.
- Add registered UI tests for both modes, edited/invalid seeds, reopening and stale
  worker results at `1120x820` in both themes. Run core/compiler/runtime/gui/project-I/O
  focused routes and repo precommit under existing visible Qt approval rules.

## Reproducibility limits and scope

Equal seeds do not guarantee equal schedules after source inventories/order, authored
settings, effective refresh rate or the scheduling algorithm changes. Report those
inputs and resolved schedules rather than promising hardware-independent timing.
Participant response times and accommodation colors remain separate from schedule
reproducibility. Native AB character/SOA, masking catch/grouping and pre/post-task
randomness retain their existing contracts; audit their seed dependencies so this work
does not change them accidentally or claim three new controls cover unrelated tasks.

## Related plans

Coordinate with [frequency overrides](../completed/clear-presentation-frequency.md),
[stream duration](../completed/per-condition-stream-duration.md) and
[presentation counts](../completed/per-condition-repeat-counts.md). Implementation may share
canonical models/helpers where needed, but each plan retains its own acceptance gate.

## Execution progress and UI brief

- First three feature plans are committed/pushed: 3200a42, 62d7064, ebcef13.
- Timing & Session exposes one overall Same for every participant / New for each
  participant choice and three labeled seeds. Pending launch seeds are resolved once;
  retries preserve them. Seed values are provenance, not participant identity.
- Use stable domain/condition/chronological-occurrence namespaces. All actual seeded
  FPVS schedules must preserve domain independence; report constraint conflicts rather
  than repairing a fixed seeded schedule. Fixed target-count mode retains its existing
  meaning; the no-equal-count rule applies to randomized count schedules.
- Default reuse remains new/fresh. No source rewrite merely from loading a legacy
  project, and no stale app-open callback may override an authored fixed choice.
- Existing ordering fingerprint identity is canonical in core/session_ordering.py;
  extend the one protocol identity path deliberately for seed policy/settings.
- Native AB, specialized masking grouping/catches and task randomness retain existing
  contracts. Document their scope precisely; no runtime randomness is introduced.
- Verify deterministic image/word/fixation schedules, lifecycle/recovery/provenance,
  persistence and source gates, with registered GUI coverage and no local Qt execution.

## Implementation decisions

- Keep `SessionSettings.session_seed` as condition-order seed; add optional validated
  `stimulus_seed`, `fixation_seed` and `randomization_mode` fields. Null mode preserves
  the legacy input shape while resolving to fresh/new behavior. Explicit mode requires
  a complete triplet; no fourth seed setting is introduced.
- `core/randomization.py` owns the typed triplet, deterministic domain derivation and
  policy resolution. Ordinary sessions use independent domains; legacy standalone
  RunSpec compilation without explicit randomization retains its old explicit-run-seed
  contract. Ordinary GUI previews explicitly supply the configured triplet.
- Fixed mode rejects a supplied launch triplet that differs from configured values.
  New-mode pending launch state is keyed to participant/visit and policy/seed settings;
  retries preserve it, and completed executions or author edits invalidate it.
- Explicit controls are unavailable for native AB and specialized masking; those
  streams retain their legacy randomization and grouped/task contracts.
- Protocol identity includes effective policy and randomization algorithm version.
  Fixed mode also includes the three configured values; new-mode seed realizations
  are provenance and are excluded from protocol identity.
- Project 1.14/config 1.12 carry explicit settings; SessionPlan/RunSpec 1.7 carry
  resolved independent-domain provenance. Historical artifacts remain readable.

## Verification result

- Core/fingerprint: 95 passed; affected session/duration/preparation: 147 passed.
  Final compiler focused: 644 passed. Native AB baseline hashes remain unchanged.
- Consumer config/provenance: 70 passed; fixed same-plan participant/visit coverage
  runs full and compact exports without collisions or seed replacement.
- Safe repository suite: 4142 passed, 12 Windows symlink skips, 24 subtests passed,
  11 failures. Ten were old handoff-schema assertions and one was an AST test stub
  missing the new seed-signature collaborator. Updated affected modules passed177
  tests/one expected symlink skip and76 non-Qt GUI-job tests. No production fallback
  was added to accommodate the test stub.
- Final Ruff/compilation, full-source mypy and repository/configuration audits passed,
  with only the pre-existing unrelated helper lint exclusions recorded in plan1.
- Registered GUI coverage checks Fixed/New, invalid/zero/max seeds, stale callbacks,
  pending retries across all launch entry points, recovery and both-theme geometry.
  Qt and physical display checks were not run locally.
- The user added generated-order preview plus manual reordering and a simplicity
  preference during this gate. Those changes have their own next plan, followed by
  the already planned post-condition question work; this plan's source stays scoped.
