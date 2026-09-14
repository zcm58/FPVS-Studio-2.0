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

The native desktop implementation is available independently of Cloudflare.
**File > Report a Bug...** is the only reporting entry point and opens Details and
Diagnostics tabs. Welcome, root-folder setup, and error dialogs have no reporting
button. Unexpected errors still enter the application logs for later review.
Repeated menu clicks raise the same dialog and preserve its existing draft.

Required fields: summary and what happened. Reproduction steps, expected behavior,
and reply email are optional. Unknown reproduction steps have an explicit option.
Users can edit or exclude logs, copy the report, or save UTF-8 text. Excluding logs
also excludes the error excerpt; app version and OS remain included. Credentials
for receipt access never appear in text exports or clipboard copies.

There is no live reporting backend configured by default. Submit is disabled and
the dialog explains that online reporting is not connected. No network requests
occur on dialog opening, collection, editing, draft saving, or exporting.

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
Abrupt process/native crashes may not leave complete logs.

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
4. Verify Welcome, first-run root setup, and error dialogs have no reporting button.
   Open the report from File twice and verify preservation of the existing draft.
5. With a test service only, test browser failure/expiry, cancellation, quota failure,
   lost upload response, pending/submitted receipts, and quit during a draft write.
6. With the variable explicitly empty, Submit remains disabled and no browser/network opens.
