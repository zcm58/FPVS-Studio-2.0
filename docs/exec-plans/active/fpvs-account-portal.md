# OpenFPVS account portal

Status: Active

Date: 2026-10-06

## Standalone website maintenance checkout (2026-10-06)

The private OpenFPVS website/service checkout now lives in the sibling
`../OpenFPVS/` at `C:\Users\zcm58\PycharmProjects\OpenFPVS`, opened as its own
PyCharm project. The move retains its existing Git history/remote, Worker, D1,
accounts, permissions and local credentials. Studio contains only integration
documentation; the private project's `PORTAL_PLAN.md` owns website implementation
and deployment acceptance. Dated deployment evidence below keeps its historical
paths and facts rather than describing the current maintenance directory.

## Portal domain migration (2026-10-06)

The current portal destination is `https://openfpvs.com`, replacing the previous
browser address at `fpvs.zack-murphy.com`. The migration keeps the same Cloudflare
Worker, D1 database, accounts, reusable lab codes, grants and experiment catalog.
It introduces no access reset, database migration or paid service. Existing
account credentials and lab codes continue to identify the same access.

Native Studio retains
`https://fpvs-studio-library.fpvs-studio-zcm58.workers.dev` as its service origin.
That hostname must serve `/v2` directly because the client rejects redirects.
Keeping this origin preserves OS-protected enrollment, cache namespaces and saved
project-origin receipts; the portal move does not require another native
reconnection. Previous `/v1` clients still receive the existing HTTP 426 upgrade
requirement independently of this domain change.

Browser authentication uses host-only cookies. Researchers and administrators
sign in again at `openfpvs.com`; browser sessions do not transfer across hostnames.
The private Library repository owns domain bindings, browser routing, provider
configuration and live deployment acceptance. Studio owns the current integration
links and documentation checks. Earlier deployment evidence below retains its
original hostname and date.

The separate Results service and its opt-in consent, the Feedback service at
`reports.zack-murphy.com`, and the personal website at `zack-murphy.com` remain
independent. The migration stays within the approved free services, without paid
subscriptions or paid overages.

The migration is deployed as Worker version
`91541690-a775-4eef-ad60-9596623c6ee1`. Cloudflare serves both new hostnames; the
old browser address redirects allowlisted pages while native routes stay direct.
Resend verifies the new sender domain with enforced TLS and the existing key's
sending-only restriction moved to `openfpvs.com`. Read-only record counts match
before and after deployment. All 208 service tests, 57 live HTTP checks and the
Studio documentation checks pass. On 2026-10-06, the user confirmed the dashboard
loads at the new `/admin` address with existing credentials. Real email delivery
and an authenticated physical-PC download were not exercised during migration;
the private service plan records those verification boundaries.

## Library access reset and administrator workspace

The user confirmed the administrator login works. The current follow-up organizes
the dashboard into tabs, removes previously enrolled/revoked computer display,
revokes existing library machine credentials, and moves native access to `/v2`.
Valid lab codes remain available for reconnection; local experiments and offline
use stay independent. Browser lab login becomes session-only and browsers no
longer enroll as computers. A verified administrator browses without a lab code
and can toggle administrator/user presentation without changing server identity.

The private service's PORTAL_PLAN.md owns backend/reset/deployment detail. This
repository owns the native credential migration and a focused 2.2.6 release from
master, including the lab-code startup/reconnection workflow. The user chose to
exclude the separate unreleased results-sharing work. The public release note is:

> Updated experiment backend server, which means all pcs will need to reconnect with their lab code before being able to access the experiment library again.

- [x] Native v2 routes and secure cached-credential reconnection coverage.
- [x] Private-service reset, browser/admin authorization and dashboard acceptance.
- [x] Focused and precommit verification; documented GUI/platform boundaries.
- [x] Focused release artifacts, publication, digests and updater selection.

The private service passes all 204 tests and is deployed as Worker version
`423b806b-9e55-4553-b95e-d51f469bb8d5`. D1 was backed up before the additive reset;
six old credentials were revoked while the reusable lab code, grant, account and
administrator web sessions were preserved. Live public boundaries, v1 upgrade
responses, v2 authentication and seven asset digests pass. Synthetic browser
acceptance covers keyboard tabs, exact-version editor links, the Library view
toggle and view-only/disconnect behavior at desktop/mobile widths.

The isolated master-based release includes startup and native v2 changes without
results-sharing source. All focused scopes pass. Mypy checks 213 files; the full
non-Qt run passes 2,605 tests with 11 Windows symlink skips and one Windows rename
denial. Both affected bundle-transfer cases pass an isolated rerun without source
changes. The separate release plan records artifact and GUI/platform acceptance.

Studio 2.2.6 is published as the latest release at
`https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.6`, built from
`2a4a4e44845b663f0e9f5767cf7ec4e9d1bd02ca`. All six public asset sizes/digests and
the exact release note match local evidence. The full 7,985-file payload and direct
2.2.5 patch reconstruct identically. The approved visible packaged smoke and all
67 startup/Library GUI tests pass. Seven live updater cases verify the authenticated
2.2.5 patch, full fallback/forced full, older versions and no update at 2.2.6.
Evidence is retained under `build/release-2.2.6/`. Installer lifecycle, a second
physical PC and real experimental/EEG execution were not run. The unreleased
results-sharing feature remains on its separate branch.

