# Clear Error Messages And Studio 2.2.5

Status: Active

## Authorized scope

The user requested plain-language common errors, a “Report this bug. Please!”
action whenever an error popup appears, optional reproduction notes through the
existing reporting service, and publication of Studio 2.2.5. This supersedes the
earlier File-only reporting preference. Experiment content is unchanged.

Release notes must be exactly: “simplified user facing error messages and streamlined
bug reporting”. The user requested skipping visible Qt tests and packaged GUI smoke;
report these as unperformed rather than running them.

## Implementation

- Add GUI-neutral explanations for common filesystem, connection, dependency,
  compatibility, validation and unexpected errors, following chained exceptions.
- Decorate Studio error message boxes centrally, including first-run/no-project
  errors. Preserve confirmation choices, error details, and explicit submission.
- Reuse the app-owned reporter and workers. Prefill required descriptions and
  diagnostics for a fresh report; preserve existing writing and locked receipts.
- Register Qt coverage for popup buttons, modality, drafts, limits, and geometry;
  run safe GUI/support checks and repo precommit. Qt execution requires a safe
  visible-session opt-in and must never use offscreen mode.
- Update canonical workflow docs and bump pyproject.toml only. Build isolated
  release-2.2.5 outputs with authenticated 2.2.4 baseline/native dependencies.
- Audit the installer, direct patch and checksums; publish matching source/tag
  and verified release assets without replacing earlier releases or installations.

## Verification and release evidence

Implemented shared error explanations/reporting, bounded/redacted error prefilling,
optional reproduction notes, and registered popup/report-editor coverage. Existing
confirmation choices, unfinished drafts, locked receipts and the service protocol
are preserved. The report action never submits automatically.

- Support and common-error focused tests: 44 passed, one Windows symlink skip.
- Safe GUI focused: Ruff, compilation and seven non-Qt checks passed. Docs: nine
  passed. Packaging: 181 passed.
- Repo precommit: Ruff, compilation, mypy (214 source files), harness and docs
  audits passed. Safe suite: 2,554 passed, 11 symlink skips and one sandbox-denied
  Windows named-pipe test; its isolated ordinary-context rerun passed (2,555 total).
- The published 2.2.4 full installer and all 7,061 extracted owned files were
  authenticated against GitHub. Baseline inventory SHA-256 is
  `9037a79a974a5307b4ea5428b67ced6056d69a4e4e153ff3f2e530628e56b459`.
- The final popup-dismissal guard passed refreshed safe GUI/type checks. Final
  packaging must include this source revision and pass embedded source parity.

Build and publication are pending. Visible Qt tests and packaged GUI smoke were
skipped at the user's request. No clean-PC installation, installed-update test,
live report submission, or physical experiment/EEG test is part of this release.
