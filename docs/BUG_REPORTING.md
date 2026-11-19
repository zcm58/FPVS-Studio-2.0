# Bug reporting

## Feature requests

Help > Request a Feature opens a single-column editor at minimum 620x440 and
default 700x480. The writing prompt appears inside the empty editor, with a live
4,000-character counter (Unicode code points) below it. Copy Request and Save
Request are available. Over-limit pasted text remains editable;
Submit Request is disabled until shortened. Online submission remains disabled
until service activation. Feature requests never collect logs or include OS,
email, project or participant data.

Feature drafts reuse atomic worker persistence and seven-day/five-draft retention
in the separate app-local `support/feature-drafts/` directory. Submit Request
uses feature-only intents and uploads without opening a browser. A confirmed service
receipt triggers a 300 ms button transition when system motion is enabled, with
delivery status available separately. Receipt locking, cancellation and status
checks reuse the existing protocol. Bug reports retain browser verification.

The `/v1/feature-reports` endpoint and the legacy verified route accept this feature payload:
`schema_version: "1"`, `kind: "feature"`, `report_id`, `created_at`, `app_version`,
and `description` (the text box). No other fields are sent. Bug payloads omit `kind`
and retain their existing bytes. Intent hashes bind the exact payload and kind.
The service must enforce 1–4,000 characters, reject whitespace-only requests, and
enforce a 32 KiB complete UTF-8 JSON limit. Count Unicode code points, not JavaScript
UTF-16 code units. Generate a private GitHub issue title from the description and
label it `enhancement`. Server rate and retention limits must cover both report
kinds together; character limits alone do not guarantee free-tier usage.

Visible acceptance: open both report types, paste 4,000 emoji then one extra
character, check counter/submission state, shorten and copy/save, close/reopen
both drafts, and check light/dark layouts at both documented sizes. Registered
Qt tests cover loading, verification, sending, receipts and independent draft
persistence. Local Qt execution remains opt-in; no live service is used.

## Platform automatic error and crash reporting

This is the shared contract for FPVS Studio and FPVS Toolbox. The automatic
Mac repair completion report is the reference for environment detail and email
format. Studio first shipped narrower crash capture and recovery in 2.4.2.
Mac repair workflow and schema-2 desktop incident intake are live. Expanded capture
is implemented in Studio and Toolbox source. Installed clients need a build that
includes those changes.
See the [automatic-crash plan](exec-plans/active/automatic-crash-reporting.md)
for build, staging, and activation evidence.

### Which incidents are reported

- Report unexpected internal application errors that interrupt an action, including
  failures handled at an app or worker boundary. Expected validation, routine
  warnings, ordinary connection problems and user cancellation stay local.
- Recover eligible native faults and unexpected exits on the next launch. Record
  **Unclean shutdown** when there is insufficient evidence to identify a crash.
  Clean exits, healthy processes and reporting-service failures stay out of intake.
- An error and a later fatal exit produce one report when the app can correlate
  them to the same incident. Use the strongest evidence before queueing. After
  queueing, preserve the report ID and exact payload, including during recovery,
  retries and receipt checks. Distinct incidents may be reported within the budget.

### Machine context and error summary

Capture allowlisted facts from the affected app and session. Use bounded OS queries
and installed version metadata outside the UI, acquisition and fault-handler paths.
Cache these facts for crash recovery so a later app or OS update cannot change the
reported environment. Omit optional facts that cannot be read reliably. A missing
GPU model or other optional field never blocks the report.

| Field | Contents |
| --- | --- |
| App | FPVS Studio or FPVS Toolbox and the actual running version. Include the build when available. |
| Operating system | OS family and full OS-reported version, for example macOS 27.0. Include the OS build when available. |
| Computer | Non-unique hardware family or model, such as MacBook Pro, when available. |
| CPU | CPU architecture and non-unique vendor/model when available. Include process architecture or translation mode when it helps explain a mismatch. |
| GPU | Model names of adapters reported by the OS when available. Use the OS inventory without creating a graphics context or loading a driver to probe it. |
| Memory | Total installed RAM in GiB, rounded to the nearest whole GiB, when available. |
| Relevant software | Allowlisted version pairs for implicated dependencies such as Python, Qt, PsychoPy, NumPy or SciPy. Use the versions the app is running with when known. |
| Incident | Random report UUID, failure category, failed operation from an app-defined list, and a short redacted error summary. Record the UTC occurrence time when known. Otherwise label the recovery time as such. Include a bounded excerpt of sanitized package-relative module/function/line locations when available. |