## Dedicated administrator password login

The approved follow-up gives `/admin` a dedicated administrator login and dashboard
landing, an `/admin/sign-in` entry alias, seven-day browser sessions and email
recovery. Firebase Authentication's free Spark plan handles the administrator's
password. The existing Cloudflare service mediates fixed provider routes, pins
the administrator email/UID/project number and reuses the verified D1 profile.
Encrypted provider refresh credentials link to hashed web sessions through
additive `0005_admin_password_sessions.sql`; protected requests check revocation.
Passwords and provider tokens never enter browser storage or logs. Independent
email and lab-code flows remain compatible. Studio and the personal website are
unchanged; implementation belongs to the private Library service.

- [x] Password/recovery integration and dedicated login/dashboard flow.
- [x] Synthetic session/security service tests and documentation checks.
- [x] Synthetic desktop/mobile browser acceptance and dry packaging.
- [x] Reviewed deployment, additive schema and live public-route/asset/boundary verification.
- [x] Authorized Firebase project creation and confirmed Spark free plan.
- [x] Provider bindings and administrator-selected password.
- [x] Real administrator password login and dashboard landing confirmed by the user.

Missing provider configuration disables password actions explicitly and retains
email recovery. No billing account, paid plan or overage is allowed.

All 183 private-service tests and 10 Studio documentation tests pass. Dry packaging
passes at 91.25 KiB (21.17 KiB gzip). Synthetic administrator/login checks at
1280px/360px cover wrong-password clearing, recovery, unverified email, revoked
sessions and provider interruption; missing configuration and researcher boundaries
are covered by tests. The additive
`0005_admin_password_sessions.sql` migration and Worker version
`659f997a-f94b-4970-ae0c-4ad572b41948` are deployed. Live public routes, protected
boundaries and code/style assets are verified. The user explicitly approved
Firebase setup, personally accepted its Terms and created the **OpenFPVS** project,
and confirmed the no-cost Spark plan. Previous console-approval/Terms blockers are
resolved. Email/Password is enabled, and the user personally selected the
administrator's password. The exact Firebase UID/project number are deployed as
pinned Worker variables; the session-encryption key was generated directly into an
encrypted Worker secret. The user explicitly approved saving the Firebase API key
as an encrypted Worker secret, and the dashboard confirms the binding. Live password
controls are enabled. Spark remains free without a Cloud Billing account.

The administrator confirmed real password login and dashboard landing work.
Recovery/provider interruption have synthetic coverage; acceptance did not force
a real password reset.

## OpenFPVS website simplification

The current follow-up renames the website **OpenFPVS Experiment Library** and its
administrator **OpenFPVS Administrator**. Remove stimulus-set labels from reader
and administrator editor flows, website category filters/tags, reader artifact
details and the requested counter/footer paragraphs. The warm tan/muted green
theme and top navigation remain. Account controls distinguish **Login with a Lab
Code** from **Individual Account Login**; the lab-code entry stays independent of
email sessions, while individual login is replaced by signed-in controls.

Reader pages show **x total downloads** for the experiment across all its recorded
versions/digests, including retired artifacts. The technical count remains
authorized native/browser starts after upstream validation and the final access
check, so later cancellation/failure can count. Preserve exact-version/digest
description/publication metadata, compatible technical count fields, native
catalog categories and the original streaming path. The historical D1
`stimulus_set` column remains dormant; no database migration is needed. This work
belongs to the existing private service; Studio GUI and the personal website are
unchanged. Completed sections below retain their historical evidence.

- [x] Website removals, brand/role wording and independent lab/email controls.
- [x] Cross-version/digest aggregate and current browser/admin content contracts.
- [x] Synthetic desktop/mobile checks, service/docs gates and live deployment.

All 150 service tests pass, including aggregate-history and native workerd/D1
coverage. The later same-page lab-login focus correction passes all nine focused
navigation tests. Synthetic 1280px/360px browser checks cover both login choices,
lab-code-only access, search, version switching, experiment totals, publications,
administrator saves and sign-out that preserves the lab connection. Changed
catalog/detail/editor surfaces fit without body overflow. Ignored
`build/openfpvs-*.png` retain desktop, mobile and live public evidence.

Syntax/diff checks, 78.46 KiB dry packaging and all 10 documentation checks pass.
Worker `70ae9d09-2bc7-4f75-8455-3e5b2ac47531` is deployed. Read-only live public
and protected-API denial checks pass; five code/style/logo assets match source.
The live browser confirms OpenFPVS branding and both login choices. No migration,
real email, live account/code mutation or paid feature was needed. Protected
real-account and second-machine acceptance remain the pre-existing separate checks.

## Portal navigation and website theme

The user requested a top header, optional account controls that change after
sign-in and clearer stimulus-set wording. After reviewing Studio's colour palette,
they chose to keep the original warm tan and muted green website theme.
The private service owns these website changes; no desktop GUI or personal
website changes are needed. Lab-code browsing stays independent of email sign-in.

