# FPVS account portal

Status: Active

Date: 2026-10-05

## Owner-chosen lab codes

The owner may type a custom code when creating or replacing a lab code, or leave
the optional field blank for a secure generated code. Custom codes are case
sensitive, 12–128 printable ASCII characters, and cannot have surrounding spaces.
The server stores only hashes and rejects reuse of historical lab/invitation
codes or the configured legacy code. Rejected replacements must preserve current
access; successful replacements retain the existing explicit confirmation and
atomically revoke previous code/device credentials. No desktop enrollment contract
or database migration changes are needed.

- [x] Synthetic custom-code enrollment, validation, collision and race regressions.
- [x] Owner form browser acceptance at 1280px and 360px.
- [x] Service tests/syntax/dry build, documentation checks and reviewed deployment.

All 97 private-service tests pass, including real workerd/D1 same-code races
and collision rollback. Syntax/diff checks and 61.92 KiB dry Worker packaging
pass. Browser acceptance covers typed creation, Show/Hide, invalid whitespace,
duplicate replacement preserving two PC connections, and successful replacement
revoking both before enrolling with the new download code. Reload/navigation
clears plaintext. Both 1280px and 360px layouts fit without body overflow; ignored
`build/custom-lab-code-desktop.png` and `build/custom-lab-code-mobile.png` retain
synthetic evidence. Studio documentation focused passes all 10 checks.

Worker version `4fef26c6-b7f6-42c3-b3ca-6ac31e162909` is deployed. Read-only live
checks pass on both retained hostnames; changed assets match local source hashes.
No migration, real account/code mutation, real email, paid service or desktop
contract change was needed.

## Reusable lab-code follow-up

The user now prefers PI-distributed lab access over individual researcher email
registration. Add one reusable view/download code per lab, issued and revoked by
the existing verified owner dashboard. Researchers may enroll multiple PCs with
the same code without creating accounts. Existing account invitations and legacy
devices remain compatible; the administrator's email sign-in is retained.

Studio prompts at startup when no local Library enrollment is configured, with
an explicit **Continue offline** option. Reading local protected credentials and
enrollment use app-owned workers. A saved enrollment skips the prompt; startup
does not contact the service or require online access. The code is never persisted
on the PC: existing OS-protected per-device tokens remain the native credential.

The service adds lab code/device linkage through an additive migration. Each
protected request checks the lab code and its permission. Replacing or revoking
a code permanently revokes its enrolled tokens; downloaded experiments remain
local. New clients request optional permission/lab metadata through an explicit
header, preserving older strict response contracts. Library view access must not
enable download or be mistaken for revoked enrollment.

- [x] Multi-PC lab code creation, replacement, revocation and permission tests.
- [x] Owner lab-code cards and enrolled-PC roster, synthetic browser acceptance.
- [x] Startup prompt, saved-enrollment/offline behavior and registered Qt coverage.
- [x] Library/GUI/docs focused checks, service checks and repo precommit.
- [x] Reviewed additive migration/deployment and read-only live verification.

The follow-up passes 88 private-service Node tests, including actual workerd/D1
enrollment/rotation/revocation races and additive migration preservation. Studio
Library focused passes 262 tests (3 Windows symlink skips), safe GUI focused 17,
and documentation focused 10. Repo precommit passes Ruff, compilation, mypy for
223 source files, repository audits and 2,704 unit tests (11 symlink skips).
Registered startup and view-permission Qt tests are not run locally; the manual
visible path remains required before an installed desktop release.

Synthetic browser acceptance creates a view code, enrolls two PCs, revokes one
while retaining the other, replaces the code with download access (revoking the
old connections), and revokes that code. Hidden/reloaded codes are not returned.
Long values fit 1280px/360px without body overflow. Screenshots are retained as
ignored `build/lab-code-desktop.jpg` and `build/lab-code-mobile.jpg`.