Build the summary from an allowlisted failure type, operation and safe diagnostic
facts. Include at most 40 sanitized frames and replace external source locations
with `<external>`. Omit any detail that cannot be safely extracted. Exclude raw
exception messages, full logs, dumps, attachments, absolute paths, hostnames,
usernames, email addresses, serial numbers, unique hardware or network identifiers,
credentials, environment dumps and participant, project, stimulus and EEG data.
Cap the complete UTF-8 upload envelope at 32 KiB, including receipt metadata.

### Preference, delivery and receipt

- Settings > Diagnostics is app-local. Automatic error and crash reporting defaults
  on for fresh installs. Preserve saved off choices across upgrades, disclose the
  expanded fields before the first expanded capture, and recheck the active
  preference generation before capture and delivery. Opt-out stops new automatic
  report capture, discards unsent reports and queues revocation of the scoped grant.
  Sessions created while off and historical sessions from before eligible capture
  stay local.
- Register and send in an app-owned worker using a revocable, random installation
  capability scoped to automatic reports. Use the fixed approved HTTPS Feedback
  origin. Browser verification and OpenFPVS sign-in are unnecessary for this flow.
  Keep report files and retry state in protected app-local support storage, with
  the existing seven-day expiry and ten-report outbox limit. Retry with the same
  immutable payload using 15-minute to 24-hour backoff and at most three attempts
  per worker pass. Keep capture and receipt recovery responsive during network
  failures.
- The independent FPVS Studio Feedback service validates versioned payloads,
  deduplicates by report identity and exact content, and enforces the shared
  storage and retention limits. Allow at most three new automatic reports per
  installation per UTC day within the existing 100/day global acceptance cap.
  Use the existing queue for a private GitHub issue with the sanitized facts and an email to the
  configured maintainer (`zmurphy@abe.msstate.edu`). Keep installation and receipt
  capabilities out of the issue and email. OpenFPVS documents the flow. Report data
  stays in the Feedback service and its delivery destinations.
- Match the Mac repair email's compact format. Put the app and failure category in
  the subject. In at most 20 lines and 8 KiB of UTF-8 email body, place the app/OS
  versions and hardware snapshot above the error summary, followed by a short
  stack excerpt if available and the private issue link. Prioritize the summary
  and link when space runs out. A service receipt records acceptance. Issue
  creation and email delivery have their own outcomes. If an email acknowledgment
  is lost, the existing queue can retry the notification using the same issue.

Verify both apps with synthetic incidents and fake delivery. Cover exact app and OS
versions, absent GPU or RAM data, opt-out and offline recovery, error-to-crash
deduplication, payload redaction and bounds, quota enforcement and one private
issue with its maintainer email. Verify the actual desktop builds and the Feedback
service in staging before enabling automatic intake in production.

## Desktop scope

### macOS source repair reports

The [macOS repair helper](MACOS_SUPPORT.md) offers **Send Error Report** and
**Copy Log** after its checks and any PyCharm restart. Its recovery code lives in
that single script and uses the standard library to implement this same manual
protocol when Studio's dependencies cannot import. Payload compatibility tests
check it against `support.models.Report` and `Draft`. Browser verification,
approved-origin enforcement and durable ambiguous-delivery receipts still apply.
It sends only the helper's diagnostic capture and its associated PyCharm finishing
job, not arbitrary IDE session logs. Per-run logs/receipts stay in the checkout's
`.fpvs-macos/diagnostics/`; see the Mac guide for bounds and recovery actions.

### Automatic workflow completion reports

`Repair Mac 2.command` and `Repair Mac 2.py` select automatic completion reporting
in the shared repair helper. Reporting waits for the final PyCharm finishing result;
a pending restart is never reported as success. The existing manual entry point and
its browser verification remain available.

`support/workflow_reporting.py` owns the reusable standard-library-only builder,
validator, text renderer, installation client and durable outbox. Each workflow
supplies allowlisted facts; future workflow schemas extend the same transport and
receipt handling. The initial `macos_repair` schema includes macOS version/build,
native and Python CPU, Rosetta state, helper/Python/Studio/PsychoPy/SciPy/NumPy/Qt
versions, before/after repair versions, check results, failure categories, duration
and final outcome. It sends no raw logs, paths, credentials or research data.

