# Free Cloudflare Bug Reporting

Status: Active

Date: 2026-09-12

## Service integration (2026-09-14)

The user subsequently authorized Cloudflare provisioning and direct email
notifications to `zmurphy@abe.msstate.edu`. The independent service repository is
now `zcm58/FPVS-Studio-Feedback` (private), with a GitHub App installed on that
repository only and Issues write/metadata read permissions. No paid plan was added.
Workers, D1, Turnstile and restricted email delivery are provisioned. The sending
domain is `reports.zack-murphy.com`; apex/www website records remain intact.

Staging has created a synthetic bug issue and feature issue; both notification
emails were accepted, and the user confirmed the bug notification arrived.
The service enforces both desktop wire variants, independent capability roles,
transactional quotas, receipt deduplication, uncertain GitHub reconciliation,
and separate email retries. Full payloads expire after 14 days; receipt metadata
after 30 days. Backend source, migrations, tests and operations belong in the
separate repository. Its README and deployment log are the deployment authority.

CPU acceptance now separates intake, cleanup, authentication, issue delivery and
email into different invocations. The minute schedule rotates four background phases.
The desktop HTTP client now identifies FPVS Studio explicitly, avoiding Cloudflare's
rejection of Python's generic user-agent. Support checks passed (30 tests, one
permission skip); repo precommit passed (1,440 tests, seven permission skips).
Service source and these desktop changes are committed and pushed. As of 14:09 UTC,
manual delivery and revised CPU tests pass, but Cloudflare's automatic schedule has
not executed despite reapplying it and waiting through the propagation window.
Production intake/delivery and local desktop activation remain disabled. The
separate service deployment record owns this remaining rollout blocker.
The earlier desktop-only deferral below records the original implementation stage;
it does not override this later authorization. Visible desktop geometry and a
packaged release remain separate acceptance work, so this plan remains active.

## Desktop implementation (2026-09-14)

Feature-request extension: implemented File > Request a Feature with a single
4,000-character text box, live counter, independent local drafts, copy/text export,
and the shared verification/receipt client. No logs are collected for requests.
The feature wire variant and server validation requirements are documented in
`docs/BUG_REPORTING.md`. Cloudflare connection and visible GUI acceptance remain
deferred. Feature-extension verification passed GUI focused checks and repo
precommit (Ruff, compilation, mypy, audits, 1,439 non-Qt tests; seven Windows
symlink-permission skips). Registered visible GUI acceptance remains unrun.

The user requested completing the FPVS Studio side first and handling Cloudflare
separately, reversing the original backend-first implementation order below.

- Implemented File > Report a Bug and the native Details/Diagnostics dialog.
  At the user's request, File is the only entry point: reporting buttons were
  removed from Welcome, root setup, and error dialogs before committing.
- Added GUI-neutral support models, queued redacted logs, atomic local drafts,
  copy/text export, and the fixed-origin opt-in HTTP client. Online submission is
  disabled until `FPVS_REPORT_SERVICE_URL` is explicitly set after service setup.
- The existing app-owned worker lifecycle handles report jobs. A bounded local
  persistence option allows shutdown to flush a draft without canceling its write;
  network jobs remain cancelable. No project or experiment contracts changed.
- The implemented client contract and activation/manual acceptance instructions
  are canonical in `docs/BUG_REPORTING.md`; the service must match that contract.
  Polling uses a bounded three-second interval for two minutes. Local logging's
  global budget is approximate across simultaneous processes, with a per-process
  three-file hard bound, as documented in that contract.
- Safe GUI focused checks and repo precommit passed: Ruff, compilation, mypy,
  architecture/registry/docs audits, and 1,433 non-Qt tests. Seven Windows symlink
  tests were skipped because this account cannot create symlinks.
- Registered GUI tests were added/updated, including layout, cancellation,
  ambiguous delivery, menu placement, and shutdown writes. Visible Qt checks and
  Windows scaling acceptance remain unrun under the repository's opt-in policy.
- Cloudflare, DNS, GitHub App/repository creation, live service validation, and
  packaged deployment remain deferred. No remote resources were changed.