The existing remote D1 database was backed up locally before `0003_lab_codes.sql`
was applied. Worker version `696a5dde-3b21-49aa-a6c9-826adadbfd68` is deployed;
live public HTTPS and anonymous account/admin/native denial checks pass on both
preserved hostnames. No real lab code, researcher grant or experimental result
was created for verification. Desktop changes are source on the feature branch;
an updated installer has not been built or published.

## Approved outcome

The user authorized account registration, a private account-management dashboard
and administrator page at `https://fpvs.zack-murphy.com`. Initial sole administrator
is `zackmurphy25@protonmail.com`; the identity must remain configurable for a later
change. Researchers create free verified accounts, request access, and wait for owner
review. Approval grants a named lab access to the experiment Library. Invitations
link enrolled computers to that grant; revocation denies subsequent server requests.
Users never need GitHub or Cloudflare accounts. Downloaded experiments remain local.
Email verification never approves access: every researcher request awaits the
owner's manual review. The final design must use free services only, without paid
subscriptions or paid overages. Cloudflare Workers/D1 host the portal and data;
Resend Free delivers sign-in email with hard UTC limits of 100 daily/3,000 monthly.

## Ownership and boundaries

Implementation belongs to private `zcm58/FPVS-Studio-Library`, alongside its existing
Worker and D1 database, on `codex/account-portal`. The local implementation checkout
is under ignored `build/account-library-service/`; Studio retains only integration
documentation. Its canonical plan is `PORTAL_PLAN.md`, and its migrations preserve
legacy computer enrollments. Keep the existing service hostname functional for
released desktop clients and existing project-origin receipts.

The personal website's main address and hosting remain independent. Result-sharing
consent and the separate Results Worker are outside this portal deployment. Initial
permissions are Library view and experiment download. New grants do not authorize
result submission or experiment publication.

## Verification and deployment

- [x] Verified passwordless email sign-in, pending profiles, bounded single-use links,
  secure session cookies, CSRF and disabled-account checks.
- [x] Owner-only verified email-session checks, lab assignments, invitation issuance,
  atomic computer enrollment, grant/device revocation and administrative audit trail.
- [x] Responsive signup/account/admin pages with loading, pending, denied, empty,
  revoked and long-value states; real-browser synthetic acceptance.
- [x] Existing Library transport regression suite, new SQL/security tests, syntax,
  binding types and dry Worker build.
- [x] Domain and email configuration, non-destructive remote schema migration,
  authorized deployment and live sign-in/read-only acceptance.
- [x] Canonical integration documents and exact implementation/deployment state.
- [ ] Live second-machine enrollment, permitted download and revocation acceptance.

Paid subscriptions, chargeable overages and Cloudflare Access billing activation
are excluded. Tests never send email, query
real researcher records or submit research reports. Owner identity, email delivery and
domain configuration must be confirmed before calling the portal live.

## Verification evidence

The private service's 74 Node tests pass with native Windows access, including
actual workerd/D1 migration preservation and atomic email quotas. Syntax, generated
bindings and the final dry Worker build pass. Studio documentation verification
passes 10 tests. Synthetic browser registration, verification, pending status,
manual approval, invitation issuance and revocation pass; the dashboard fits
1280px and 360px viewports with long profile values. Screenshots are retained under
ignored `build/portal-desktop.jpg` and `build/portal-mobile.jpg`.

Resend reports the sender subdomain verified, with enforced TLS and no tracking
configuration. The existing D1 database has a private local pre-migration backup
and the additive account migration is applied. The tested Worker is deployed and
`fpvs.zack-murphy.com` is attached. Live HTTPS checks verify the public-page 200 and
anonymous account/admin/Library denial; the old native hostname remains active.
Cloudflare's secret inventory confirms `RESEND_API_KEY` is stored as an encrypted
Worker secret. After the owner registration/sign-in instructions, the user reported
"Everything appears to work now" on 2026-10-05. This is user-reported live portal
acceptance; owner email delivery and sign-in are no longer setup blockers.
No paid subscription or overage consent has been activated.

The plan remains active for live enrollment/download/revocation on another machine.
Those flows pass synthetic coverage, but the user's portal confirmation does not
establish that separate native acceptance check.