Helper 2.1 runs the initial engine import before checking source-version policy or
changing packages. Optional `initial_engine_import`, `initial_dependency_check` and
`initial_compatibility_check` facts preserve that baseline; final `engine_import`,
`dependency_check` and `compatibility_check` describe the last checks. `change_kind`
distinguishes `none`, `compatibility_update`, `repair` and `unknown`. Package installs
are reported through `package_updates`, independently of `environment_rebuild`.
A successful compatibility update never implies the engine previously failed.
Older reports without the added facts retain a generic completion outcome.

The service accepts `kind: workflow` at `/v1/workflow-reports` after browser-free
registration at `/v1/workflow-installations`. Installation capability authentication,
strict 16-KiB envelopes, per-installation/global quotas and immutable report/receipt
identities bound delivery. The existing service queue creates the private issue and
maintainer email. Acceptance, issue creation and email delivery are separate outcomes.
Email calls the resulting record a **GitHub report**, including successful workflows.

Private `support/automatic-workflows/` storage owns registration and a bounded
seven-day outbox. Existing automatic-report preferences are read only: a saved off
choice or changed generation prevents historical delivery. Workflow revocation does
not depend on the separate crash-report backend. Offline reports retain their exact
identity and are retried on a later invocation; disabled reporting origins remain
disabled. The local repair also retains `completion.json` and `completion.txt`.

Service source/deployment is owned by `../FPVS-Studio-Feedback`; its deployment
record is authoritative for migration `0006_workflow_reporting.sql` and the separate
`WORKFLOW_REPORTS_ENABLED` switch. Workflow completion and desktop crash intake
have separate routes and installation capabilities.

### Studio capture and recovery

Settings > Diagnostics offers **Automatically send error and crash reports**, on by
default. A saved off choice remains off across upgrades and restarts. A one-time
startup notice lists the expanded fields and offers **Keep enabled** or **Turn off**.
Studio waits for the local disclosure record before expanded capture and delivery.
The switch remains usable during network work. Local preference writes run independently
of blocked HTTP, serialize repeated changes and finish during ordinary shutdown.
Stale network/load results cannot restore an earlier preference. Registration happens in a worker
without opening a browser, and closing Settings preserves the preference.
An explicitly disabled reporting origin pauses registration and uploads.

Studio registers in the background. Manual bug reports retain browser/Turnstile
verification.

After an unexpected exit, the next Studio startup recovers eligible app-owned
session records in a background worker. The first launch persists a stable random
installation identity before capture, even if registration is offline. Only sessions
started with reporting enabled in the active preference generation are eligible.
Studio may begin capture within the first eligible launch after showing the notice.
Sessions started while off and pre-v2 historical sessions stay local.
Python failures and native trace evidence
have separate categories; without native evidence the report says **unclean shutdown**,
which can also mean forced termination or power loss. Healthy active processes and
clean exits are excluded. This is best-effort recovery, not a guaranteed minidump.
Studio keeps exits from PyCharm source runs local when no Python failure or native
trace was recorded. PyCharm's Stop button can end the process before it saves a
clean shutdown. Captured Python, native and handled internal failures in those
runs remain eligible for automatic reporting.
An unreadable or changing native trace defers only its session for a later recovery
pass; other eligible sessions can still be recovered. Deferred evidence is preserved
without guessing a failure category.

Studio captures unexpected programming failures at app and worker boundaries.
It holds handled failures briefly before queueing so a correlated fatal exit can
provide stronger evidence. An already queued report keeps its identity and contents.
The session snapshot preserves the original Studio and OS versions and any
available allowlisted hardware and software facts. Inventory work runs outside
the GUI, presentation and fault-handler paths. Reports contain a failure category,
operation, occurrence or recovery timestamp and up to 40 sanitized stack locations.
Only package-relative Studio locations, function names and line numbers survive.
External paths and function names become `<external>`.

The account-local `support/automatic-crashes/` directory owns consent and a random
installation capability, session snapshots and queued payloads/receipt capabilities.
These use the existing protected account directory and atomic files (0600 on POSIX),
without separate encryption. No service credentials are included in Studio. Local
records expire after seven days; at most 100 inactive session snapshots and ten
queued reports remain. Active sessions are never pruned. The outbox reuses the same
UUID and exact payload after ambiguous delivery, with 15-minute to 24-hour backoff
and at most three attempts per worker pass. A timer revisits delivery every 15 minutes.

