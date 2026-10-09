# Automatic crash reporting

Status: Active

Date: 2026-10-08

## Authorized workflow

The user requested automatic crash reports emailed to their existing maintainer address
(`zmurphy@abe.msstate.edu`) and selected all installations, then requested an opt-out
feature. Settings exposes a separate Diagnostics tab, initially enabled; an existing
saved opt-out remains off. Desktop registration now runs in the background with no
browser, and the switch stays usable during connection work. The user explicitly
approved removing automatic-report browser verification; the matching service source
now uses background installation registration. Users can disable reporting at any time. Manual bug and
feature submission retain their existing per-report review/verification contracts.

Native failures are recovered at the next startup, never by networking in a fault
handler. A session snapshot records preference generation; only sessions started
while enabled in that generation are eligible, including the first launch before
background registration. Sessions while off and older historical sessions are never
backfilled. Unclean exits without native evidence are identified honestly
as unclean shutdowns, not proven crashes. Automatic reports contain app/OS version,
failure category and a bounded sanitized stack, without exception messages, research
records, environment dumps, full support logs or arbitrary attachments.

## Boundaries

- Desktop support owns per-user consent, crash session records, sanitized payloads,
  bounded persistent outbox and installation capabilities in account-local storage.
- The existing app-owned Qt lifecycle owns cancellable background registration/upload
  work. Fault handlers and GUI callbacks never perform HTTP.
- The separate `../FPVS-Studio-Feedback` repository owns installation registration,
  scoped/revocable installation credentials, transactional limits, idempotent intake,
  private issues and email. No service credentials are shipped in Studio.
- Preserve the fixed approved reporting origin, free service plan and configured
  verified recipient. Do not change project, runtime or presentation contracts.
- Crash reports share the existing global report cap; cap automatic reports per
  installation/day, with explicit retention and safe duplicate recovery.
- Reuse the PySide6 cleanup, registered pytest-qt and project-path audit skills.
  The user's earlier visible synthetic Qt approval remains applicable.

## Verification and progress

- [x] Inspect desktop/service ownership and confirm recipient and opt-in scope.
- [x] Run repo focused baseline (52 pass).
- [x] Implement/test service enrollment, revocation, strict intake and quotas.
- [x] Implement/test crash recovery, safe stack extraction, consent and outbox.
- [x] Wire Settings and startup through app-owned workers; register visible coverage.
- [x] Run focused/precommit and visible synthetic Qt checks plus service tests/dry-run.
- [x] Validate deployment availability and document concrete rollout status.
- [ ] Authenticate Cloudflare and perform additive migration, live acceptance and activation.
- [x] Update canonical docs, clean temporary artifacts and summarize limitations.

## Opt-out follow-up

- [x] Change the desktop default to on while preserving existing saved opt-outs.
- [x] Prepare background registration, cancellation, offline/retry/renewal and GUI coverage.
- [x] Run support tests (52 pass, one existing Windows symlink skip).
- [x] Run visible Qt 6.11.2 acceptance (21 pass), including first-launch native recovery,
  responsive real worker, delayed registration, opt-out while busy, dialog close,
  interrupted shutdown, existing preferences and disabled origin. All HTTP is fake.
- [x] Obtain explicit approval for removing automatic-report service browser verification.
- [x] Apply and verify the corresponding backend registration change.
- [x] Finish opt-out repo precommit, documentation verification and temporary cleanup.

Opt-out follow-up verification: GUI focused passes 17 tests, docs focused passes ten,
and the existing Settings regression selection passes ten visible Qt tests in addition
to the 21 automatic-crash tests. Ruff, compilation, mypy (234 source modules) and
repo audits pass. The first full non-Qt run had one Windows access-denied failure at
atomic outbox replacement (2,879 passed, 11 skips); its isolated recheck passes, and
the full rerun passes **2,880 tests with 11 Windows symlink skips**. No source change
was needed between those runs. Isolated Qt dependencies and all applied service-update
helpers were removed; XML verification evidence remains under ignored `build/`.

