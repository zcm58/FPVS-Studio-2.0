# Remote experiment results reporting

Status: Active

Date: 2026-10-07

Implementation approved on 2026-10-05 on `codex/experiment-data-sharing`.
The source feature is integrated with OpenFPVS lab-code/project administration on
`codex/openfpvs-project-reporting` and sibling OpenFPVS's
`codex/studio-project-reporting`. Current verification and remaining activation are
recorded below; earlier standalone notes are historical. Keep this plan active
until production activation and packaged Studio acceptance are resolved.

## Outcome and approved scope

The user selected per-experiment opt-in, lab-issued invitation codes, automatic
reporting after completion and easy comparison with compatible shared results.
V1 implements private fixation summaries for newly completed multi-condition
session launches, including single-occurrence sessions. Local research results
remain authoritative; the standalone stream-only execution API does not capture.

The canonical implemented workflow, wire fields, bounds, identity, crash recovery,
credentials and comparison rules live in [Data sharing](../../DATA_SHARING.md).
The OpenFPVS sibling repository owns the production Worker, additive D1 migration,
explicit lab/project grants and private project dashboard. Begin with its
`PROJECT_REPORTING.md`. The [standalone reference](../../../services/results/README.md)
and synthetic wire fixtures remain undeployed. No research data is submitted by
local verification, and no additional service or storage provider is required.

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
- OpenFPVS `src/results/` owns scoped enrollment, durable/idempotent intake,
  revocation, receipts and aggregate comparison. `src/projects.js` owns private
  lab-scoped browser summaries and administrator project grants; `public/projects.js`
  refreshes results on each page load/reload/history restoration. Separate Results
  credentials do not expand Library permissions.

## Decisions and integrity boundaries

Enrollment never opts in. Project/config/bundle transfers exclude automatic sharing
activation and credentials. Protocol/version edits hold uploads while local runs
continue; earlier reports retain their original identity. Actual selected image and
task media bytes enter the fingerprint, excluding local identity, random seeds and
machine connection/display geometry. Missing verification is actionable.

One fresh UUID belongs to each captured ordinary session execution. Repeated compiled
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

## Initial source verification (before OpenFPVS review)

- [x] Neutral strict contracts, zero-target/no-hit semantics, private field rejection,
  bounded payloads and authored/actual-asset fingerprint checks.
- [x] Durable capture boundaries in full/compact workflows; failure injection for
  intent, terminal, research, queue and workbook writes; UUID replay and no backfill.
- [x] Opt-out/backlog, immutable receipt, hostile paths, atomic replacement, capacity,
  explicit archive preservation and partial-move recovery checks.
- [x] Desktop fake-transport/secure-store and synthetic Worker intake/comparison checks.
- [x] Initially added GUI source and registered tests without running local Qt. No experiment
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

## Historical remaining acceptance (2026-10-05)

- [x] Obtain a clean repo precommit result. The earlier file-locking process remains
  unproven; this passing run does not claim an unrelated Windows issue was fixed.
- [x] User-approved synthetic native layout review at `820x620` and `880x700`, both
  themes, 125% and 150% scaling: 80 tab/state layouts pass, with explicit opt-out and
  cancellation actions. Retained synthetic reports/screenshots are under the ignored
  `build/results-review/visible-1.25/` and `visible-1.5/` directories.
- [ ] End-to-end request cancellation during project switching and app shutdown with
  a staging service. Synthetic layout and registered Qt checks do not establish this.
- [ ] Reconcile this feature with the current released master before packaging a
  Results release, then verify the resulting Library and reporting workflows together.
- [ ] Before live enrollment, authorize private-data ownership, retention/deletion,
  backup, research approval, hostname/D1 provisioning and current account capacity.
  Desktop configuration alone is not authorization to deploy.
- [ ] Deploy an isolated staging experiment after approval. Enroll multiple machines
  with synthetic sessions; verify full/compact local metrics, lost-response retry
  deduplication, credential-scope rejection, revocation and a 10-session/3-other-device
  reference cohort. No local test establishes live multi-machine acceptance.

## Historical OpenFPVS review and integration target (2026-10-05)

The user selected the existing Library lab code with explicit contribution permission
per experiment, plus Studio's separate local experiment opt-in. This is the next
integration target, not implemented authorization. The canonical design and current
one-code/one-scope limitation are in [Data sharing](../../DATA_SHARING.md).