Disabling first persists local opt-out and discards the outbox, then revokes access
when connected. Pending revocation is retried at startup, every 15 minutes and before
registering a fresh generation after re-enabling. Network failure does not turn an
enabled preference off, and remote revocation never resets a saved opt-out to on.
Already sent/in-flight reports cannot be recalled. Network work is cancellable and
application-owned; only local opt-out persistence may finish during shutdown.
Local delivery warnings include the operation, error class and available HTTP status,
without exception messages, credentials or response bodies.

Exhausting the log budget or losing the log sink leaves the running session snapshot
active until Studio actually closes. A later unexpected exit can still recover as
an unclean shutdown even when bounded native/log capture has stopped.

The desktop protocol uses a revocable scoped grant with a one-year lifetime.
The service controls intake with a separate activation switch.
Expired/missing grants are registered again with the
same capability after a failed upload, preserving queued identities and retry backoff.
Registration shares the 1,000/day intent budget and a
10,000-installation metadata cap. Accepted automatic reports are limited transactionally
to three per installation/day and share the existing 100/day global report/storage
limits. Duplicate acceptance cannot create another issue or completed notification.
Ambiguous email delivery can still repeat a notification through the existing queue.

The desktop client uses POST `/v1/crash-installations` with the random installation
bearer token and exactly `{schema_version: "1", installation_id}` to register a UUID.
Only its capability hash is stored by the service. Registration retries reuse the
same identity/token; mismatched tokens and revoked identities cannot register.
POST `/v1/crash-reports` uses the installation capability and `X-Installation-ID`
and accepts exactly `{report, receipt_token_sha256}`. Required report fields are
`schema_version: "2"`, `kind: "crash"`, `report_id`, `created_at`, `time_basis`,
`product`, `app_version`, `os_family`, `os_version`, `crash_type`, `operation` and
`stack`. The optional `context` object contains the allowlisted inventory above.
Each stack frame has exactly `module`, `function`, and `line`. The complete envelope
is capped at 32 KiB. Ambiguous delivery checks the same report UUID and the separate
receipt capability at `/v1/reports/{id}/status` before a retry.
POST `/v1/crash-installations/{id}/revoke` revokes that installation. Installation and
receipt capabilities are scoped to crash reporting. Manual bug reports use browser
verification, and feature requests have their own intake.
This unattended registration flow permits more automated abuse than a browser check;
fixed-origin validation, IP limits, transactional registration/storage/report quotas
remain in the service. Registration retries and renewals do not consume another
registration quota. Never ship a shared service secret as a substitute.

Source implementation and rollout evidence are tracked in
[the automatic-crash plan](exec-plans/active/automatic-crash-reporting.md).

### Manual bug reports

The native desktop implementation is available independently of Cloudflare.
**Help > Report a Bug...** opens Details and Diagnostics tabs. Error popups also
offer **Report this bug. Please!**, including errors before a project is open or
while choosing the Studio Root. One click closes the error popup and opens the
existing reporter with its full error details attached alongside collected session
logs, instead of replacing the logs with the popup traceback. A fresh report has its
summary and description filled in; a quick note about reproduction is optional.
Opening either entry point collects locally and never submits automatically.
Repeated menu clicks raise the same dialog and preserve its existing draft.
After an upgrade, restored editable drafts use the running Studio version in the
dialog, copied/saved text, and submitted payload. Receipt-locked reports retain
their recorded version and exact payload for status recovery.

Required fields: summary and what happened. Reproduction steps, expected behavior,
and reply email are optional. Unknown reproduction steps have an explicit option.
Users can edit or exclude logs, copy the report, or save UTF-8 text. Excluding logs
also excludes the error details; app version and OS remain included. Credentials
for receipt access never appear in text exports or clipboard copies.

The approved reporting service is connected by default. Submit Report keeps the
existing browser verification, reviewed payload, and receipt recovery workflow.
An explicitly disabled connection leaves Copy and Save available. No network
requests occur on dialog opening, collection, editing, draft saving, or exporting.

