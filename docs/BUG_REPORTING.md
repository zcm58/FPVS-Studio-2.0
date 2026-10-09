# Bug reporting

## Feature requests

File > Request a Feature opens a text-only editor at minimum 760x680 and default
860x760. One required text box has a live 4,000-character counter (Unicode code
points), Copy Request and Save Request. Over-limit pasted text remains editable;
Submit Request is disabled until shortened. Online submission remains disabled
until service activation. Feature requests never collect logs or include OS,
email, project or participant data.

Feature drafts reuse atomic worker persistence and seven-day/five-draft retention
in the separate app-local `support/feature-drafts/` directory. Bug drafts stay
independent. Receipt locking, cancellation, browser verification and explicit
status checks reuse the existing reporting protocol.

The `/v1/reports` endpoint accepts this feature payload variant:
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

## Desktop scope

### Automatic crash reports

Settings > Diagnostics offers **Automatically send crash reports**, on by default
in desktop source. A saved off choice remains off across upgrades and restarts.
The switch remains usable during network work. Local preference writes run independently
of blocked HTTP, serialize repeated changes and finish during ordinary shutdown.
Stale network/load results cannot restore an earlier preference. Registration happens in a worker
without opening a browser, and closing Settings preserves the preference.
An explicitly disabled reporting origin pauses registration and uploads.

The matching service source implements browser-free background registration, explicitly
approved by the maintainer. Automatic intake remains disabled pending authenticated
deployment acceptance. Live use requires that deployed backend and an updated desktop
build; manual bug and feature reports retain their browser/Turnstile verification.

After an unexpected exit, the next Studio startup recovers eligible app-owned
session records in a background worker. The first launch persists a stable random
installation identity before capture, even if registration is offline. Only sessions
started with reporting enabled in the active preference generation are eligible;
sessions created while off and prior historical sessions are never backfilled.
Python failures and native trace evidence
have separate categories; without native evidence the report says **unclean shutdown**,
which can also mean forced termination or power loss. Healthy active processes and
clean exits are excluded. This is best-effort recovery, not a guaranteed minidump.

Automatic payloads contain Studio/OS versions, timestamp, failure category and at
most 40 sanitized stack locations. Only package-relative Studio source paths,
function names and line numbers survive; external paths/names become `<external>`.
No exception messages, full logs, environment, hostname, hardware identifier,
project/stimulus data, participant records or attachments are collected. The service
emails `zmurphy@abe.msstate.edu` a summary, up to 8 KiB of sanitized stack locations
and a private issue link. Manual report contents retain their existing review rules.

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

Exhausting the log budget or losing the log sink leaves the running session snapshot
active until Studio actually closes. A later unexpected exit can still recover as
an unclean shutdown even when bounded native/log capture has stopped.

The separate feedback service needs additive migration `0005_crash_reporting.sql`
and `CRASH_REPORTS_ENABLED=true` after deployment acceptance. Its scoped grant lasts
one year and can be revoked. Expired/missing grants are registered again with the
same capability after a failed upload, preserving queued identities and retry backoff.
Registration shares the 1,000/day intent budget and a
10,000-installation metadata cap. Accepted automatic reports are limited transactionally
to three per installation/day and share the existing 100/day global report/storage
limits. Duplicate acceptance cannot create another issue or completed notification.
Ambiguous email delivery can still repeat a notification through the existing queue.

Opt-out protocol: POST `/v1/crash-installations` uses the random installation
bearer token and exactly `{schema_version: "1", installation_id}` to register a UUID.
Only its capability hash is stored by the service. Registration retries reuse the
same identity/token; mismatched tokens and revoked identities cannot register.
POST `/v1/crash-reports` authenticates the
installation capability and accepts exactly `{report, receipt_token_sha256}`;
the report fields are `schema_version: "1"`, `kind: "crash"`, `report_id`, `created_at`,
`app_version`, `os_version`, `crash_type`, and `stack`. Each stack frame has exactly
`module`, `function`, and `line`; the complete envelope is capped at 32 KiB.
POST `/v1/crash-installations/{id}/revoke` revokes that installation. Installation and
receipt capabilities cannot authorize manual reports, which retain browser verification.
This unattended registration flow permits more automated abuse than a browser check;
fixed-origin validation, IP limits, transactional registration/storage/report quotas
remain in the service. Registration retries and renewals do not consume another
registration quota. Never ship a shared service secret as a substitute.

