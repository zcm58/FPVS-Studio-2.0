# Backend Reliability And Compilation Efficiency

Status: Completed

## Authorization and scope

The user approved fixing all eight findings from the September 18 backend review,
especially repeated compilation work, on a new feature branch followed by verification,
commit and push. Work is on `codex/backend-reliability-efficiency`.
Trigger-sending logic, experiment timing, seeded randomization, and existing persisted
research formats remain unchanged. No GUI or hardware execution is implied.

## Implementation and acceptance

1. Preserve completed compact run results across later presentation/cleanup failures.
   Verify recoverable checkpoints and explicit interruption without hiding the error.
2. Make shared JSON persistence atomic. Inject write/replacement failures and preserve
   the prior destination byte-for-byte.
3. Separate retry-safe research history commits from derived spreadsheet generation.
   Verify repeated finalization, report failure, and distinct participant visits.
4. Stage source-image replacement and unify intake behavior. Verify disjoint filenames,
   partial copy failure, shared-set preservation, and project/manifest/pool agreement.
5. Hash bytes as they are streamed into bundles. Verify mutation between phases,
   round trips, limits, cancellation, and atomic destination replacement.
6. Prepare shared compiler inputs once per invocation. Preserve complete seeded output
   parity and independent run realization; verify read counts scale with unique assets.
7. Read historical session plans only when legacy seed fields are missing.
8. Mechanically enforce documented internal dependency restrictions and relative imports.

## Work ownership

- Compiler changes and parity/performance regressions: compiler review agent.
- Runtime durability, report retry safety and legacy seed reads: runtime review agent.
- Image replacement and document bindings: preprocessing review agent.
- Atomic JSON, bundle streaming, dependency checks, documentation and integration: root.

## Verification

Run narrow regression tests, relevant focused routes, and repo precommit (safe non-Qt
suite, mypy, Ruff, compilation and audits). Register new test files in the existing
verification routes. Compare seeded compilation outputs and record measured operation
counts; do not infer wall-clock speedups. Report platform skips and unrun visible GUI,
hardware or installed-build acceptance separately. Review all changes before committing,
push the feature branch, and verify remote commit identity.

## Progress

- Initial checkout clean on `master` at `53b7400`; feature branch created.
- Baseline repo focused checks: 32 passed.
- Review identified six baseline library-publishing launch-validation fixture failures;
  address only fixture intent if required, without changing excluded sending behavior.
- Compiler parity: ten complete-plan fingerprints captured before refactoring match
  afterward across image, word, AB, counting and memory studies at two seeds.
- Synthetic 40-run/29,200-event session: project validations 41 -> 1, manifest probes
  41 -> 1, condition validations 40 -> 4, directory scans 80 -> 2, task-asset checks
  1,440 -> 12, task-image hash reads 960 -> 12 (now streamed).
- Five alternating runs after warm-up, same Windows/Python 3.10.11 environment:
  median compilation 6.564 -> 2.181 seconds, with full output equality every run.
  Tiny synthetic task assets and concurrent local development load limit generalization.
- Windows save stress reproduced 29/1,000 transient native access-denied replacements
  with no application handles open; immediate repeats all succeeded. Shared atomic
  replacement now retries only native Windows access/sharing/lock errors for at most
  150 ms. Persistent failures propagate; no non-atomic fallback exists. A fresh
  1,000-write/readback stress run passed with zero failures or leftover temporary files.
- Atomic JSON/project/bundle regression group: 49 passed. Project-io focused (before
  the additional Windows-lock regressions): 175 passed. Docs focused: 9 passed.
- New safe tests are registered in compiler, project-io, preprocessing, GUI and runtime
  verification routes; config audit passes. Visible Qt coverage remains registered/unrun.
- Compiler focused: 249 passed. Runtime focused: 354 passed, one Windows symlink
  privilege skip. Full-source mypy (193 files), changed-file Ruff/compilation and
  repository/documentation audits pass.
- The first complete safe suite exposed baseline fixture drift in mocked engine and
  serial-backend tests: missing explicit test-mode options or missing fake-backend
  capability metadata. Corrected test inputs to the existing contracts; production
  trigger sending and existing behavior assertions are unchanged. Both mocked test
  files pass (106 tests).
- Final repo precommit passes: 1,952 tests passed, eight Windows symlink-privilege
  skips, 153.70 seconds. Ruff, compilation, mypy and repository/documentation audits
  also pass. All eight review findings have regression coverage.
- Visible Qt, physical display/EEG hardware, and installed-build acceptance were not
  run. No production engine or trigger-sending files changed. Seeded compiler output
  parity and mocked runtime tests do not constitute hardware timing verification.
