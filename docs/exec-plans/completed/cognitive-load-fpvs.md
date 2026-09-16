# Cognitive Load FPVS

Status: completed

## Requested workflow and assumptions

Create a Cognitive Load FPVS experiment category on `codex/cognitive-load-fpvs`.
The starter contains three image conditions, each represented by matched load and
no-load variants (six runs), with shared placeholder image sources within each pair.
Each variant runs once in a randomized session. Default FPVS exposure is 90 seconds
at 6 Hz with every fifth image an oddball. Existing Timing & Session controls remain
the duration editor. Fixation monitoring is disabled for the scaffold so it does not
add a second distraction task; the fixation cross remains visible.

A baseline runs once before the first selected session entry, even after shuffling.
It asks the participant to subtract 13 repeatedly from a seeded random integer in
1000–9999, for 120 seconds by default, then enter the final integer. These settings
are editable. Load runs show a fresh start number before FPVS and collect the final
number immediately after playback, before feedback or the next condition. No-load
runs have no concurrent counting assignment or endpoint question.

Backward-counting baseline, start, and endpoint modules are reusable library choices
in ordinary projects. Estimated steps are `(start - end) / subtraction step`; retain
fractional estimates/remainders, raw endpoints, duration, and rate. This estimate is
not evidence of correct intermediate subtraction. Baseline comparisons use rates
because baseline and FPVS durations differ.

## Boundaries and implementation

- Core owns category/preset, task settings, seeded numbers and task compilation.
- Preprocessing owns deterministic placeholder image creation and manifest provenance.
- GUI reuses the existing category, Design, and modular task editor surfaces.
- Runtime owns sequencing, calculations and incremental task exports in full/compact
  modes; engines render the existing neutral task screens. RunSpec timing is unchanged.
- Project paths stay relative and rooted in the chosen experiment folder. Existing
  projects, task defaults, exports, and unrelated active plans are preserved.

## Verification

1. Establish core and GUI focused baselines, then test new seeded compilation,
   randomized first-session baseline, paired source/duration equality and persistence.
2. Use fake-engine runtime integration to test baseline, load/no-load flow, immediate
   endpoint collection, abort persistence, estimates and full/compact exports.
3. Add registered GUI coverage; run safe focused checks and repo precommit. Do not
   run local Qt or real PsychoPy without an approved safe visible environment.
4. Document a visible/manual acceptance path and report unrun hardware checks.

## Progress

- Feature branch created; clean starting tree.
- Core focused baseline: 383 passed, one unavailable Windows symlink check skipped.
- GUI focused baseline passed (non-Qt).
- Implementation split across core tasks/compiler, GUI, runtime, and preset/integration.
- Category and three matched pairs implemented, with manifest-backed placeholder
  PNGs. Created the requested experiment in the configured FPVS Studio Project Root
  and compiled its saved project successfully (six runs, three task modules).
- Baseline/start/report modules added to the built-in task chooser with editable
  settings, linked reports, shared-edit controls and first-session occurrence.
- Runtime records endpoint estimates, remainder, planned/observed duration, rates and
  eligible baseline comparisons. Full/compact checkpoints preserve aborted work and
  upgrade old CSV headers without losing existing values.
- Fixed duration-only task screens accepting Space early and integer numeric inputs
  losing fractional validation at large bounds; both have headless regressions.

## Final verification and boundaries

- Core focused: 410 passed, one Windows symlink check skipped.
- Counting/runtime targeted: 49 passed. Existing task/session tests: 43 passed.
- Runtime focused: 317 passed, one symlink check skipped; the process-lock test hit
  sandbox `WinError 5` creating a named pipe and passed outside the sandbox (1 passed).
- Repo precommit: Ruff, changed-file compilation, mypy (173 source files), harness
  and docs audits passed. Non-Qt suite: 1632 passed, seven Windows symlink checks
  skipped, and the same named-pipe test failed only within the sandbox. Its independent
  unsandboxed rerun passed. No source change was needed for that environment failure.
- Bundle verification used short pytest base paths to avoid Windows `WinError 206`.
- GUI focused static checks and registered coverage added; no local Qt tests, visible
  GUI session, physical trigger/display session, or packaged release was run.
  The visible acceptance path remains documented in `docs/COGNITIVE_LOAD_FPVS.md`.
