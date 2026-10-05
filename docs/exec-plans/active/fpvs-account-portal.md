# FPVS account portal

Status: Active

Date: 2026-10-05

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
