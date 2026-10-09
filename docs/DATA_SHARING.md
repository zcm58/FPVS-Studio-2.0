# Private experiment data sharing

FPVS Studio can contribute fixation-task summaries for an enrolled experiment and
compare its latest eligible local session with compatible shared results. Sharing
is off by default. OpenFPVS owns the private lab project dashboard and the
`/results/v1` service in the sibling `../OpenFPVS` repository. Its canonical backend
contract is `PROJECT_REPORTING.md`. The integration is included in the published
Studio 2.4.0 Windows installer, and the existing OpenFPVS backend is activated.
Packaging evidence and operational check boundaries are in the
[2.4.0 release record](exec-plans/completed/release-2.4.0.md).

## Operator workflow

An administrator creates a private project in **OpenFPVS > Projects**, selecting
the lab and immutable experiment ID, version and protocol fingerprint. Studio's
**Copy protocol fingerprint** action supplies the actual authored/asset hash.
For a Library-linked experiment, use its installed item ID and version.

Open **View > Data Sharing & Comparison** in the active experiment. Enter the
existing lab code and the website's **OpenFPVS project ID**, choose **Connect**,
then ask the administrator to approve a new results enrollment on its project page.
Reconnect with the same code/project after approval;
review the registered study, version and field list through the study-title and sharing
checkbox tooltips, then enable **Automatically share completed sessions**. Connecting alone does not enable
sharing or upload history. **View OpenFPVS project** opens the private dashboard.
Locally authored experiments can enroll without a Library download. A Library
view/download grant alone does not authorize reporting: the lab needs an explicit
project grant, and Results credentials remain separate from Library credentials.

After a completed session, Studio saves its research records and queues the report.
An application-owned background job submits it. Project opening, session completion
and opening the sharing dialog can retry opted-in pending reports; temporary
failures use bounded backoff. The controller schedules at most four automatic
follow-up retries per cycle. **Retry pending** explicitly releases held reports in
the current registered scope. Authentication, schema, version and digest conflicts
require operator attention. Closing the dialog cancels its current operation.
Starting a Home or Setup launch cancels background reporting and waits asynchronously
for its bounded request and any noncancelable local opt-out persistence to finish
before starting runtime work. An in-flight request
may already have reached the service; no new request starts during presentation.
Projects that have never enrolled and leave sharing off skip protocol hashing and
network access. Enrolled protocol hashing checks cancellation between asset chunks
so a canceled reporting job can release the launch gate promptly.

On Studio startup, one sequential background pass discovers projects beneath the
configured root and checks remembered existing project paths. It retries eligible
pending deliveries without reopening projects or retrieving their comparison
snapshots. Projects without pending/recoverable work skip hashing and HTTP. Saved
opt-in, Library scope, authored protocol and OS credentials are rechecked before
delivery. Held reports still require explicit Retry. Missing/moved projects are
skipped; malformed metadata remains intact and produces non-modal attention status
and a log identifying the affected project. Startup shares the same job ownership
and launch/shutdown gate as project-open and after-run work, and resumes interrupted
projects after the presentation cycle.

Failed delivery with local `network`/`timeout` codes shows **Waiting for connection**
and retains the exact report and original completion time. Startup permits a prompt
retry of that connectivity-delayed work; throttling/service backoff remains in place.
The actual Results request tests availability, without a separate internet probe.
This flags failed delivery, not proof that acquisition itself occurred offline.
If the service reports that the project/lab storage budget is full, Studio retains
the contribution with a persistent needs-attention message. The administrator must
review capacity before **Retry pending**; automatic startup does not repeatedly send
that failed report. Ordinary rate throttling retains its retry backoff.

Turning sharing off stops new uploads and holds unsent reports. Turning it back on
does not silently release that backlog. The off setting is committed before outbox
review; malformed records remain intact and prevent re-enabling until resolved.
The bounded local opt-out job survives dialog closure, project switching and app
shutdown. Upload cancellation cannot discard the requested opt-out.
**Revoke access** disables local sharing
and revokes the enrollment; accepted reports remain with the owner. Reconnection
requires a lab invitation. If access was already rejected or the copied project's
OS credential is missing, Revoke access can clear the unusable local enrollment
and allow reconnection; previously received records remain. An offline/other revoke
failure preserves the profile with sharing disabled for an explicit retry.
Sharing failures change the reporting status and preserve
local research results.