Automatic approval review rejected running `build/opt-out-service-update.py` because
it removes the separate service's browser/Turnstile verification and allows unattended
registration, a security-boundary change requiring exact user approval. No retry,
alternate execution or backend mutation was performed until the user replied:
"Yes, you can remove browser verification." The prepared change was then applied
with that explicit authorization. Capabilities, revocation, strict payloads and quotas
remain, and manual reports retain Turnstile.

Matching service acceptance now passes **28 synthetic tests**, including no browser/
Turnstile calls for automatic registration, same-capability duplicate renewal without
extra quota, malformed/oversized registration rejection, keyed IP/metadata limits,
automatic/manual capability separation, revocation, expiry, strict payloads,
transactional report quotas and one issue/email after duplicate delivery. Both
production and staging dry-runs pass (43.36 KiB bundle, 12.38 KiB gzip). The unchanged
desktop already passed the opt-out verification above; these service-only edits do
not require another desktop or visible Qt run.

## Delivery status

The earlier opt-in desktop and independent service source were implemented in their
working trees. Desktop and service source now implement the requested opt-out workflow,
including browser-free automatic registration.
Neither the installed executable nor the live service has been changed.
`wrangler whoami` found no authenticated session. A restricted device sign-in was
offered to the user and expired after five minutes without authorization; no migrations,
deployments, live reports or emails were performed. Automatic intake stays false in
both service configs. A fresh limited device sign-in offered after explicit
browser-removal approval also expired after five minutes without authorization.
No migrations, deployments or live email tests were performed in this follow-up.
Live activation requires an authenticated session and
acceptance before enabling that switch; installations require an updated desktop build.

## Source acceptance evidence

- Service: 24 synthetic tests pass, including complete automatic issue/email chaining,
  sanitized email contents, duplicate completion, role separation, revocation/expiry,
  strict schema and transactional per-installation/global limits. Deployment dry-run
  passes with the automatic intake switch false.
- Support: crash recovery/cancellation/outbox tests include real logging child exits
  and native Qt fatal recovery. These use only synthetic account-local records.
- Visible Qt 6.11.2: worker/startup/diagnostics group passes 46 tests. Settings/recovery
  follow-up passes 91 with one pre-existing clipboard assertion blocked by Windows
  OpenClipboard access; an earlier manual feature-editor run has four analogous
  clipboard failures. The final automatic-crash acceptance module passes 16 tests, including
  700x560/700x650 off, verifying, enabled and error states, native recovery, cancellation,
  finished-consent preservation, offline revocation and paused/expired connections.
- GUI focused passes (17 tests), docs focused passes (10). Repo source Ruff,
  compilation and mypy (234 source modules) pass. The first sandboxed precommit run
  has 33 denied filesystem/PowerShell fixture failures, 2,843 passes and 11 symlink
  skips; the permission-correct rerun passes with 2,876 tests and 11 symlink skips. These checks never use offscreen Qt.

## Changed owners and manual smoke

Desktop source: `app/main.py`, `support/diagnostics.py`, `support/client.py`, new
`support/crash_reporting.py`, `gui/application.py`, `gui/controller.py`,
`gui/settings_dialog.py`, and new `gui/crash_report_controller.py`. New unit/registered
GUI modules are `test_automatic_crash_reporting.py` and `test_crash_reporting.py`.
The separate service changes HTTP/verification, migration/storage, delivery, tests,
configs and its README/deployment record. Existing manual reporting/feature requests,
project formats, authoring, runtime and engine contracts remain intact.

Visible manual path after approval/release/activation: open Settings > Diagnostics at
the existing Settings minimum/default size in both themes and confirm reporting on
without a browser; reproduce a synthetic unexpected exit, restart and inspect
the maintainer email/private issue. Test offline queuing and disable during delivery;
confirm the preference stays off on restart and queued files are discarded. Current
  local tests stub network/browser and never enroll the user's actual installation.

Downloaded isolated Qt dependencies and four temporary service patch helpers were
removed after testing. Ignored XML reports retain the visible verification evidence.
The execution plan remains active for the authenticated live activation step.
