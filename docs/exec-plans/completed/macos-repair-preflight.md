# Mac repair preflight and truthful completion reports

Status: Completed (implementation)

## Authorized outcome

Check the existing engine before changing packages, distinguish compatibility
updates from repairs of observed failures, and use friendly GitHub report wording.
Publish the desktop changes to master and deploy the compatible reporting service.

## Boundaries

- Keep the Mac-wide SciPy constraint. A working environment can receive compatibility
  updates to match the source requirements; version drift alone is not an engine failure.
- Record initial engine, dependency and compatibility checks independently. Preserve
  those results through setup, failures and detached IDE completion. Report package
  updates separately from rebuilding the entire environment.
- Add optional typed facts to the existing reporting protocol. Preserve existing
  receipts, old report compatibility, opt-out, bounded payloads and raw-log exclusion.
- The researcher's requested per-file stimulus counts, spacing and ordered loading
  are a separate feature request and are outside this repair change.

## Verification

1. Reproduce healthy-engine/version-drift misclassification with regression tests.
2. Cover actual engine failure plus drift, no changes, check-only and failed updates;
   ensure the initial engine test precedes setup or IDE mutations.
3. Verify compact local/email reports, legacy payloads and failure wording; run focused
   checks and repository precommit without local Qt execution.
4. Deploy service changes before the client; validate one synthetic staging report,
   retain rollout evidence, publish source and remove disposable verification data.

## Progress

- [x] Confirm current probe checks metadata before loading the engine.
- [x] Separate setup diagnosis from the researcher's feature request.
- [x] Implement and test helper preflight/classification.
- [x] Implement and test local/service report presentation.
- [x] Deploy the reporting service and complete source verification for publication.

## Evidence

- Helper 2.1 separates the actual engine import, installed dependency consistency
  and source compatibility checks. Confirmed version differences use a distinct
  probe exit; unexpected failures remain unknown and stop further mutations.
- Final focused repair checks: 195 passed. Reporting checks: 58 passed, with two
  Windows permission/POSIX skips. Independent review found no remaining blockers.
- Repository precommit: 6,439 passed, 41 platform/permission skips and 24 passing
  subtests. Ruff, compilation, Windows/Darwin mypy and repository audits passed.
  The final probe-error and check-only refinements were verified in the focused
  checks above after the full run began.
- Feedback `ec86cdc` is deployed on production and staging; 50 service tests and
  both builds passed. Exact module readback confirmed the deployed source, with
  existing bindings and feature flags preserved. A single synthetic staging report
  verified delivery for healthy-engine compatibility updates; the final wording
  follow-up submitted no additional report. `FPVS-Studio-Feedback/DEPLOYMENT.md`
  retains the deployment and receipt evidence.
- The researcher's log identifies a native SciPy library load rejection on macOS
  27.0. The maintainer's successful helper run was on macOS 26.5.2. Matching SciPy
  release numbers do not prove identical wheels; neither the OS difference alone
  nor the replacement wheel has been validated on the affected Mac.
- Affected-Mac repair, visible completion and Test/Pilot remain acceptance checks
  under [macOS Phase 1](../active/macos-source-phase-1.md). No local Qt session was launched.