The service origin defaults to `https://openfpvs.com`. An explicit
`FPVS_DATA_SHARING_SERVICE_URL` override must be one HTTPS origin without credentials,
paths, queries or fragments; an empty value disables online operations. The desktop
uses `/results/v1` and rejects redirects. Configuring an origin does not provision
the service or activate sharing.

## Experiment and protocol identity

The service registers an immutable experiment ID, version and protocol SHA-256.
Folder names and local project IDs do not identify a shared study. The OpenFPVS
project UUID selects the lab's study, allowing separate projects to use the same
protocol without mixing their results. Enrollment and every submission are scoped
to that project and registered identity. A changed protocol requires a new approved
project scope; earlier reports retain their original scope.

Local outbox records retain their original OpenFPVS project UUID. Reconnecting to
another project with the same protocol cannot release or send the earlier project's
reports. Older unscoped records stay held when connected to a website project.
This local metadata does not change the uploaded report envelope.

For an experiment with a native Library origin receipt, the Results experiment ID
must equal its Library `item_id`, and the Results version must exactly equal its
`installed_version`. `data_sharing/library_scope.py` checks that association before
enrollment, ordinary capture, sending and comparison. Linked enrollment requests
include both expected identity fields, so the Worker can reject an invitation for
another item or version before creating a device enrollment. An unknown installed
Library version requires review; Studio does not guess it from the project name or
the available catalog version. A mismatch holds reporting and preserves local runs.
Standalone authored experiments without a Library receipt retain the scope supplied
by their approved OpenFPVS project; a Library download is not a prerequisite.

`core/data_sharing.py:protocol_fingerprint` hashes authored protocol, condition,
task, fixation, presentation and stimulus settings, template identity, and actual
bytes of the selected stimulus variants and referenced task media. It uses the
compiler's existing manifest/filesystem path resolver; unrelated files and
unselected image variants do not enter asset provenance. Actual selected assets are
hashed in chunks, so editing a file without updating the manifest changes the hash.
Local project identity, dates, participant electrode bookkeeping, random seeds and
machine connection/display geometry fields are excluded.

The GUI supplies the actual authored fingerprint as a runtime-only launch option,
only for the document's current compiled session plan. A stale compiled plan can
still run locally but cannot be labeled with an edited document's sharing protocol.
Runtime snapshots it with the enrolled profile before presentation. A mismatch,
missing fingerprint or later project edit holds upload eligibility while local
execution remains available. Reports are never relabeled to a newly registered
version. `RunSpec`, `SessionPlan`, project JSON, config exports and bundles contain
neither sharing activation nor credentials.

