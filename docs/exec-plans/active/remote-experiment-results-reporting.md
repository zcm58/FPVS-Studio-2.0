# Remote experiment results reporting

Status: Active

Date: 2026-10-05

Implementation approved on 2026-10-05 on `codex/experiment-data-sharing`.
Source implementation is complete. Focused local checks and latest repo precommit
pass. User-approved visible GUI acceptance and authorized live service acceptance
remain separate checks. Keep this plan active until those acceptance boundaries are
resolved.

## Outcome and approved scope

The user selected per-experiment opt-in, lab-issued invitation codes, automatic
reporting after completion and easy comparison with compatible shared results.
V1 implements private fixation summaries for newly completed multi-condition
session launches, including single-occurrence sessions. Local research results
remain authoritative; the standalone stream-only execution API does not capture.

The canonical implemented workflow, wire fields, bounds, identity, crash recovery,
credentials and comparison rules live in [Data sharing](../../DATA_SHARING.md).
The independently deployable [Results Worker](../../../services/results/README.md)
contains Worker/D1 source and migrations. Existing Library and Feedback services
remain independent. No service resources or hostname have been provisioned, and
no research data has been submitted to a live endpoint by local verification.

## Implemented ownership

- Core `data_sharing.py` owns strict allowlisted report, profile, receipt and
  comparison schemas and read-only authored protocol/selected-asset fingerprints.
- Runtime `data_sharing.py` owns explicit capture intent before presentation,
  terminal eligibility before research finalization, and commit proof plus queueing
  after research writes and before derived participant workbooks. It checks actual
  launch flags, complete frames/tasks/occurrences and completion-screen outcomes.
- `data_sharing/storage.py` owns private project-local settings, immutable outbox
  bytes/digests/attempts/receipts, safe state transitions and explicit local archive.
  OS credentials and fixed-origin HTTP remain in dedicated neutral modules.
- GUI `data_sharing_controller.py` uses app-owned cancelable jobs and captured project
  snapshots. View > Data Sharing & Comparison supplies enrollment, separate opt-in,
  backlog retry, revoke and archive controls plus descriptive condition comparison.
  Never-enrolled/off projects skip asset hashing; enrolled hashing checks cancellation
  between chunks. Reporting jobs drain asynchronously before presentation begins.
- `services/results/` owns independent deployment source, D1 schema, invitation
  registration SQL generation, scoped enrollment, durable/idempotent intake,
  revocation, receipts and aggregate comparison. Owner CSV administration is future
  work; it is not an implemented endpoint or current acceptance requirement.

## Decisions and integrity boundaries

Enrollment never opts in. Project/config/bundle transfers exclude automatic sharing
activation and credentials. Protocol/version edits hold uploads while local runs
continue; earlier reports retain their original identity. Actual selected image and
task media bytes enter the fingerprint, excluding local identity, random seeds and
machine connection/display geometry. Missing verification is actionable.

One fresh UUID belongs to each reporting-enabled session execution. Repeated compiled
session IDs cannot deduplicate remote reports. Immutable bytes and the same UUID
survive retry; the service returns the same receipt or rejects conflicting bytes.

The wire envelope carries study/version/protocol, UUID, UTC completion time, Studio
version and ordered fixation occurrences. It carries no participant numbers,
demographics, host/path identifiers, raw answers, stimuli, EEG or logs. Completion,
actual test/Pilot context and participant-to-report mappings remain private local
proof. Additional timing-QC fields from the initial proposal are deferred; V1 neither
infers EEG quality nor silently rejects poor performance.

Test/Pilot sessions, reserved IDs `0`/`00`, aborted/incomplete sessions and protocol
mismatches remain local. Research rows alone never authorize upload. Recovery requires
explicit eligible terminal proof, a persisted research-commit marker and matching
numbered condition-history evidence. A crash between research commit and marker
requires review and remains held. A failed derived XLSX cannot lose a queued report.
Reporting faults preserve ordinary local execution and its original errors.

