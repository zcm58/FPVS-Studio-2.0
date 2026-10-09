# Streamlined whole-project review uploads

Status: Active

Desktop source ships in Studio 2.4.2; visible synthetic Qt verification passes.
Cloudflare production activation is complete. Authenticated end-to-end
upload/email/validation/publication qualification remains pending.

Date: 2026-10-08

## Approved outcome

Reuse the existing clean publication exporter, submission transport, private GitHub
drafts, administrator review and accepted catalog overlay. File > Export > Upload
Project for Review opens a compact form with prefilled project title/description,
author/contact and sharing permission. Upload automatically prepares and submits all
conditions and required assets. Submission does not require Library enrollment or a
contributor grant. The exact uploaded bytes remain immutable and retries reuse the
same request. Research data, logs and credentials stay excluded.

OpenFPVS emails the administrator after a complete upload, with GitHub/admin review
links. The administrator validates and tests the project, then publishes the same
GitHub draft. The existing catalog automatically reconciles that publication; signed
bundle validation and withdrawal checks remain required for Library delivery.

## Owners and lean implementation

- Studio keeps core/developer clean preparation, app-owned GUI jobs and the existing
  bounded Library HTTP transport. Retain the enrolled condition API for older clients.
- A separate OS-protected upload token permits own-upload status/retry without granting
  Library access. No GitHub credentials or participant data enter project files.
- Sibling `../OpenFPVS` extends its existing review queue with an additive migration,
  public submission routing, existing email delivery and publication reconciliation.
  Reuse quota, exact-asset, catalog and safety owners; avoid new storage services.
- Keep optional help/inventory details out of the main form. GUI coverage remains
  registered visible opt-in; ordinary local verification does not instantiate Qt.

## Acceptance

- [x] Whole-project preparation preserves every condition and excludes research/private files.
- [x] One Upload action handles save, preparation, delivery, errors, cancellation and exact retry.
- [x] A never-enrolled client can upload and read its own status without Library access.
- [x] Completed upload emails the administrator once; failure preserves the submission for retry.
- [x] Publishing the exact validated draft updates catalog/status without a second approval action.
- [x] Incomplete/changed/rejected/withdrawn/unvalidated bundles stay withheld.
- [x] Existing enrolled clients, approved catalogs and Library access continue to work.
- [x] Focused Library/GUI/docs and sibling synthetic tests/syntax/dry build pass.
- [x] Run safe precommit; investigate its two Windows rename failures with fresh-folder regressions.
- [x] Document activation, approved visible smoke and production qualification boundaries.

## Source verification and delivery record

The existing exporter remains unchanged. Studio reuses PublisherService preparation,
LibraryClient streaming and OS credential storage under a separate submission namespace.
The compact form automatically chains preparation/upload and retains original bytes
for retry. New `submitted-<UUID>` items support whole-project signed proofs while
legacy `reviewed-<UUID>` rules and enrolled APIs stay intact.

Sibling migration 0014 preserves every queue/review field and existing device linkage.
Confirmed uploads trigger the existing Resend sender, with atomic notification state
and a ten-minute schedule for bounded retries. The returned GitHub draft `html_url`
is pinned and retained. Catalog reconciliation verifies original release/tag/asset
and signed admission, including rejection/withdrawal races.