Common permission, missing-file, file-in-use, disk-space, archive, connection,
dependency and compatibility errors have plain-language explanations and next
steps. Messages state the failed action, a supported possible cause and a short
recovery step. Unknown errors say that the cause could not be identified rather
than guessing. Clear field-specific validation keeps its field labels and useful
values; Python exception names, stack traces, internal field names and serialized
settings do not appear in primary explanations.
USB TriggerBox failures retain their connection, marker/reset or cleanup explanation
before generic file/network rules, including chained Windows access errors and
serialized launch failures. Technical driver details stay in **Show Details...**.
**Show Details...** retains the original message and chained traceback. Studio's
application-owned `gui/error_dialogs.py` decorates critical message boxes and
simple warning errors, including static Qt message boxes. Warning confirmations
and information messages retain their existing decisions. Native error popups
size to their wrapped text; Qt may choose a content width below the requested minimum.
Details expand separately. The report button is never the default or Escape action.

`support/error_explanations.py` owns GUI-neutral explanation rules. New error
popups and exception-driven inline labels use this owner, including recording,
authoring, results, Library, sharing and update failures. Device/local display
timeouts remain separate from online-service failures; file errors keep their
file-specific recovery even when raised during an online operation. Inline
diagnostics remain in existing tooltips/logs; updater startup errors have expandable
details without loading the full Studio application. Normal progress messages and
confirmation decisions are unchanged. Visible acceptance checks the affected
surfaces at minimum size in both themes, with long failures and expanded details.

New error context is redacted and bounded through the existing support helpers. Existing
report text is preserved; **Use newly reported error** adds that error to its
diagnostics and fills only blank description fields. Refreshing the logs retains
the last explicitly accepted error. Verification, sending, and
receipt-locked reports cannot replace their payload with a later error.

## Local ownership and retention

`support/` owns the report model, redaction, persistence, and HTTP client.
`gui/report_bug_dialog.py` owns presentation, and `gui/bug_report_controller.py`
owns the single dialog and worker callbacks. The generic task API in the existing
`gui/update_lifecycle.py` owns native worker lifetime and shutdown coordination.
Its `finish_on_shutdown` option is reserved for bounded local persistence, never
network work; draft flushes may finish after a shutdown request. Application exit
continues processing events until those jobs stop, without a GUI-thread wait.

The thin `app/main.py` entry point installs a queue-backed log handler on the
`fpvs_studio` logger. It captures application messages and unhandled exceptions;
formatting, redaction, and writes occur on a daemon logging thread. Close drains
the queue with a bounded wait only after the GUI event loop exits. No engine imports,
hardware probes, project-file reads, or per-frame disk logging are introduced.
`gui/qt_diagnostics.py` forwards Qt warnings to the same logger and preserves a small
redacted fatal breadcrumb and thread tracebacks before Qt aborts (Windows fast-fail
can bypass ordinary fault handlers). Bootstrap also enables Python's fault
handler before importing Qt, unless another fault handler is already enabled. Native
tracebacks use a separate `session-<id>-native.log` in the same app-owned logs directory;
the descriptor stays open until capture is disabled. These local traces contain stack
filenames/function names, not source text or project data. Collection redacts them and
requires the same explicit review/submission as other diagnostics. Abrupt native exits
can still prevent complete capture; these traces do not replace native minidumps.

Support storage is independent of the active project root:

- Windows: `%LOCALAPPDATA%/FPVS Studio/support/`.
- Linux: `$XDG_STATE_HOME/fpvs-studio/support/`, defaulting to
  `~/.local/state/fpvs-studio/support/`.
- macOS path resolution is provided, but the desktop target remains Windows/Linux.

Each process uses a unique log basename, at most three 1 MiB files. Startup removes
expired owned logs after seven days, or older inactive logs when space is needed.
Recent logs are not deleted to make room for another process. Logging stops with
a collection notice at the 10 MiB budget; simultaneous processes may exceed that
threshold briefly by a bounded record per writer. The queue holds 256 records;
overload drops logs with a notice instead of blocking presentation.
Files disappearing during concurrent log rotation or pruning are skipped without
stopping the logging thread or collection. Other storage failures remain visible.
Native capture stops after reaching 1 MiB; an in-flight traceback may exceed that
threshold, bounded by Python's limits of 100 threads/100 frames and 500 characters per
string. Native files share the existing retention and overall budget. Only fatal Qt
breadcrumbs and catastrophic native tracebacks write directly to the open descriptor;
ordinary formatting and file writes remain on the logging thread.