The plan remains active for the separate service integration and visible acceptance.

## Decisions and scope

The user requested a plan for Cloudflare hosting using their existing
`zack-murphy.com` domain and selected descriptions and text error logs only.
The user also explicitly requested a new native GUI surface reached through
**File > Report a Bug...**; this is a required deliverable of the feature.
On 2026-09-14 the user first authorized desktop implementation and then the separate
service setup described above. Online submission remains explicitly configured
through the launcher environment after service acceptance.

Use Workers Free, D1 Free, and Turnstile Free. Do not enable R2, a paid Workers
subscription, paid email infrastructure, screenshots, or arbitrary file uploads.
This replaces the earlier R2 suggestion because bounded text diagnostics fit D1.
The target is zero incremental hosting cost on the free plans, not guaranteed
availability under unlimited traffic. Existing domain renewal costs are separate.

Selected deployment configuration:

- Public submission and verification host: `reports.zack-murphy.com`.
- Private GitHub repository: `zcm58/FPVS-Studio-Feedback`, containing the small
  service's code and incoming issues.
- GitHub App installed only on that repository, with Issues read/write and the
  required metadata access. No repository Contents write permission or webhooks.
- Native FPVS Studio report editor, with a short system-browser verification step.
- Optional reply email stored privately; replies are manual in version one.
- Full text diagnostics retained in D1 for 14 days. Issue descriptions and a short
  reviewed error excerpt remain in the private GitHub issue until manually removed.

## Domain evidence and deployment boundary

On 2026-09-12 the public homepage identified itself as built with Quarto and GitHub
Pages. Public DNS returned `holly.ns.cloudflare.com` and
`fattouche.ns.cloudflare.com`. This supports Cloudflare DNS use but does not verify
the signed-in account, zone status, existing Workers subscriptions, or ownership of
the proposed reporting hostname.

