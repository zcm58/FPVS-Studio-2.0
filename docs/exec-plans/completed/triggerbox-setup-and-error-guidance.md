# TriggerBox setup and error guidance

Status: Completed

## Requested behavior

Make Recording Setup explicitly require installing the vendor software/drivers while
closing Configuration/Test IO during Studio experiments. Keep BrainVision Recorder
recording. Explain common failures concisely in setup and launch errors, retaining
technical diagnostics in details. The operator confirmed Test IO successfully sent
markers on the affected PC; that supports a working driver/output route and an
exclusive-port conflict, not a missing-driver diagnosis for that incident.

## Implementation boundaries and acceptance

- Share pure TriggerBox connection-error classification/wording between Detect and
  backend launch: busy/denied, missing port, settings rejected, communication failure,
  timeout, close failure and unknown failures. Check COM3/COM4 and serialized errors.
- Keep missing Studio serial support distinct from vendor software installation.
  No listed COM port cannot prove a missing driver, and access denied cannot identify
  a specific process. Recommend relevant checks without claiming either was detected.
- Distinguish marker-write timeout, short marker/reset write, reset-worker failure
  and too-close marker scheduling; preserve abort, cleanup and no-resend behavior.
- Preserve concise actions through chained/serialized error popups; unrelated file
  errors mentioning TriggerBox must keep their file guidance.
- Retain the 700x640 Recording Setup layout, manual selection, worker/cancellation
  behavior, settings formats and all marker scheduling. Add registered Qt cases but
  do not execute Qt without the repository's visible-environment approval.
- Run focused trigger/GUI/docs checks and non-Qt repo precommit with a short temporary
  test base to avoid the previously observed Windows path-length test failures.

## Timing note

The user reported that BrainVision staff described a constant 1 ms pathway delay
during training on 2026-11-05; this was staff advice, not a measurement supplied by
the user or performed by Studio. Current TriggerBox Plus specifications state USB
delay <1 ms and jitter <1 ms. Explain transport latency without adding a universal
fixed compensation or treating USB timing as measured display-to-EEG timing.

## Evidence and status

- Baseline focused triggers: 272 passed.
- Before implementation: 13 connection/write-timeout regressions failed, and the
  support-summary review reproduced 23 new-message failures.
- Implemented shared connection recovery, specific marker/reset failures, setup
  guidance and preservation of actionable summaries through error popups. Raw
  diagnostics remain available; no process ownership or driver-installation claims
  are inferred from a failed COM operation.
- Focused triggers: 295 passed; targeted backend/discovery/support checks: 199 passed.
- Non-Qt repository precommit passed in an isolated short-path checkout: Ruff,
  compilation, mypy and repository/documentation audits passed; 5,341 tests passed,
  32 skipped for platform/symlink constraints, and 24 subtests passed. A short pytest
  temporary base avoided the prior Windows path-length failures and the checkout
  excluded unrelated user-owned untracked files.
- Integrated concurrent upstream saved-COM3/Recorder-confirmation and response-cursor
  commits. Preserved saved-port selection and repaired the merged GUI fixtures so
  geometry cases explicitly assert the intended recovery message. Post-integration
  focused checks passed: GUI 178, engine/runtime 608, docs 13; changed-file Ruff and
  compilation passed. Verified source/test copies against the primary checkout.
- Registered GUI cases cover missing/occupied COM3/COM4, serial dependency/listing
  failures, rejected settings, USB communication, timeout, close/cleanup and unknown
  errors, plus long content in both themes at 700x640. Qt and physical TriggerBox,
  Recorder, display-to-EEG timing and installed-package checks were not performed.
  The visible acceptance path remains in `docs/GUI_WORKFLOW.md`; no installer was built.

Primary references: [software/drivers](https://www.brainproducts.com/downloads/more-software/),
[single-program setup](https://www.brainproducts.com/download/how-to-set-up-the-triggerbox-plus/),
[Plus timing specifications](https://www.brainproducts.com/solutions/triggerbox/).