Drafts use atomic writes and retain at most five files, each up to 4 MiB, for
seven days. Closing saves the current draft; Discard Draft explicitly deletes it.
Only matching owned files are purged. File-save cancellation has no side effects.
Storage failures remain visible and Copy Report is still usable. Drafts contain
reviewed text and receipt capabilities in the user's local account storage; they
are not encrypted separately. Do not include research records in reports.
The last accepted error is local draft metadata so refreshing after restart can
retain it. It is not a new upload field and does not change receipt-bound payloads.

Collection reads only the active process's app-owned support session logs, including
retained rotations and native traces, up to 256 KiB. Without a matching active logger,
it explicitly identifies the latest retained session. It never mixes other live
sessions into the report. Sections identify their source files; missing, rotated-away
or over-budget text cannot be recovered, and omissions are explicitly identified.
The collector and popup context share the same reviewed-text budget. Common path prefixes,
emails, participant tags, and credentials are redacted best-effort. Users review
the final text because redaction cannot guarantee removal of every sensitive value.
Credential redaction covers quoted keys and values, including JSON and passwords
containing spaces, as well as complete bearer tokens.
No project models, stimuli, participant CSVs, or arbitrary attachments are collected.

## Production activation

The Cloudflare service passed automatic queue delivery acceptance on 2026-09-14.
FPVS Studio now defaults to `https://reports.zack-murphy.com`; users still explicitly
review and submit each report. Opening a dialog does not upload its contents.
No account, DNS or subscription changes are performed by the desktop.

An explicitly empty `FPVS_REPORT_SERVICE_URL` disables online submission. When set
to a nonempty value it must exactly equal the approved HTTPS origin. Other origins,
HTTP, URL credentials, paths, and redirects are rejected. Restart FPVS Studio after
changing the launch environment. No GitHub or Turnstile secrets belong in the app.
Tests inject a fake transport instead of allowing alternate production URLs.
Existing installed builds need an updated release or the approved endpoint in their
launch environment; changing source does not update already installed applications.

## Version 1 wire contract

All responses use `application/json`, bounded at 16 KiB. Requests use HTTPS with
a 10-second socket timeout; redirects are never followed. No automatic HTTP retries.
Error responses are not echoed to the user, preventing accidental secret disclosure.

The reviewed report is UTF-8 JSON, sorted keys, no insignificant whitespace,
`ensure_ascii=False`. Its SHA-256 binds the intent to the exact upload bytes.

| Field | Type / limit |
| --- | --- |
| schema_version | String `1` |
| report_id | UUID string, stable across retries |
| created_at | UTC ISO timestamp |
| title | Required, at most 160 characters |
| happened | Required text |
| steps / expected | Optional text; all description fields together at most 16 KiB UTF-8 |
| email | Optional reply email, at most 254 characters |
| app_version / os_version | App and OS strings; no hostname or environment dump |
| diagnostics | Reviewed text, at most 256 KiB; empty when excluded |

Maximum complete bug payload: 1 MiB. Feature and automatic crash limits are unchanged.
Unknown fields and binary uploads must be rejected
server-side. Backend must revalidate all lengths, types, and hashes independently.

1. `POST /v1/intents`: body contains `schema_version`, `report_id`,
   `payload_sha256`, and `receipt_token_sha256`. The desktop creates the random
   receipt token before this request and saves it locally. The service binds its
   hash to the report ID now, so a lost upload response remains recoverable.
   Return exactly `intent_id`, `browser_token`, `desktop_token`. IDs use 16–128
   URL-safe characters; tokens use 32–256 URL-safe characters and require at least
   256 bits of random entropy on the server. Store token hashes on the server.
2. Browser opens `/verify#intent_id=...&token=...` using only the browser token.
   The page consumes/removes the fragment and verifies Turnstile server-side.
   No description, email, or desktop/receipt token enters the URL.
3. `GET /v1/intents/{intent_id}/status`, with `Authorization: Bearer <desktop_token>`:
   return `{"state":"pending"}`, `verified`, or `expired`. The desktop polls every
   three seconds for at most two minutes, while the reporter keeps the dialog open.
   Expiry, cancellation, or editing requires a new intent. The same report ID and
   receipt hash must remain acceptable when renewing an unsubmitted intent.