Confirmed review defects were corrected with synthetic regression coverage:

- Linked projects require the canonical Library receipt's exact item ID and installed
  version before authorized enrollment, capture, send and comparison. Unknown versions
  require review. The Worker accepts and checks the optional paired expected scope;
  a wrong invitation cannot create a mismatched device enrollment. An unbound local
  retry token is intentionally retained before HTTP; it does not authorize reporting.
- Enrollment atomically rechecks invitation/version revocation and expiry before
  storing the device, closing a revocation race. Expiry uses the database execution
  clock so queue delay cannot extend enrollment; a deterministic clock regression
  reproduces the original stale-timestamp acceptance before this correction.
- Duplicate JSON members are rejected before storage. They cannot hide private fields
  behind the last parsed value or make SQLite aggregate a different metric value.
  Valid immutable payload bytes and receipt digests are preserved.
- Known Test/Pilot launches and reserved participant IDs skip capture before capacity
  checks, so these launches cannot exhaust the intent collection.
- Visible verification exposed a test-isolation defect: the backend import-boundary
  check removed real Qt modules from the parent test process. It now checks fresh
  imports in a subprocess; a regression proves preloaded modules remain intact.
  Reapplied the released Library branch's stale GUI settings-fixture cleanup so the
  current feature branch can run its approved native tests.
- The default collection probe exposed two pre-existing document tests that create
  real QtCore objects outside the Qt registry. They now require explicit Qt opt-in,
  and the core route selects them only in its full tier. A fresh default collect-only
  probe blocks Qt imports; default verification can no longer hide a leak by removing
  modules after collection. These document tests' behavior is unchanged.
- The short-path precommit exposed a reproducible Windows bundle path edge: a short
  stimulus directory can contain children exceeding the legacy path limit. Bundle
  validation and collection now preserve `filesystem_path` on the directory before
  enumeration, including recursive traversal. Six real-Windows regressions cover
  directory lengths 238/247/264 with files over 260.
  No global resolver, persisted path, import transaction or file-lock retry changed.

The capacity limitation for ordinary aborted/protocol-mismatch terminal intents
remains: these consume the 512 active records, and uploaded-history archiving cannot
free them. Add an explicit review/archive workflow that preserves their evidence
before treating long-running collection capacity as complete.

Integration completion requires a reviewed experiment/version/protocol grant map,
an admin Contributions section, server-authoritative lab/PC/grant revocation, and a
separate Results route namespace. Existing Library `/v1` routes reject old clients;
the current Results client also uses `/v1` on a separately configured origin. Pointing
it directly at the Library origin would not connect these services. Preserve exact
version publication links and bundle download totals separately from contributed
session counts; neither is a count of participants.

## OpenFPVS integration and activation (2026-10-07)

The user approved private lab/administrator project pages, existing lab codes with
explicit project grants, and automatic sharing only after local experiment opt-in.
The dashboard refreshes when opened, reloaded or restored from browser history.
It reports completed sessions, latest report time and pooled fixation counts,
accuracy and weighted mean RT by condition. Results remain scoped to one project
even when separate studies share an experiment/version/protocol. The requested
session-count explanatory paragraph was removed from the website.

Final counting decision: show total completed sessions only. Labs can assign
different participant numbers across collection computers, so unique participant
totals and shared server-reserved numbering are deferred. No participant key or
participant number was added to the wire contract. Toolbox reporting is also deferred.

- [x] Reconciled the reporter with released Studio 2.3.0, preserving condition
  publication requests and installed Library identity/version checks.
- [x] Results client defaults to OpenFPVS `/results/v1`, accepts the website project
  UUID, and keeps separate OS-protected credentials. Connecting never opts in.
  Immutable outbox records also retain that UUID; explicit retry after reconnecting
  cannot send old reports to a different project with the same protocol.
- [x] Studio Copy protocol fingerprint and View OpenFPVS project actions run through
  existing job ownership. Source focused checks: 144 pass. Approved visible dialog
  checks: 13 pass at minimum/default sizes and all covered states.
- [x] Studio repo precommit: Ruff, compilation, mypy on 227 files, repo/doc audits
  and 2,748 non-Qt tests pass; 11 Windows symlink-privilege checks skip.
