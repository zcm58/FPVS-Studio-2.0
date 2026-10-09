# Complete the reporting lifecycle after uploads

Status: Completed

Date: 2026-10-07
Revised: 2026-10-08
Completed: 2026-10-08 (local implementation; rollout qualification remains below)

## Purpose and baseline behavior

Finish ordinary reporting work after each upload, recover offline deliveries at the
next connected Studio startup, and keep Cloudflare contributions small. The user
selected this narrower direction instead of a capacity-management feature. This is
a user-approved implementation plan as of 2026-10-08. Current behavior remains in
[Data sharing](../../DATA_SHARING.md).

Before this implementation, the two 512-record limits applied separately to active
captures and outbox records in each local project folder. Successful uploads occupied
those collections until manual **Archive uploaded history** ran. The archive operation retains
the latest acknowledged report per project/experiment/version/protocol and preserves
receipts and finalized capture evidence. Project opening and session completion
already retried opted-in pending reports; startup did not check every known project.

## Intended user experience

1. An opted-in completed session is committed locally and queued, then uploaded in
   the existing background worker. Recording never waits for internet access.
2. If delivery cannot connect, retain the exact queued report and show a local
   **Waiting for connection** status and pending count in the existing sharing view.
   Distinguish service/authentication/quota errors from connectivity failures; an
   uncertain failure must not be presented as proven offline collection.
3. On the next connected Studio launch, automatically retry eligible pending records
   for known local projects, including projects the user does not reopen. Show
   non-modal delivery status; do not require opening the sharing dialog or clicking Retry.
4. After a matching receipt is durably saved, retire older acknowledged records and
   matching finalized captures through the existing local archive operation. Keep
   the latest local comparison evidence and leave research exports and cloud totals intact.

Use existing pending state, attempt timestamps and network/timeout error codes for
offline delivery flags where sufficient. Any additional delivery metadata stays
local and versioned. Preserve original completion times, report UUIDs, payload bytes
and enrolled scopes; offline sessions must not become new reports dated at upload time.
Clarify that the current Uploaded count represents active local caches, not lifetime
cloud contributions, when automatic retirement changes that count.

## Startup retry and lifecycle boundaries

- Run one bounded, app-owned background startup pass after root preferences are ready.
  Reuse known-project discovery under the configured root and remembered project paths;
  do not scan arbitrary disks, construct authoring windows or load PsychoPy. Process
  projects sequentially and skip projects with no pending work or relevant history.
- Recheck per-project opt-in, registered scope, Library provenance and native credentials
  before sending. Never auto-enroll, opt in, or release held/opted-out records. Missing
  credentials, revoked access, protocol conflicts and non-retryable failures need attention.
- Reuse the existing delivery path without fetching comparison snapshots for every
  unopened project. Startup drains pending work; comparisons refresh when the current
  project/view needs them. This avoids extra cloud requests and aggregate-history reads.
- Use a bounded request to the actual Results service to establish delivery availability;
  avoid a separate internet-ping service or recording-time network probe. Permit one
  prompt startup retry of network/timeout-delayed pending work while respecting service
  throttling and existing retry limits. If still offline, keep evidence for a later cycle.
- Preserve launch/shutdown cancellation and the existing rule that background requests
  stop before presentation. Share job ownership with after-run/project-open retries so
  startup cannot create a competing uploader or continue during another project's run.
- Reuse archive cleanup at startup to retire pre-change acknowledged history before
  recovery/queue capacity checks. Cleanup failure must preserve accepted status and
  receipts, report the local problem, and resume on a later bounded cycle. It must not
  turn an accepted upload into a failed/pending report or change cloud totals.
- Protect pending, held, failed, running, uncommitted and malformed evidence. Ordinary
  aborted/ineligible captures remain retained; their separate review/archive workflow
  is deferred. This plan does not promise unlimited offline backlog or total history.

## Lightweight Cloudflare storage

Keep the existing strict summary-only report: enrolled scope, report UUID, original
completion time, Studio version and condition-occurrence fixation counts/RT provenance.
Participant identity, demographics, raw responses, EEG, logs, stimulus files, local
archives and offline flags remain local. Preserve separate occurrences and valid
denominators. Do not reduce precision or drop scientific provenance to save bytes.

Reuse compact JSON and the existing Worker/D1 owners. Backend source stores one exact
accepted payload with receipt/idempotency metadata; avoid additional payload copies,
body logging, per-retry rows or cloud uploads of local capture/archive files. Identical
retries must reuse the same UUID/digest and produce no new retained report or totals.

