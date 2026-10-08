# Condition Library review

Status: Completed

Date: 2026-10-07

## Authorized behavior

An enrolled Studio computer may submit one condition and its required assets for
manual OpenFPVS Administrator review. Approval publishes only the exact reviewed
bundle; future edits require a new submission. No general publishing permission,
experimental results, participant history or GitHub credentials are granted.
Keep the existing Library audience and authentication requirements.

## Ownership and verification

1. Extend canonical clean bundle preparation with selected-condition dependency
   closure; verify ordinary import/compilation and unchanged source files.
2. Add enrolled-device submission/status transport and app-owned GUI jobs;
   verify bounded upload, retries, cancellation and registered GUI coverage.
3. In sibling OpenFPVS, add private artifact storage, a review queue, exact-byte
   download, rejection and explicit tested-version acceptance/publication;
   verify owner/CSRF/device boundaries, immutable uploads and hidden pending items.
4. Run focused Studio checks, safe precommit, OpenFPVS Node/runtime tests and dry
   packaging. Document visible/manual and live deployment boundaries.

The user chose the existing private GitHub repository's draft Releases for bundle
storage. Tags identify requests; draft visibility plus an accepted-only D1 catalog
overlay enforce review. No R2 binding or paid service is added. Production permission and deployment changes require explicit maintainer approval;
the approved activation and release are recorded below.

## Progress

- [x] Selected-condition clean bundles and regression coverage.
- [x] Studio submission/status GUI and client.
- [x] OpenFPVS review queue and publication.
- [x] Safe local verification and deployment instructions.
- [x] Approved visible native GUI and packaged smoke checks.
- [x] Production App permission, additive migration and service activation.

## Development verification before release isolation

The tracked development branch was pulled with `--ff-only`; it was already current.
At that stage both source checkouts used `codex/condition-review`; source changes
were uncommitted. This historical run included unrelated results-sharing development
and is not the released-source verification record.

Studio Library focused verification passed 307 tests with three Windows symlink
privilege skips, GUI focused passed 17 safe non-Qt checks, and docs focused passed
10 checks. Verification configuration passed for all 14 scopes. Safe precommit
passed lint, compilation, mypy (227 files), harness/documentation audits and 2,743
non-Qt tests with 11 Windows symlink skips. After that run, two additional word/AB
dependency tests were added; all 12 submission unit tests and their Ruff check pass.
Bundle checks used native Windows access required by existing hard-link operations.

OpenFPVS's final suite passed all 222 Node tests, including native workerd/D1
concurrency and streamed upload checks with mocked GitHub. Required JavaScript
syntax checks, `npm run check`, diff checks and Wrangler dry packaging pass.
Synthetic browser review at 1280px and 360px fits long names/contact/checksums without
body overflow. Explicit testing confirmation, accepted/rejected states, empty and
connection-error/retry controls were exercised. Browser fixtures contain no real
accounts, credentials or submissions.

Registered Qt coverage was added but not run: repository instructions require an
explicitly approved visible environment. These source checks do not establish
installed-build behavior, actual experiment execution or live GitHub/service
publication. Production configuration retains submissions disabled; no permission,
migration, deployment or paid-service change occurred.

## Completed activation and release

The isolated Studio release and companion integration are committed and pushed.
Studio 2.3.0 is public and the review feature is enabled on OpenFPVS. The user
explicitly approved the fixed-private-repository App Contents write permission,
visible GUI verification and production deployment. Five new registered GUI
tests and the packaged visible smoke pass. The additive D1 migration was applied
after a private local backup. The deployed feature preserves the website rename,
research tags and concurrent Toolbox download-link fix.

See [the 2.3.0 release record](release-2.3.0.md) for exact source/Worker versions,
authenticated artifact audits, current-source test counts and live endpoint checks.
Live authenticated submission/testing/rejection/acceptance was not exercised on
this unenrolled Windows profile; this verification boundary does not claim actual
experiment execution or installed-upgrade acceptance.