- [x] OpenFPVS: 242 synthetic tests pass, including actual workerd/D1 intake and
  transactional dashboard snapshots; 27 JavaScript syntax checks and dry build pass.
- [x] Desktop client against a local synthetic backend verifies enrollment, immutable
  retries, receipts, comparison suppression and fresh browser totals (2 → 4 → 6).
  Browser review covers lab/owner/anonymous views, setup disclosure and 360px/1280px
  layout without document overflow. Error/retry/bfcache guards have DOM unit coverage.
- [x] Private pre-migration backup retained under ignored `build/project-reporting/`.
  Applied only additive `0009_project_results.sql` to the existing production D1.
- [x] Deployed existing OpenFPVS Worker, preserving dashboard-managed domains,
  bindings, variables and secrets. Version: `cb4ee772-d663-49f5-9863-d9c258b5f18b`.
  Live checks confirm `/projects`, removed paragraph, private API 401, native Results
  access rejection, preserved Library routes and canonical alias redirects.
- [ ] Package/release the Studio integration. The user authorized Studio 2.4.0 on
  2026-10-07; packaging and publication evidence belongs in
  [the release plan](release-2.4.0.md). The current public installer remains 2.3.0
  until that release is published.
- [ ] Real two-machine study enrollment, presentation/metrics acceptance and shutdown
  cancellation remain operational checks. No real report, experiment or participant
  upload was used for verification; no production project grant was created.

The earlier standalone bridge/provisioning targets are superseded by the existing
OpenFPVS backend. The unresolved local capture-capacity limitation above remains
documented; uploaded-history archiving does not remove ineligible intent evidence.

Current review verification:

- `data-sharing` focused: 140 synthetic checks pass before the dependency-test fix.
  Approved visible `data-sharing` full tier after that fix: 153 pass, comprising
  141 unit checks and 12 native dialog checks. No offscreen Qt is used.
- Independent Worker tests: 20 pass; all six syntax checks pass.
- Safe GUI focused: 17 pass. Docs focused: 10 pass.
- Synthetic native layout review: 80 tab/state layouts at the minimum/default sizes,
  both themes, 125%/150% scaling, with opt-out/cancel actions; screenshots were
  inspected. A first partial-palette simulation was corrected before final inspection.
- First repo precommit: changed-file checks, mypy (224 files), repository audits and
  docs hygiene pass; 2,727 unit checks pass, 11 skip for Windows symlink privileges,
  and two unchanged import/save checks fail with Windows file-access interference.
  A short isolated recheck of both complete modules passes all 46 cases. No import
  or serialization source/test changes mask these failures; the locking process
  remains unproven.
- Second short-path precommit: 2,718 pass, 11 skip and 12 fail. Ten publishing
  failures are reproduced by the Windows enumeration edge above; one is the existing
  import rename access failure, and one reveals the previously hidden default Qt
  collection leak. All 61 isolated publishing/import/save checks pass in a shorter
  directory; the actual threshold reproduction and new path regressions establish
  the enumeration fix, rather than treating every failure as file locking.
- Windows enumeration follow-up: the original publishing dry-run plus six native
  path regressions pass; the bundle/import/save modules pass all 52 checks. A broader
  sandboxed publishing check encountered nine hardlink permission errors; the final
  project-I/O and repo gates run outside the sandbox without changing publication.
- Harness follow-up: 52 registry/import/driver/docs tests pass; configuration validates
  14 scopes and 42 registered Qt modules. No Qt objects are constructed by this gate.
  The next repo gate stopped before collection because its explicit `tests/unit`
  argument requested the newly registered QObject modules. The precommit driver now
  selects all non-Qt unit files explicitly, preserving the strict opt-in guard for
  registered Qt paths. Its regression checks full unit coverage and that the planned
  command does not request any registered Qt file; all 52 harness checks pass again.
  Project-I/O focused outside the sandbox: 286 pass, two Windows symlink-privilege
  skips. The final docs focused gate passes all ten checks.
- Final repo precommit on 2026-10-06 after the source and collection-boundary fixes
  passes: 2,710 unit checks, 11 Windows symlink-privilege skips, changed-file
  Ruff/compilation, mypy (224 source files), repository audits and docs hygiene.
  The previously failing publication/import/save checks pass in this full run;
  no hardlink, rename or serialization retry behavior was changed.

No Results deployment, provisioning or participant uploads are part of this review.

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