Source implementation and rollout evidence are tracked in
[the automatic-crash plan](exec-plans/active/automatic-crash-reporting.md).
Existing installed executables require an updated build; source edits alone do not
enable this preference in shipped installations.

### Manual bug reports

The native desktop implementation is available independently of Cloudflare.
**File > Report a Bug...** opens Details and Diagnostics tabs. Error popups also
offer **Report this bug. Please!**, including errors before a project is open or
while choosing the Studio Root. One click closes the error popup and opens the
existing reporter with its full error details attached. A fresh report has its
summary and description filled in; a quick note about reproduction is optional.
Opening either entry point collects locally and never submits automatically.
Repeated menu clicks raise the same dialog and preserve its existing draft.

Required fields: summary and what happened. Reproduction steps, expected behavior,
and reply email are optional. Unknown reproduction steps have an explicit option.
Users can edit or exclude logs, copy the report, or save UTF-8 text. Excluding logs
also excludes the error excerpt; app version and OS remain included. Credentials
for receipt access never appear in text exports or clipboard copies.

The approved reporting service is connected by default. Submit Report keeps the
existing browser verification, reviewed payload, and receipt recovery workflow.
An explicitly disabled connection leaves Copy and Save available. No network
requests occur on dialog opening, collection, editing, draft saving, or exporting.

Common permission, missing-file, file-in-use, disk-space, archive, connection,
dependency and compatibility errors have plain-language explanations and next
steps. Unknown errors describe the failed action without guessing its cause.
**Show Details...** retains the original message and chained traceback. Studio's
application-owned `gui/error_dialogs.py` decorates critical message boxes and
simple warning errors, including static Qt message boxes. Warning confirmations
and information messages retain their existing decisions. Native error popups
size to their wrapped text with a minimum width of 580 logical pixels; details
expand separately. The report button is never the default or Escape action.

`support/error_explanations.py` owns GUI-neutral explanation rules. New error
context is redacted and bounded through the existing support helpers. Existing
report text is preserved; **Use newly reported error** explicitly replaces its
diagnostics and fills only blank description fields. Verification, sending, and
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
Native capture stops after reaching 1 MiB; an in-flight traceback may exceed that
threshold, bounded by Python's limits of 100 threads/100 frames and 500 characters per
string. Native files share the existing retention and overall budget. Only fatal Qt
breadcrumbs and catastrophic native tracebacks write directly to the open descriptor;
ordinary formatting and file writes remain on the logging thread.

Drafts use atomic writes and retain at most five files, each up to 256 KiB, for
seven days. Closing saves the current draft; Discard Draft explicitly deletes it.
Only matching owned files are purged. File-save cancellation has no side effects.
Storage failures remain visible and Copy Report is still usable. Drafts contain
reviewed text and receipt capabilities in the user's local account storage; they
are not encrypted separately. Do not include research records in reports.

Collection reads only app-owned support logs, up to 96 KiB. Common path prefixes,
emails, participant tags, and credentials are redacted best-effort. Users review
the final text because redaction cannot guarantee removal of every sensitive value.
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
| diagnostics | Reviewed text, at most 96 KiB; empty when excluded |

Maximum complete payload: 128 KiB. Unknown fields and binary uploads must be rejected
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
as pending GitHub issue creation. Submitted becomes Done. The service never returns
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

Full submitted logs and optional reply email expire after 14 days; D1 recovery
history may retain deleted data for seven additional days. GitHub descriptions and
a bounded reviewed error excerpt have a separate lifetime until manually removed.
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

1. Open File > Report a Bug at 760x680 and 860x760. Repeat the action and confirm one
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