Before selecting any wire/schema optimization, measure representative small and large
reports, including repeated conditions, and actual synthetic SQLite/D1 growth with
indexes and metadata. Report bytes per session, stored bytes per session, read/write
work, and projected capacity at 100, 500 and 1,500 sessions. Remove demonstrably
redundant storage/serialization only when the savings justify the change. Any field
removal needs a reviewed versioned contract and old-report compatibility, not silent
changes to schema 1.0. Do not introduce compression infrastructure or another storage
provider without measured need.

Cloudflare reference limits checked 2026-10-08:

- [D1 Free limits](https://developers.cloudflare.com/d1/platform/limits/): 500 MB
  per database and 5 GB across the account. The existing shared OpenFPVS database's
  per-database ceiling matters before the account total; portal data and indexes consume space too.
- [D1 Free pricing allowances](https://developers.cloudflare.com/d1/platform/pricing/):
  5 million rows read and 100,000 rows written per day. Size optimization must also
  avoid full-history scans or extra write work on every retry/startup.
- OpenFPVS backend source additionally defaults each project to 2,000 reports,
  8 MiB of exact payload bytes and 100,000 occurrences, with smaller shared lab/service
  budgets than Cloudflare's total allowance. Local archiving does not free that storage.
  The read-only production snapshot confirmed these deployed project defaults, a
  368 KiB shared database and 568 KiB across three visible databases. No results
  projects/reports existed at inspection. Billing tier was not exposed, so remaining
  included capacity is conditional on that tier. See [Storage measurements](../../REPORTING_STORAGE.md).
  No paid resource, quota increase, cloud deletion or migration is authorized by this revision.

## Owners and implementation sequence

1. Map current receipt finalization, startup/project discovery, pending/error states,
   scope checks and source-defined cloud quotas. Record baseline size/capacity estimates
   with synthetic fixtures and resolve any necessary local delivery metadata.
2. Reuse `data_sharing/storage.py` and `service.py` to finish acknowledged-history
   retirement in the existing upload flow, preserving receipt-first ordering, latest
   comparison evidence, guarded project paths and resumable partial archive moves.
3. Extend `gui/controller.py` and `data_sharing_controller.py` through their app-owned
   jobs for one startup pass, prompt offline retries and existing-view status/counts.
   Core/runtime continue owning eligibility, capture proof and neutral results.
4. Apply only measured storage/payload improvements through Studio's canonical wire
   owner and sibling OpenFPVS's `PROJECT_REPORTING.md`, `src/results/` and migration
   owners when necessary. `services/results/` is an undeployed reference, not production.
5. Update canonical sharing/startup documentation when behavior lands. Keep this plan
   in `active/` during implementation; move to `completed/` after local acceptance,
   recording any outstanding visible/service qualification separately.

## Acceptance and verification

- At least 1,500 synthetic acknowledged sessions retire old active history without
  changing exact archived evidence, research files, latest comparison or server totals.
- Eligible sessions captured offline survive exit; the next connected startup uploads
  them automatically without reopening their project. Cover multiple known projects,
  absent/moved roots, two independent PC roots, continued offline operation and opted-out scopes.
- Existing manual Retry, opt-out/held rules, live scope authorization and completion
  eligibility remain intact. Startup distinguishes waiting-for-connection from access,
  protocol, quota and local-storage errors and never invents missing captures.
- Lost HTTP acknowledgments, receipt writes, every archive move, restarts, cancellation
  and overlapping jobs cannot duplicate contributions or erase unfinished evidence.
  Use fake clients/synthetic roots; verify shutdown and presentation start stop network work.
- Pending/held/failed/aborted/ineligible records survive cleanup; no silent drop occurs
  at genuine offline capacity. Successful history retirement is not terminal-capture cleanup.
- Record actual wire/storage budgets and limiting project/lab/database quotas. Uploads
  contain only allowlisted summaries; duplicate retries add no report rows or totals.
  Verify mixed RT provenance, repeated occurrences and weighted aggregates remain exact.
- Run affected `data-sharing`, `runtime`, `project-io` and safe `gui` focused routes,
  then repo precommit. Register GUI status/job coverage; Qt execution requires an
  approved visible environment. OpenFPVS changes use its own synthetic tests/checks.
- Before rollout, verify a synthetic two-PC offline/restart/connected-delivery sequence
  in an approved service environment. Local mocks do not establish live cloud acceptance.

## Exclusions

No new housekeeping dashboard, capacity-threshold manager, general connectivity monitor,
terminal-capture review UI, participant numbering, Toolbox reporting, raw-data uploads,
historical export backfill, timing/scoring/trigger changes or paid cloud services.

## Implementation record: 2026-10-08

- `data_sharing/service.py` invokes existing guarded archive cleanup before recovery
  and after durable upload receipts. Older accepted reports and finalized capture
  mappings retire locally; the latest acknowledged report per scope stays active.
  Interrupted capture/outbox moves resume without another accepted submission.
- `core/project_service.py` owns shared cancellable project discovery. The app starts
  one sequential reporting pass under the configured root and remembered existing
  paths. Discovery, saved-project loading, hashing, credentials and HTTP run in
  app-owned background jobs. The pass uses the existing launch/shutdown gate and
  resumes canceled projects after higher-priority project/presentation work.
- Startup preserves opt-in, held/failed reports, installed Library identity and
  immutable UUID/payload/completion times. Open projects use the existing captured
  authored document, including unsaved edits, rather than stale saved protocol state.
  Unopened projects submit without comparison requests; projects with no relevant
  pending/recoverable work skip hashing and HTTP.
- Network/timeout failures retain pending work and show **Waiting for connection**.
  One startup retry can bypass connectivity backoff. Service throttling retains its
  delay. A validated `project_storage_limit` response is saved as non-retryable
  capacity attention, with explicit Retry available after administrator resolution.
- Welcome and the existing status bar show passive startup status. The existing
  sharing view labels its active cache **Retained uploaded** and explains local
  retirement. No capacity dashboard, polling service or new cloud data was added.
- [Storage measurements](../../REPORTING_STORAGE.md) and the reproducible synthetic
  SQLite script cover 1, 12 and 120 occurrences at 100/500/1,500 sessions. A repeated
  12-occurrence report is 3,375 wire bytes and about 4,377 stored bytes at 1,500 rows
  including metadata/indexes. Measurements did not justify compression or wire
  field/precision changes. No sibling backend source, schema or resource changed.

## Local acceptance and remaining qualification

- A separate durability test passed for 1,500 sequential acknowledged sessions,
  using real atomic writes, locks and archive moves. It verifies 1,499 exact archives,
  one active latest report, preserved receipts/captures/research files and 1,500
  unique simulated server contributions. Runtime: 498.91 seconds. This already-passed
  stress case is deselected in repeated focused/precommit runs.
- Focused runtime: 567 passed / 2 Windows symlink-privilege skips. Project I/O:
  317 passed / 2 equivalent skips. Safe GUI route: 17 passed. Documentation:
  10 passed. Final data-sharing route: 174 passed / one stress-case deselection.
  Startup coordinator tests cover discovery, multiple/missing roots,
  unsaved edits, opt-out, cancellation, project switching, presentation and shutdown.
- Receipt-write and both archive-move failures preserve exact identity/evidence and
  accepted state. Two independent synthetic PC roots retain offline work across
  client restart and deliver unchanged reports when their fake service reconnects.
  Quota-attention and ordinary throttling are separately covered.
- The final repository precommit gate passed 2,872 non-Qt tests, 20 subtests, 11 Windows
  symlink-privilege skips and one stress-case deselection, plus Ruff, compilation,
  mypy (228 files), harness configuration/GC and documentation checks. This includes
  the final quota-response distinction. Runtime: 519.04 seconds.
  Concurrent unrelated project-submission edits appeared during this run and were
  preserved; this task does not qualify that separate feature's final source state.
- Before commit, lifecycle changes were staged separately from concurrent dialog
  copy/layout and project-submission work. The exact exported index passed 211
  selected non-Qt reporting/project/discovery/documentation checks, with the already
  passed stress case deselected, plus changed-file Ruff, compilation and mypy (228
  files). The committed dialog keeps its existing layout and adds retained counts;
  the concurrent compact-dialog revision remains in the working tree. The isolated
  checks used a short explicit fixture path to avoid Windows raw-path limits.
- Registered Qt coverage was added for offline/retained counts and Welcome status
  at minimum/default sizes. No local Qt/offscreen run was performed; current visible
  layout and native worker cancellation qualification remain pending an approved
  visible environment. No experiment/hardware run occurred.
- Live synthetic two-PC offline/restart/delivery, lost-response deduplication and
  D1 billed read/write qualification remain rollout checks in an approved service
  scope. Read-only production inspection establishes neither live delivery acceptance
  nor the account billing tier. No release/deployment/live submission was performed.
- Automatic approval review rejected exact-file cleanup of a 56 KiB synthetic SQLite
  fixture in Windows Temp with "blocked by policy". The fixture was left intact;
  subsequent benchmark runs close their databases and clean their own temporary files.

The 512 limits still protect genuine unfinished/offline backlog per local project.
Cloud project budgets combine enrolled machines. Terminal-capture review remains
deferred and local archives do not free accepted cloud storage.