Library focused: 362 passed, 3 Windows symlink privilege skips, 20 subtests.
GUI focused: 17 passed; docs focused: 10 passed; CheckConfig: 14 scopes passed;
repo focused: 52 passed. Library full now explicitly routes the registered upload
dialog module, so approved visible verification can use the narrow Library scope.
Safe precommit passed changed-file Ruff/compilation, mypy over 228 source files,
registry and documentation audits. The full safe suite completed with 2,880 passes,
11 Windows symlink privilege skips and 20 subtests, plus two existing temporary-folder
rename failures (`WinError 5`) in Library publishing/media portability tests. All
seven related parametrized cases passed in fresh short folders, and the final
Library focused run passed the publishing coverage again. No fallback or unrelated
project-I/O change was added; the original full gate retains its failed-run record.
OpenFPVS: all 329 synthetic tests passed, including real workerd/D1 legacy and
independent uploads, signed multi-condition admission, notification failures,
immutable receipts, direct GitHub publication and admin controls. Required syntax,
binding generation and dry packaging passed. Dry output and synthetic test log are
in sibling `.wrangler/streamlined-upload-20261008/` (ignored, no production secrets).
The admin queue was checked in a separate visible browser with local synthetic
data at 1280 and 360 pixels. Long title/contact, expanded upload details, unsafe,
withdrawn, published, empty and error states fit without horizontal overflow.
Existing website components/styles are reused; obsolete publication instructions
were removed. Screenshots/snapshots are retained under that folder's `browser-checks/`.

At initial source acceptance, local Qt execution and live submission/email/publication
were unperformed. The October 9 integration verification below records subsequent
visible Qt acceptance. Live submission/email/publication remain unperformed; the
desktop changes ship in [Studio 2.4.2](../completed/release-2.4.2.md).
Initial production preflight
returned Cloudflare D1 code 7403; a later retry using the same limited login succeeded
without changing account scopes. At that preflight, only migration 0014 was pending. The existing D1
database was exported to sibling ignored private backup
`.wrangler/private-backups/before-project-submissions-20261008-184732.sql`
(28,859 bytes; SHA-256 `33e351e3c2b0031f91c3934bcffd45965f6883cd7477b55439025f8eee539b43`).
Applying 0014 to that backup in memory preserves all 13 device rows, the empty
submission queue, and valid foreign keys. Synthetic migration coverage also preserves
every field of populated legacy review rows. The export temporarily reserves database
access and has completed. No live migration/deployment or account-scope changes occurred.
Preserve the existing limited login/domain configuration for activation.

Production migration/deployment and a Studio installer release are separate delivery
operations; prepare reviewable artifacts and verification before any required approval.

## October 9 Studio integration verification

The user authorized visible synthetic Qt tests. After merging the reporting/upload
updates with the worker crash fixes and automatic crash reporting, all 78 selected
Qt 6.11.2 checks pass, including this upload dialog's states, geometry, explicit
confirmation, cancellation, long-error accessibility and preserved title. The same
selection covers data-sharing dialogs, startup status, crash recovery and native worker
cleanup. All network responses are fake and account-local settings are isolated.
Evidence is retained in ignored `build/merge-studio-visible.xml`; the temporary Qt
dependencies were removed. This does not establish live upload, email or publication.
The full merged source checks and Windows save-retry test caveat are recorded in
[the automatic crash-reporting integration record](automatic-crash-reporting.md#october-9-remote-integration).

## Cloudflare activation: 2026-10-09

The user authorized activation. Sibling OpenFPVS source `a134828` passed all 329
synthetic tests, syntax checks, binding type generation and dry packaging. A fresh
private database export and recovery bookmark preceded application of only 0014.
Live read-only checks confirmed preserved baseline row counts, all 13 devices,
zero foreign-key violations and the new submission columns; no migrations remain.

Worker `008f34b9-57aa-4633-83d0-0872751f5499` is deployed with whole-project uploads
enabled and ten-minute notification retries. The existing limited login, domains,
native hostname, secrets, variables, D1 binding and runtime settings are preserved.
All 36 bounded anonymous live checks and five exact browser asset hashes passed.
The canonical activation/evidence record is sibling `../OpenFPVS/CONDITION_REVIEW.md`.

Cloudflare activation, visible synthetic Qt checks and the Studio 2.4.2 release
are complete. Authenticated native upload/email/validation/publication qualification
remains unperformed. No project submission, provider email or publication was used
as a deployment smoke test. Keep this plan active for that remaining check.