With automatic checks enabled, Library-linked projects check for new experiment
versions on open. The version review
warns about changing an ongoing study and offers keeping the current version or
downloading a separate project for inspection. Keeping the current version preserves
its enrollment and reporting scope. The new copy needs its own enrollment and explicit
opt-in; an available update never relabels earlier reports or changes conditions.
See [Project version checks](EXPERIMENT_LIBRARY.md#project-version-checks).

## Private OpenFPVS project reporting

The existing OpenFPVS Worker and D1 database own dedicated project, device, report
and quota tables. No additional storage provider is required. `/results/v1` is
separate from the Library's native API and retired `/v1` routes. Enrollment checks
the live lab code, explicit project grant, installed Library identity when present,
and actual protocol. Lab-code or project revocation immediately blocks enrollment,
intake, receipts and comparison. Completing a project pauses new reports; reopening
resumes intake. Received reports stay with the owner.

Only the lab's authenticated browser session and the administrator can view a
project. `/projects` lists authorized projects; `/projects/<UUID>` shows Ongoing or
Completed status, completed-session totals, reporting enrollments, latest report
time, and pooled fixation counts, accuracy and response time by condition. Opening,
reloading or restoring the page reads fresh, non-cached aggregates. Failures clear
the displayed results and offer a retry rather than displaying stale totals.

Session counts are not unique participant counts. Repeat visits count separately,
and only newly completed eligible sessions reported after opt-in contribute. The
dashboard does not expose raw report envelopes or participant identities. Toolbox
summary spreadsheets and public result publication are deferred.

`services/results/` remains an undeployed standalone reference and synthetic wire
fixture source. Production backend changes and tests belong in `../OpenFPVS`,
where `PROJECT_REPORTING.md` documents administration, retention and activation.

## Completion and crash recovery

Automatic capture applies to ordinary multi-condition session launches, including
single-occurrence sessions. The standalone stream-only `RuntimeWorker.execute`
entry point does not queue a report. V1 requires a positive planned condition count,
every planned occurrence in order, full stream frame counts, all pre/post tasks
complete and no session abort, including a completion-screen abort. Test Mode,
Pilot Mode and reserved participant IDs `0` and `00` stay local. Runtime checks the
actual launch flags and skips these known local-only launches before writing capture
intents or consuming the 512-record capture capacity. Historical execution-mode
metadata is not the gate. Terminal proof validation still rejects test executions
when reading existing capture records.

The local sequence is the same in full and compact export modes:

1. Before presentation, persist an explicit capture intent with a fresh report UUID,
   registered profile, actual protocol, launch flags and private local join references.
2. After presentation/tasks/cleanup, before research finalization, persist the
   terminal eligibility decision and exact allowlisted report candidate.
3. Commit the existing research records: condition history, compact task rows when
   applicable, and finalized native attentional-blink records. Full artifacts remain
   in their ordinary output directory.
4. Verify the numbered condition-history rows, persist an explicit research-commit
   marker and evidence digest, and atomically queue immutable report bytes.
5. Generate the derived participant workbook and discard successful recovery
   checkpoints through the existing runtime workflow.

A workbook failure after step 4 cannot remove the queued report. An earlier research
write failure cannot make a report eligible for submission. Capture/queue failures
produce logging and actionable status without replacing a runtime error or blocking
local research finalization.

Recovery considers explicit capture intents only. It requires eligible terminal
proof, the persisted research-commit marker and matching committed condition-history
evidence. Rows alone never imply a successfully finished execution. A crash after
research writes but before the commit marker leaves a capture requiring review;
Studio conservatively holds it instead of inferring completion. An eligible committed
capture interrupted during queuing reuses the same UUID and bytes. Enrollment does
not backfill historical results.

## Private wire contract

`core/data_sharing.py` owns strict Pydantic models with unknown fields forbidden.
The Worker independently validates the same contract. The report contains exactly:

| Envelope | Meaning |
| --- | --- |
| `schema_version` | `"1.0"` |
| `report_id` | Canonical UUID generated for this execution |
| `experiment_id`, `experiment_version`, `protocol_sha256` | Immutable enrolled scope |
| `completed_at`, `studio_version` | UTC completion time and Studio release |
| `occurrences` | Ordered, distinct condition occurrences |

Each occurrence contains `condition_id`, one-based `occurrence_index`,
`total_targets`, `hit_count`, `miss_count`, `false_alarm_count`, `accuracy_percent`,
`mean_rt_ms`, `rt_count`, `scoring_source` (`timestamps` or `frames`), `refresh_hz`
and `response_window_ms`. Repeated conditions retain distinct occurrence indices.
The local scoring labels `hardware_timestamp` and `frame_fallback` map explicitly
to those wire values. Mixed provenance within an individual occurrence requires
review; legitimate differences between occurrences remain in the stored report.

Counts conserve targets: hits plus misses equal targets. Accuracy is
`100 * hits / targets`; it is null when targets are zero. False alarms remain a
separate count. Mean RT comes from existing hit scoring and is null exactly when
the RT observation count is zero. RT observation count cannot exceed hits.
Disabled fixation tasks produce zero counts and null accuracy/RT. No composite
attention score or EEG quality inference is introduced.

Reports contain no participant numbers, names, demographics, hostnames, paths,
raw keypresses, questionnaire answers, logs, stimulus files or EEG. Stream/task
completion flags and participant-to-report mappings remain in private local
capture evidence. The remote endpoint still receives completion timestamps and
an authenticated enrollment link; these summaries are private research data,
not an anonymous public dataset.

Reports are bounded to 128 KiB, 1–4,096 occurrences and at most 512 distinct condition
IDs. Per-occurrence integer counts are bounded to 1,000,000; booleans cannot stand
in for counts. Refresh rates are 1–1,000 Hz and RT/window values are 0–600,000 ms.
Nonfinite numbers, malformed UTC timestamps and inconsistent metrics are rejected.
The Worker also rejects duplicate JSON object keys, including escaped-equivalent
keys, so its validated fields and D1's aggregate interpretation cannot disagree.
Oversized data is retained for review rather than truncated or acknowledged.

The service commits immutable bytes before issuing a receipt containing report ID,
scope, SHA-256 and UTC receipt time. Same ID and bytes return the existing receipt;
conflicting bytes return a conflict. The desktop persists an attempt before sending
and records Uploaded only after validating that receipt. A lost response never
causes creation of a replacement UUID.
Enrollment inserts atomically recheck invitation expiry and invitation/version
revocation. Report inserts atomically recheck device/version revocation after
authentication; a revoke during that interval prevents a new report commit.

## Descriptive comparison

The local column pools repeated occurrences within the latest eligible captured
session for the current scope, including a pending or held report. It is not an
aggregate of all local participants or a new analysis-inclusion decision.

The reference column uses only the matching experiment/version/protocol and always
excludes the requesting enrollment's reports. Each condition requires at least ten
distinct report sessions from three other enrolled devices. These are report and
credential/enrollment counts, not unique-participant counts or proof of independent
people. Zero-target observations do not contribute to the reference denominator.

Reference conditions with insufficient counts or mixed scoring sources/response
windows expose no performance metrics. Eligible reference conditions carry their
scoring source/window; Studio also suppresses comparison when these differ from
the latest local condition. The response retains cohort counts when metrics are
suppressed; the GUI shows eligible denominators and a threshold notice when the
reference cohort is unavailable.
Accuracy uses pooled hit/target counts. RT uses observation-weighted means,
`sum(mean_rt_ms * rt_count) / sum(rt_count)`, with null RT for no-hit cohorts.
This supports descriptive comparison, not a participant-level repeated-measures
test, a population norm or causal inference. Contributors cannot retrieve other
devices' individual reports.

## Local persistence and credentials

| Project-local path | Purpose |
| --- | --- |
| `.fpvs-data-sharing/settings.json` | Bounded local profile and explicit opt-in |
| `logs/data-sharing/intents/<UUID>.json` | Private launch, completion and commit proof |
| `logs/data-sharing/outbox/<UUID>.json` | Immutable report JSON/digest, attempts, state and receipt |
| `logs/data-sharing/archive/<UUID>/report.json` | Archived acknowledged record |
| `logs/data-sharing/archive/<UUID>/capture.json` | Finalized private mapping or reviewed excluded capture evidence |

Files stay beneath the active project root, reject links/reparse points and require
private regular files. Settings are bounded to 16 KiB, each intent/outbox record to
256 KiB, and each active collection to 512 records. Reads reject malformed data
visibly; no pending report is silently skipped or discarded. Recovery reads at most
64 MiB of committed condition history. Atomic replacements and the existing project
reporting lock preserve writes across threads/processes.

Credentials use Windows Credential Manager or Linux Secret Service in a dedicated
Data Sharing namespace, scoped to origin, project path and protocol. Enrollment
codes are not saved in project files. A token is stored before enrollment so an
ambiguous response can retry the same identity. Library credentials are not reused.
A copied project requires its own secure-store enrollment on the destination.

After each matching receipt is durably saved, automatic cleanup moves older acknowledged
outbox records and matching finalized intents to the guarded archive, retaining the
latest uploaded report for each OpenFPVS project/experiment/version/protocol in the active outbox.
Pending, held, failed and unfinished captures remain active. Receipt and local
participant-to-report evidence are preserved for audit; raw research exports and
the shared dataset are unchanged. Every selected source/schema/destination is
validated before file moves; existing targets are never overwritten. A partial
move remains recoverable and resumes on a later cleanup cycle. Cleanup also runs
before startup recovery to retire pre-change acknowledged history. A cleanup error
preserves accepted status/receipts and reports a local problem; it does not cause
another submission of an acknowledged record. Active capacity counts ignore
archived files. **Retained uploaded** counts the active local cache, not lifetime
cloud contributions. **Archive uploaded history** remains an explicit local retry
and performs no HTTP request.

Reports already use compact JSON and one exact cloud payload per accepted session.
[Storage measurements](REPORTING_STORAGE.md) record representative wire/SQLite
sizes, the read-only D1 snapshot and source-defined project/lab/service budgets.

The sharing dialog displays active capture capacity against the 512-record limit.
At capacity it reports an actionable local error while experiment execution remains
available. **Review captures…** reads a bounded snapshot of terminal excluded
captures and their reason counts without HTTP. After explicit confirmation, it
archives only those unchanged records with an exclusion reason and no outbox report.
The reviewed project, UUIDs, contents and guarded destinations are revalidated under
the reporting lock before moves. New or changed evidence requires another review;
existing archive targets are never overwritten. Running, eligible and finalized
captures, every pending/held/failed report and accepted receipts remain protected.
Excluded evidence moves to the private archive without changing research exports or
the shared dataset. **Archive uploaded history** continues to retire accepted report
pairs independently.

## Maintainer setup

Save the reviewed experiment first. From the repository root, obtain the same
fingerprint used by Studio without presentation, network access or enrollment:

```powershell
$env:FPVS_PROTOCOL_PROJECT = 'C:\path\to\the\experiment'
@'
import os
from pathlib import Path
from fpvs_studio.core.data_sharing import protocol_fingerprint
from fpvs_studio.core.paths import project_json_path
from fpvs_studio.core.serialization import load_project_file

root = Path(os.environ["FPVS_PROTOCOL_PROJECT"])
project = load_project_file(project_json_path(root))
print(protocol_fingerprint(project, root))
'@ | & .\.venv3.10\Scripts\python.exe -
```

The loader applies normal in-memory project migrations; this command does not save
the project. It requires the selected image variants and referenced task media to
exist. Register the reviewed hash/version and a hashed high-entropy invitation
through [the standalone service registration procedure](../services/results/README.md#registration-and-enrollment).
For a linked experiment, use the receipt's exact Library item ID and installed
version; for a standalone authored experiment, use its reviewed registered identity.
The registration script emits SQL for review and does not deploy or execute it.
Resolve owner access, private-data retention/deletion, backups, research approval
and current Cloudflare capacity before authorizing a live installation.

`services/results/` owns Worker/D1 enrollment, intake, receipts, revocation and
aggregate comparison. It has separate credentials and deployment from Library
and Feedback. Public publication, raw EEG upload, researcher dashboards, owner CSV
exports and longitudinal joins are future work.

## Verification and remaining acceptance

Use the `data-sharing` focused route for neutral contracts, local storage, runtime,
fake HTTP and shared wire fixtures; run repo precommit after cross-layer edits.
Run the independent Worker's synthetic Node SQLite tests separately as described
in its README; the Python harness does not run those tests.
The GUI route excludes Qt locally. Registered GUI tests and source checks do not
confirm real layout or live service acceptance.

```powershell
./scripts/verify.ps1 -Scope data-sharing -Tier focused
./scripts/verify.ps1 -Scope gui -Tier focused
./scripts/verify.ps1 -Scope docs -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

The earlier user-approved synthetic native layout check passed at `820x620` minimum and
`880x700` default in both themes, at 125% and 150% scaling. It checked both tabs,
long profiles/condition labels, empty/ready/busy/error/validation states, and explicit
opt-out and cancel actions. No controller, HTTP client, presentation or hardware is
instantiated. Request lifecycle checks with project switching and application shutdown
remain separate end-to-end acceptance. Registered Qt tests require a user-approved
safe visible environment; never use local offscreen Qt.

The compact dialog now uses `820x480` minimum and `880x540` default. Registered tests
cover those sizes, including offline status, full-value tooltips and concise comparison
notices. This revised layout has not yet had an approved visible check. See
[GUI workflow](GUI_WORKFLOW.md#private-experiment-sharing) for the manual smoke path.

Live acceptance remains pending: authorize and provision an isolated Results
Worker/D1 scope, enroll two or more machines with synthetic sessions, check exported
metrics and lost-response deduplication, prove credential-scope rejection and build
the required aggregate cohort without real participant data. No claim of live
multi-machine acceptance follows from local tests. The read-only database snapshot
in [Storage measurements](REPORTING_STORAGE.md) does not establish the billing tier,
included remaining capacity or synthetic live delivery acceptance.