4. `POST /v1/reports?intent_id={intent_id}`, same desktop authorization, body is
   the exact reviewed report bytes. The desktop durably saves `delivery=uncertain`
   and its receipt token before this request. Server must check hash, consume the
   intent, and accept a report ID idempotently. Report bodies may not vary for an
   already accepted ID. Register/revoke grants atomically against report state.
5. `GET /v1/reports/{report_id}/status`, with `Authorization: Bearer <receipt_token>`:
   return the report ID and a state, without any private report contents.

Submission/status response:

```json
{"report_id":"a UUID matching the request","state":"received"}
```

Supported states are `received`, `submitted`, `uncertain`, and `not_received`.
`not_received` is authoritative only if the server has also revoked all previous
upload grants for that report and guarantees no earlier in-flight submission can
later be accepted. A generic 404 or search miss is not this guarantee. Without it,
keep `uncertain` and reconcile or request maintainer intervention. Never turn an
unknown receipt into permission to create a duplicate report.

The UI freezes the reviewed payload during verification/upload and while delivery
is uncertain or pending. It shows Check status after ambiguous delivery, preserving
the same report ID; it never automatically POSTs again. A received report is shown
as pending GitHub delivery. Submitted becomes Done only after the issue and every
required diagnostic part are confirmed. The service never returns
a private GitHub URL as the user's receipt link. Cancellation does not retract bytes
already sent, so receipt checks remain necessary after interrupted uploads.

## Cloudflare service ownership

The independent service lives in the private
[`zcm58/FPVS-Studio-Feedback`](https://github.com/zcm58/FPVS-Studio-Feedback)
repository. Its README and deployment log own live configuration, migrations,
acceptance evidence and rollback. It uses Workers Free, D1, Turnstile, a GitHub
App restricted to that repository, and email notifications to
`zmurphy@abe.msstate.edu`. No R2 or paid subscription was enabled. Sending-domain
records belong under `reports.zack-murphy.com`; existing website records are preserved.

The service's copy of submitted logs and optional reply email expires after 14 days;
D1 recovery history may retain deleted data for seven additional days. GitHub descriptions
and all included reviewed diagnostics from Studio 2.8.2 and later remain until manually removed.
Earlier clients retain their disclosed short-excerpt delivery; existing reports are
not republished with expanded logs. Small diagnostics
fit directly in the issue; larger diagnostics use numbered, bounded comments. Accepted
text is not silently shortened for GitHub. Delivery confirms each part and reconciles
ambiguous writes before retrying, preserving report identity and preventing blind reposts.
The server shares a 100-report daily limit across bugs and features, with separate
transactional intent and storage limits. Background cleanup, GitHub authentication, issue creation and
email run in rotating minute phases to keep CPU work bounded. Email retry cannot
create a second issue. A received receipt may remain pending during external failures.

The HTTP client identifies itself as `FPVS-Studio/1.0`; Cloudflare rejected Python's
default user-agent during live integration. No Cloudflare security rules were weakened.

## Verification and visible acceptance

Safe local checks: GUI focused, repo precommit, and the support unit tests. The
registered `tests/gui/test_report_bug_dialog.py` tests use fake services and browser
calls; they require explicit approval for a safe visible environment. Never use
offscreen Qt execution. GUI geometry has not been accepted solely by static checks.

Manual visible acceptance in both themes and at 125%/150% Windows scaling:

1. Open Help > Report a Bug at 760x680 and 860x760. Repeat the action and confirm one
   dialog. Check both tabs, longest status text, keyboard traversal, and no clipping.
2. Write a detailed report, edit the diagnostic preview, exclude logs, and copy/save
   text. Check that excluded logs and receipt tokens are absent. Cancel the picker.
3. Close and reopen, then restart normally to confirm recovery. Discard the draft.
4. Trigger a file-access error from Welcome/first-run setup and a project window.
   Check its explanation, expanded details, and Report this bug. Please! button.
   Confirm OK/Enter/Escape never reports, confirmation choices are unchanged, and
   the report is interactive above modal setup. Submit a fresh error report with
   no reproduction note using a fake service; verify draft/receipt preservation.
5. With a test service only, test browser failure/expiry, cancellation, quota failure,
   lost upload response, pending/submitted receipts, and quit during a draft write.
6. With the variable explicitly empty, Submit remains disabled and no browser/network opens.