Comparison uses the latest eligible local captured session and the same registered
reference scope. Each condition needs ten distinct report sessions from three other
enrolled devices; these counts are not unique participants. The service excludes
the requesting enrollment and suppresses incompatible source/window cohorts. Studio
also checks actual local provenance against the returned uniform reference method.
Accuracy pools hits/targets; RT uses observation weighting. This is descriptive
comparison, not a repeated-measures or causal analysis.

Explicit Archive uploaded history moves older acknowledged records and matching
finalized mappings into guarded project archive files. The latest uploaded record
per scope stays active. Unsent/unfinished captures and raw research exports are
preserved; receipts and mapping survive for audit. Archive makes no network request
and changes no shared data. Partial moves are actionable and resumable.

## Completed source verification

- [x] Neutral strict contracts, zero-target/no-hit semantics, private field rejection,
  bounded payloads and authored/actual-asset fingerprint checks.
- [x] Durable capture boundaries in full/compact workflows; failure injection for
  intent, terminal, research, queue and workbook writes; UUID replay and no backfill.
- [x] Opt-out/backlog, immutable receipt, hostile paths, atomic replacement, capacity,
  explicit archive preservation and partial-move recovery checks.
- [x] Desktop fake-transport/secure-store and synthetic Worker intake/comparison checks.
- [x] GUI source and registered tests added without running local Qt. No experiment
  presentation or hardware run was performed.
- [x] Final `data-sharing` focused route: 127 checks pass, including corruption-safe
  opt-out, failed backlog-pause, cancellation and default-off startup regressions.
- [x] Runtime focused route: 567 pass, two skip for unavailable Windows symlink
  privilege. GUI safe focused route: 17 pass. Docs focused route: 10 pass.
- [x] Independent synthetic Worker suite: 16 tests pass; six syntax checks pass.
  No credentials, participant data or deployed resources enter these checks.
- [x] Earlier repo precommit ran outside the sandbox: changed-file Ruff/compilation, mypy
  (222 source files), repository audits and docs hygiene pass. Earlier full non-Qt
  suite: 2,671 pass, 11 skip, one fails at the unchanged Library staging-directory
  rename (`test_explicit_newer_library_import_preserves_the_previous_project`,
  WinError 5). An isolated Library/serialization module follow-up has 30 pass,
  two skip and one different Library import access failure. Earlier isolated
  serialization retry cases all passed. No Library import/serialization production
  or test code was changed to mask these failures; their locking process is unproven.
- [x] Latest repo precommit after collection-safe version-review changes passes:
  2,672 unit tests, 11 Windows symlink-privilege skips, changed-file Ruff/compilation,
  full source mypy (222 files), repository audits and docs hygiene. Earlier Windows
  file-access failures did not recur; no import/serialization code was changed.

## Remaining acceptance

- [x] Obtain a clean repo precommit result. The earlier file-locking process remains
  unproven; this passing run does not claim an unrelated Windows issue was fixed.
- [ ] In a user-approved safe visible environment, inspect the dialog at `820x620`
  minimum and `880x700` default, both themes and practical Windows scaling. Exercise
  long labels, busy/error/cohort states, opt-out and cancellation during requests,
  project switching and app shutdown. Registered Qt checks do not establish this.
- [ ] Before live enrollment, authorize private-data ownership, retention/deletion,
  backup, research approval, hostname/D1 provisioning and current account capacity.
  Desktop configuration alone is not authorization to deploy.
- [ ] Deploy an isolated staging experiment after approval. Enroll multiple machines
  with synthetic sessions; verify full/compact local metrics, lost-response retry
  deduplication, credential-scope rejection, revocation and a 10-session/3-other-device
  reference cohort. No local test establishes live multi-machine acceptance.

Use `./scripts/verify.ps1 -Scope data-sharing -Tier focused` for this feature and
repo precommit for cross-layer changes. Follow the GUI route without local Qt;
registered Qt execution needs explicit user approval in a safe visible environment.
Do not use offscreen Qt. The service README owns local synthetic Node test/check
commands and the separately authorized deployment procedure.

## Future work

Public dataset publication, raw EEG/files, task-specific result schemas, longitudinal
pseudonyms, researcher dashboards, owner CSV exports and per-run email require their
own scope and explicit workflows. They are not implied by private fixation reporting
or by contributor access to aggregate comparison.