- [x] Clear top navigation and exact-release stimulus label help.
- [x] Server-confirmed account/owner controls and session lifecycle regression checks.
- [x] Synthetic desktop/mobile browser acceptance, service/docs gates and deployment.

All 145 private-service tests pass, including 11 new session/navigation checks and
native workerd/D1 fixtures. Synthetic browser acceptance covers lab-code-only,
researcher and owner states, sign-out without lab disconnection, browser-history
restore, keyboard navigation and probe error/retry. Catalog/detail/account/editor
content fits 1280px and 360px without body overflow. The optional stimulus-set
label names existing images/words, with an example and associated help; empty
labels are omitted. The final colours retain the original warm tan/muted green
theme and a dark green top header. Ignored `build/library-portal-*.png` retain
synthetic and live public screenshots.

Syntax/diff checks, 78.24 KiB dry packaging and the 10 documentation checks pass.
Worker version `d4ce1a9a-91fb-478c-9b2b-02bb43362ffa` is deployed. Read-only
live public/security checks pass; five changed code/style/logo assets match source
and the browser shows the final lab-code homepage. No database migration, real
email, live account/code change or paid feature was needed. The pre-existing
protected real-account and second-machine native acceptance checks remain separate.

## Experiment website follow-up

The user authorized a clean lab-code-protected experiment website, with citations
for the exact experiment stimulus set/version and recorded download totals, managed
from the owner portal. The website supports discovery, version reference pages and
bundle downloads; Studio handles setup, version updates and running experiments.
Its Welcome screen already accepts dropped `.fpvsbundle` files. Private GitHub
assets stay behind Cloudflare download authorization, so researchers need lab
codes rather than repository membership. The personal website stays independent.

Separate browser APIs preserve the strict native catalog. Canonical device auth
also checks browser credentials, while owner-only metadata edits retain session
identity, origin/CSRF and audit protection. Additive website metadata and authorized
download-start counts bind to item ID, version and bundle SHA-256. Counts start at
feature launch and include repeat starts. Denied/unavailable requests do not count;
transfers failed or cancelled after starting may count. Totals do not represent
completion, unique users or confirmed local imports. New versions do not
inherit old publication claims. Existing verified Studio publishing owns package
uploads; the service GitHub App remains read-only.

- [x] Session, permission/revocation, exact-version metadata and migration tests.
- [x] Download-start counting and failure/cancellation regression checks.
- [x] Catalog/detail/admin editor browser checks at 1280px and 360px.
- [x] Service tests/syntax/dry build, docs and reviewed live deployment.

All 134 private-service tests pass, including actual workerd/D1 checks, 500-item
metadata joins, migration preservation and atomic per-artifact counts. Syntax,
diff checks and 77.63 KiB dry packaging pass; Studio's documentation focused gate
passes 10 tests. Synthetic browser acceptance covers lab connection, search,
category filters, exact-version selection/download, view-only access, browser
disconnect and owner metadata/publication saves with version isolation. At 1280px
and 360px, catalog/detail/editor layouts have no body overflow. Ignored screenshots
under `build/experiment-library-*.png` retain synthetic and public live evidence.

A 512 MiB actual local workerd profile verified native streaming without full
buffering. Completion tracking through JavaScript on every chunk regressed that
path, so final **Downloads started** tracking uses one scheduled D1 write after
upstream validation and final authorization. It preserves the original native
transport and makes no completion claim.

The existing remote D1 database has a private pre-website local backup and additive
`0004_library_content.sql` applied. Worker version
`86cca457-4c5a-4de8-9915-4d35ca2b21ef` is deployed. Live public-page/security
checks pass on the custom and retained native hostnames; all changed code/style
assets match source hashes, and the browser confirms the lab-code landing page.
Real protected catalog/download/editor checks and second-machine native acceptance
remain separate. No live accounts/codes were changed, real emails sent, or paid
features enabled. This plan remains active for the pre-existing live acceptance gap.

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
and administrator page at `https://openfpvs.com`. Initial sole administrator
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
is the standalone sibling `../OpenFPVS/`, opened as its own PyCharm project;
Studio retains only integration documentation. Its canonical plan is
`PORTAL_PLAN.md`, and its migrations preserve legacy computer enrollments.
Keep the existing service hostname functional for
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
and the additive account migration is applied. On 2026-10-05, the tested Worker
was deployed and `fpvs.zack-murphy.com` was attached. Live HTTPS checks verified the
public-page 200 and anonymous account/admin/Library denial; the old native hostname
remained active.
Cloudflare's secret inventory confirms `RESEND_API_KEY` is stored as an encrypted
Worker secret. After the owner registration/sign-in instructions, the user reported
"Everything appears to work now" on 2026-10-05. This is user-reported live portal
acceptance; owner email delivery and sign-in are no longer setup blockers.
No paid subscription or overage consent has been activated.

The plan remains active for live enrollment/download/revocation on another machine.
Those flows pass synthetic coverage, but the user's portal confirmation does not
establish that separate native acceptance check.
