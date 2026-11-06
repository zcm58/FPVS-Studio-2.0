# Plain-language error recovery

Status: Completed (source implementation; visible acceptance unperformed)

## Requested behavior

User-facing errors explain what happened, a supported possible cause, and a short
recovery step in ordinary language. Python exception names, stack traces, internal
field names and serialized settings belong in expandable technical details rather
than primary messages. Keep useful device names, file names, values and settings
labels. Preserve the conditional TriggerBox occupied-port message approved by the user.

## Implementation boundaries

- Improve the existing shared explanation owner and its GUI presentation paths;
  route inline failures through the same owner where raw exceptions bypass it.
- Preserve clear existing validation instructions and distinguish local device/file
  failures from online-service failures. Do not invent a root cause, claim an
  application is running, or infer a missing driver from an absent COM port.
- Explain common setup, recording, launch, import/open/save/export and update
  failures. Retain complete diagnostics in details/logs and existing report flows.
- Preserve validation, marker scheduling, abort behavior, saved formats, worker
  ownership and cancellation. No new retries, probes or silent fallbacks.
- Keep required recovery steps visible with wrapping; update registered GUI tests
  without running Qt locally. Visible acceptance checks the affected dialogs at
  their documented minimum sizes, long errors, both themes and expanded details.

## Verification

1. Audit shared and bypassed error surfaces; reproduce technical text leakage and
   misleading classifications with targeted tests.
2. Update message owners and callers; verify exact summary/recovery and preserved
   diagnostics, including native/chained/serialized error paths.
3. Run focused trigger/GUI/docs checks and safe repository precommit. Report skipped
   visible GUI/hardware checks, finalize this record, and commit/push the changes.

## Evidence and status

- Baseline before broadening: trigger scope 295 passed, GUI non-Qt scope 178 passed,
  docs 13 passed, and popup/occupied-port launch checks 89 passed.
- Shared explanations now distinguish device/display failures, local file problems,
  online-service failures, update verification and field validation. Current and
  historical TriggerBox failures retain their specific recovery advice. Unknown
  failures acknowledge an unclear cause instead of inventing one.
- Exception-driven inline labels across recording, authoring, results, Library,
  sharing and updates use the shared owner. Raw diagnostics remain in details,
  tooltips or logs. The standalone updater hides technical text behind Show Details.
- Focused verification passed: 172 explanation tests, 295 trigger-scope tests,
  178 safe GUI-scope tests and 13 documentation tests. The 76 sharing-workflow
  tests preserve failed opt-out warnings, disabled state, cancellation and retries.
- Non-Qt job harnesses now bind the production formatter and retain workflow and
  diagnostic assertions. Repository precommit ran against a hash-matched isolated
  short-path checkout, excluding unrelated user-owned untracked files.
- The initial full run exposed stale extracted-method test harnesses (repaired)
  and one Windows bundle-rename access failure in unchanged core code. All 302
  final explanation/sharing/Library job tests passed together. The complete
  library-origin module passed separately (25 passed, 2 platform skips), including
  both duplicate-release cases; the transient access failure's cause is unconfirmed.
- Final precommit: Ruff, compilation, Windows typing (271 files), macOS typing
  (9 files) and repository/documentation audits passed. Safe tests: 5484 passed,
  32 platform skips, 24 passing subtests and one Windows access-denied failure in
  `test_bundle_transfer_without_windows_long_path_policy[True]`. The import-module
  rerun produced the same failure in the other parameter case (110 passed,
  2 skipped). Restoring the disposable checkout to committed `840e7c0` reproduced
  that same rename failure on the second targeted baseline run, confirming it
  predates these changes. The importer and its tests were not modified.
- Registered Qt coverage was updated but not executed locally. Visible acceptance
  remains: induce occupied/missing-device, validation, permission, online-service
  and update failures; check wrapped recovery text at minimum/default sizes in
  both themes, then open details and retry. No physical hardware or installer
  qualification was performed.