Before deployment, inspect that account's active zone, Workers plan, existing
usage, and the proposed hostname's records. Add an exact Worker Custom Domain for
`reports.zack-murphy.com`; do not attach the Worker to the apex, `www`, or a wildcard
route. Cloudflare requires an active zone and disallows a conflicting CNAME at the
chosen hostname. Preserve the homepage, mail records, and current site deployment.
[Homepage](https://zack-murphy.com/),
[Custom Domain requirements](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

## User workflow

1. Open **File > Report a Bug...** beside the existing File-menu support actions.
   Welcome, root setup, and error dialogs have no reporting button. Unexpected
   errors remain in application logs; validation errors are not treated as crashes.
2. Enter a title, what happened, reproduction steps, expected behavior, and optional
   reply email. Reproduction steps may explicitly say the cause is unknown.
3. Review the exact text diagnostics. The user may edit/remove them or submit the
   description alone. Explain the private destination and retention before sending.
4. Click **Submit report**. Open the system browser to a small Turnstile verification
   page. Explain this step in the dialog; the native dialog preserves the draft.
   No GitHub or Cloudflare account is required for reporters.
5. After verification, the desktop worker submits the reviewed payload. Report the
   actual state: **Report received; issue creation pending** or **Report submitted**
   with a receipt ID. A private issue URL is not a useful reporter-facing link.
6. On offline, timeout, expired verification, quota, or service failure, retain the
   draft and offer explicit Retry, Copy report, and Save report as UTF-8 text.
   Do not claim delivery just because the browser opened or a request started.

Proposed report-dialog minimum: 760x680; default: 860x760, in logical pixels. Use
Details and Diagnostics pages so all controls fit. Long text may scroll inside
editors; primary actions and status remain visible in every state. Preserve the
eight-step Setup layout. Normal closing preserves the unsent draft; **Discard**
explicitly deletes that draft. Network work cancels asynchronously without blocking
the GUI or destroying active worker threads.

## Native Report a Bug surface

Implement a dedicated PySide6 `ReportBugDialog`, titled **Report a Bug**, rather
than asking users to write their report on a website. The browser is used only
for the verification step. All writing, diagnostic review, progress, and recovery
remain in the native dialog.

### Entry points and ownership

- Add `report_bug_action` in `gui/main_window.py`, between **Check for Updates**
  and the existing Tutorials/About actions in File. It is available regardless
  of whether project setup is complete and does not save or modify a project.
- Keep File as the only reporting entry point. Shared unexpected-error handling in
  `gui/window_helpers.py` logs the traceback for later diagnostic review.
- Use one application-owned reporting coordinator and one modeless report dialog.
  Repeated menu clicks raise the existing dialog. Never overwrite an existing
  draft with a newly reported error; offer an explicit action to replace the
  diagnostic context while preserving the written description.
- Proposed UI module: `gui/report_bug_dialog.py`; coordinator/worker ownership:
  `gui/bug_report_controller.py`. The main window wires the File actions.
  GUI-neutral collection, persistence, and submission remain in `support/`.

### Layout and fields

Use the shared dialog styling and components, with a fixed header, two tabs, a
wrapped status area, and persistent footer actions. The Details tab opens first.

| Surface | Controls and behavior |
| --- | --- |
| Header | Report a Bug; short explanation that the report goes privately to the developer |
| Details tab | Summary (required), What happened? (required), Steps to reproduce, What did you expect?, Reply email (optional) |
| Diagnostics tab | Include error logs checkbox; editable plain-text preview; included app/OS metadata; visible truncation/size notice |
| Status area | Field validation, collection/verification/upload progress, errors, or receipt confirmation; text wraps |
| Footer | Save Report..., Close, and primary Submit Report; Copy Report and Discard Draft in a secondary actions menu |

Use multi-line editors for the description fields, with **I don't know how to
reproduce it** available beside reproduction steps. Validate the required summary
and actual behavior inline; optional fields never block submission when blank.
Validate an email only if supplied. Show length/byte-limit feedback before submit,
without silently cutting user-written descriptions. Match the limits in the
service contract below.

Diagnostics are collected locally on opening, in a worker. The user can inspect
and edit the exact selected text before sending. Unchecking **Include error logs**
removes both the logs and error excerpt from the outgoing report. Keep a visible
summary of app version and OS that will still be included. Re-collecting diagnostics
must be explicit and must not silently overwrite user edits. If collection fails,
allow a description-only report with a clear notice.

Before submission, show concise copy explaining the private destination, the
14-day full-log retention, the longer-lived GitHub description/error excerpt, and
that a browser verification step will open. Detailed retention information can
expand in-place. No screenshot, attachment picker, or project-upload control in v1.

### Interaction states

| State | Required behavior |
| --- | --- |
| Editing/collecting | Preserve typing while logs load; Submit becomes available once required fields and selected diagnostics are ready |
| Awaiting verification | Freeze the reviewed payload; show Open verification page and Cancel submission; Cancel returns to editing |
| Sending | Prevent repeated submission, keep progress visible, and offer Cancel; cancellation does not promise remote retraction |
| Received, issue pending | Show receipt ID and accurate pending status; Check status uses the same receipt; do not offer a new submission |
| Submitted | Show confirmation and Copy receipt; primary action becomes Done; an explicit New report starts a fresh draft |
| Failed/uncertain | Preserve the draft; show actionable Retry or Check status as appropriate, plus Save Report; retain the same report ID |

Closing or canceling after an upload may have reached the service must retain the
receipt/report ID for later reconciliation. Do not discard that identity and then
resend as a new report. Editing after a definite failure invalidates verification;
editing after an uncertain outcome first requires checking the previous delivery.

### GUI acceptance

The native dialog is part of the initial implementation, not a later enhancement.
Exercise its minimum 760x680 and default 860x760 sizes in both themes, including
Windows 125%/150% display scaling in visible acceptance. Text editors may scroll;
tabs, labels, validation, status, and footer actions must fit without clipping.
Provide keyboard traversal, accessible labels, plain-text copy, and focus on the
first invalid field. Closing by Escape or the window button follows draft retention.

Register `tests/gui/test_report_bug_dialog.py` and entry-point coverage when the UI
is implemented. Test File-menu placement, repeat-open behavior, no-project access,
error-prefill draft preservation, tab switching, diagnostic exclusion/editing,
validation, every state above, keyboard operation, sizing, and worker-safe closing.
Use fake services; do not open a real browser or send real reports in GUI tests.

## Service design

```text
FPVS Studio report editor -- reviewed text --> Worker HTTPS API
          |                                      |
          +--> browser verification / Turnstile   +--> D1: receipt, logs, delivery state
                                                 +--> GitHub App: private issue
```

Keep a versioned JSON contract independent of Qt and experiment schemas:
`schema_version`, client-generated random report ID, creation time, title,
description fields, optional contact email, selected environment metadata, and
reviewed diagnostic text. Never put report contents or contact details in URLs.
Choose explicit field and UTF-8 byte limits; initial complete request cap is
128 KiB, with at most 96 KiB of recent diagnostic text. Reject binary, compressed,
multipart, or unknown-field payloads. Truncation must be visible during review.
Cap the combined description fields at 16 KiB, the title at 160 characters, and
the optional email at 254 characters; preserve the complete accepted description
in GitHub and use only the remaining issue-body budget for the error excerpt.

Use these logical endpoints, finalized and contract-tested during implementation:

- `POST /v1/intents`: bounded metadata only; creates a short-lived verification
  intent tied to the report ID and hash of the exact reviewed payload. Rate limit
  before allocating D1 rows; expire intents after 10 minutes.
- `GET /verify`: serves the verification page. Give it a random, purpose-limited
  browser capability via URL fragment, exchange it in a POST, and remove the
  fragment from history. It never grants access to the report contents.
- `POST /v1/intents/verify`: validates Turnstile server-side, checks expected
  hostname/action, and marks that intent verified. Turnstile tokens are single-use
  and expire after five minutes; failed or stale verification stays recoverable.
- Intent status endpoint: authenticated by a separate random desktop capability
  supplied in a header. Poll with bounded backoff for at most two minutes; after
  that offer Resume verification, with no background indefinite polling.
- `POST /v1/reports`: requires the verified intent and desktop capability; checks
  the payload hash and atomically consumes the grant while saving the report.
  Editing a reviewed report requires a fresh intent.
- Receipt status endpoint: a separate random capability returns only delivery
  state and receipt ID, never diagnostics, email, or a private issue body.

Generate capabilities with at least 256 bits of cryptographic randomness and
enforce their expiry. Store capability hashes, not plaintext credentials. Intent creation returns
distinct browser and desktop capabilities so a verification link cannot read or
submit a report. Use strict same-origin browser requests, origin validation, no
third-party analytics, and no report content in request logs. CORS and a packaged
app identifier are not authentication. Validate actual streamed request size as
well as Content-Length. Use prepared SQL statements.
[Turnstile validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/).

## GitHub delivery and recovery

- Store the GitHub App private key and Turnstile secret in Worker secrets. Use a
  fixed server-configured repository; callers cannot choose the destination,
  labels, assignees, or URLs the service fetches. No secrets ship in FPVS Studio.
- Create issues using a fixed template and existing `bug` / `needs-triage` labels.
  Include the description, app/OS version, receipt ID, and a reviewed error excerpt.
  Limit the generated issue body to 24 KiB; full diagnostics stay in D1. Escape
  user content for each rendering context and suppress unwanted mentions.
- Optional contact email stays in D1 rather than the issue body. The reporter must
  be told that optional contact and full logs expire; their written description
  and error excerpt in GitHub have a separate lifetime.
- Save delivery state before making the GitHub request. Unique report IDs,
  payload hashes, and conditional leases prevent concurrent submissions/retries
  from generating multiple issues. Reusing an ID with different content is 409.
- Use a small indexed D1 outbox and a bounded scheduled Worker pass for retrying
  definite transient failures; honor GitHub Retry-After and rate limits. Do not
  rely on an unawaited background task for durable delivery.
- GitHub issue creation has no transaction shared with D1. If the response is
  lost after creation may have succeeded, mark delivery uncertain and reconcile
  the exact receipt marker before retrying. Do not blindly POST again. If certainty
  cannot be established, require maintainer review rather than claim exactly-once
  behavior. Concurrent cron invocations must respect the same lease.
- The maintainer reads issues in GitHub and retrieves full logs by receipt ID
  through the authenticated Cloudflare D1 dashboard or an authenticated operator
  command. Version one needs no public diagnostic-download or admin endpoint.
- GitHub notifications alert the maintainer according to their repository settings.
  GitHub comments do not email reporters who lack a GitHub account; follow-up is
  manual using the optional address, while retained.
[Issue API](https://docs.github.com/en/rest/issues/issues#create-an-issue),
[GitHub App installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation),
[Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/).

## Staying within the free plans

Verified published allowances on 2026-09-12:

| Component | Relevant free allowance | Design response |
| --- | --- | --- |
| Workers | 100,000 requests/day; 10 ms CPU/invocation | Small requests, bounded polling, no archive processing; measure CPU before rollout |
| D1 | 5 million rows read/day; 100,000 rows written/day | Indexed queries, bounded retries and cleanup |
| D1 storage | 500 MB per free database; 5 GB account total | One database with a lower application cap |
| Turnstile | Free plan with unlimited challenges | Use one widget restricted to the reporting hostname |

Sources: [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[Turnstile plans](https://developers.cloudflare.com/turnstile/plans/).

Initial service caps: 100 accepted reports/day, 200 MiB of retained report payloads,
and 1,000 verification intents/day. At 100 reports/day and 128 KiB/report, 14 days
of payloads use at most 175 MiB before database/index overhead. Delete expired
payloads and intents in bounded scheduled batches; cap metadata separately and
retain receipt/deduplication metadata for 30 days. Reserve quota atomically in D1,
including in-flight reports, so concurrent requests cannot oversubscribe storage.

Apply best-effort per-IP burst limiting before D1 access and a durable global
quota before accepting payloads. Account for labs sharing a public IP. Cloudflare's
Worker rate limiter is approximate and local to a location; it cannot be the
global storage counter. A public endpoint can still exhaust free request capacity
under abuse. Keep drafts local and fail visibly when service capacity is exhausted.
Avoid storing raw IP addresses in application tables; any persisted abuse-control
keys must be short-lived keyed hashes, excluded from reports and purged daily.
[Rate limiter accuracy](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/).

Workers and D1 quotas are shared with other services on the account. Confirm the
account is actually on Workers Free; an existing paid subscription changes billing
behavior. Free D1 rejects operations at its limits instead of automatically adding
paid usage. Do not promise that quotas equal guaranteed uptime, and do not enable
a paid plan automatically. CPU profiling must include cold GitHub App signing,
maximum payload parsing, Turnstile validation, and outbox processing. If 10 ms is
not viable, revise the free design before rollout; a paid upgrade is outside scope.

R2 remains a future option requiring a new decision: it requires a subscription
checkout and can bill above its included usage.
[R2 onboarding](https://developers.cloudflare.com/r2/get-started/).

## Desktop diagnostics and ownership

Current startup does not configure persistent application logging. The shared
`gui/window_helpers.py::_show_error_dialog` already formats exception tracebacks.
Use this seam for handled errors and a thin startup hook for unexpected exceptions.
Do not promise complete diagnostics after native crashes, abrupt termination, or
power loss; show any available previous-session error only on the next launch.

Proposed new desktop package: `src/fpvs_studio/support/`, GUI-neutral and responsible
for the report contract, bounded logging, redaction, drafts, and HTTP client.
Add its package AGENTS.md when implemented. Wire it from the thin `app/main.py`
entry point; UI owns the editor and worker lifecycle, not payload construction.
Do not import PsychoPy for metadata collection or run hardware probes to report a bug.
Do not modify RunSpec, SessionPlan, project models, or runtime export contracts.
Keep the Cloudflare service in its separate repository and deployment lifecycle.

Use a dedicated OS-local FPVS Studio support directory for logs and drafts, separate
from projects and the updater cache. Resolve it through an explicit platform path
helper, never the working directory or installation folder. Project-facing exports
continue to use the active project root. **Save report** writes only to the user's
chosen path, treats cancellation as no-op, and reports write errors explicitly.

Configure bounded application-owned logs: proposed 1 MiB per file, three files per
process/session and a 10 MiB total retained budget. Avoid multi-process rollover
collisions and recursive logging failures. Logging must not synchronously flush to
disk inside the presentation hot loop. Limit each record and preserve relevant
tracebacks; diagnostic collection runs after presentation, never during timed frames.

Allowlist app/build version, OS, and already-known relevant settings. Redact user
home/project prefixes, participant identifiers, and secret-looking values; avoid
capturing them at source wherever possible. Do not include entire environment
variables, project files, participant exports, responses, stimulus names/content,
or arbitrary files. Redaction is best effort, so exact-payload review remains required.
Opening the dialog does not upload diagnostics; only the reviewed Submit action does.

Keep unsent drafts for up to seven days, max five drafts under a separate bounded
budget, with explicit discard. Purge according to that disclosed policy; never
delete project output. Removing a D1 payload after 14 days does not immediately
remove recoverable backup copies: Free D1 Time Travel retains recovery history
for seven days. Document this and the separate GitHub retention honestly.
[D1 recovery limits](https://developers.cloudflare.com/d1/platform/limits/).

## Implementation order and acceptance

1. **Account and feasibility check:** inspect the active zone/hostname, free plan,
   shared usage, and proposed private repository. Measure a minimal Worker/D1/
   GitHub-auth prototype within the Free CPU budget before building the full UI.
2. **Service contract and backend:** implement strict validation, verification,
   receipts, quotas, private GitHub delivery, uncertainty reconciliation, cleanup,
   and an operator runbook. Test with synthetic text only.
3. **Desktop diagnostics:** add bounded logs, reviewed payload construction,
   crash/handled-error capture, local drafts, and offline text export.
4. **Desktop UI:** deliver the native Report a Bug surface specified above, including
   **File > Report a Bug...**, both tabs, submission
   states, draft recovery, and registered GUI smoke tests. Reuse `gui/components.py`
   and implement worker cancellation from the first pass.
5. **Staging acceptance:** isolated database and GitHub test destination; prove
   successful delivery, duplicate retries, GitHub outage, expired verification,
   quota exhaustion, redaction, retention, and draft recovery. No real reports in tests.
6. **Production rollout:** deploy the service, validate the exact subdomain and TLS,
   confirm the homepage and email DNS remain healthy, then ship the desktop feature.
   A server-side submissions switch permits disabling intake while preserving
   receipt lookup and local save. Record deployment version and rollback procedure.

Backend tests must exercise capability separation, token replay, payload mutation,
unauthorized receipt reads, streamed oversize requests, concurrent quotas/leases,
ambiguous GitHub outcomes, cleanup with pending deliveries, and safe rendering.
Do not automatically retry an expired pending report as a new submission. Alert the
maintainer through a runbook/dashboard check before its payload retention expires.

Desktop tests must cover missing/unwritable support directories, long/non-ASCII
Windows paths, incomplete log files, redaction fixtures, explicit diagnostic removal,
offline save/cancel, restart recovery, worker shutdown, and absence of project I/O.
Registered Qt tests cover both themes at the minimum/default size, long descriptions
and status text, every submit state, and absence of Welcome reporting buttons. Stub network,
browser, file pickers, and modal error calls.

Run GUI and repo focused verification for desktop implementation, then repo
precommit for shared startup changes. Apply the project-path and GUI skills; use
the pytest-qt skill when adding registered tests. Local Qt execution remains limited
to a user-approved safe visible environment; never run offscreen Qt locally.
Service tests run in that service repository with its own instructions. Update
ARCHITECTURE.md, the agent index, GUI_WORKFLOW.md, and support/service contracts when
implementation establishes the new owners; do not describe planned behavior as shipped.

## Earlier planning validation

The original 2026-09-12 planning change affected only this plan and `docs/PLANS.md`.
`./scripts/verify.ps1 -Scope docs -Tier focused` passed on 2026-09-12: documentation
hygiene and all nine harness-documentation tests. Current desktop implementation
and the deferred service work are recorded at the top of this plan.
