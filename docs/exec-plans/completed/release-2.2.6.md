# FPVS Studio 2.2.6 Library Reconnection Release

Status: Completed

Date: 2026-10-05

## Scope

The user selected a Library-only release. Build from stable master plus the isolated
startup lab-code connection feature and native Library v2 integration. Keep the
unreleased result-sharing/comparison feature on its existing branch. Do not change
experiment, participant-data, runtime or trigger contracts.

Native Library routes use `/v2`, retaining JSON schema `1.0`. The separately deployed
service rejects `/v1` with HTTP 426 and revokes previous device access. Studio removes
old secure credentials under the cache lock; reconnection uses a new random token and
the lab's currently valid reusable code. Startup offers connection or Continue offline.
Existing imported projects continue to work offline. Current v2 pending requests
retain their saved token for idempotent retries after a lost response.

## Exact release note

Updated experiment backend server, which means all pcs will need to reconnect with their lab code before being able to access the experiment library again.

## Candidate and release gates

- Stable base: `0deed9f` (published Studio 2.2.5).
- Isolated branch: `codex/library-reconnect-2.2.6`.
- Integrated startup feature: parent commit `47a5bbd`; results-sharing conflict context removed.
- Integrated native v2 behavior: parent commit `cf70ae0`.
- Canonical version: `pyproject.toml`, `2.2.6`.
- Exact built source and release tag `v2.2.6`: `2a4a4e44845b663f0e9f5767cf7ec4e9d1bd02ca`.
- Later plan evidence: `ee57e6213a44a56472ff7dc539bb55f96b1a8fd1`.
- Test-only fixture repair: `5658d6588012ec7f0616af420270c5cd4dbd2555`.
  It removes four stale global recording-setting cleanup calls. Recording settings
  now belong to projects; no runtime or packaged source changed.
- Source verification reused the existing Python 3.10 environment with candidate
  source on PYTHONPATH. No runtime dependencies were installed or updated.
- [x] Commit the isolated source/version candidate.
- [x] Library, safe GUI, packaging, updates and docs focused verification pass.
- [x] Repo precommit completed; one Windows rename denial passed the isolated native recheck below.
- [x] Build the full installer and direct 2.2.5 patch in isolated versioned folders.
- [x] Verify full/patch inventories, exact reconstruction and native/source identities.
- [x] User-approved packaged smoke and 67 registered startup/Library GUI cases pass.
- [x] Publish the exact source/tag, six assets and user release note.
- [x] Verify public asset digests and actual updater patch/full-fallback selection.

## Source verification

- Library: 274 passed, 3 Windows symlink skips. The initial long temporary-path run
  had 10 publisher-fixture failures; the complete fresh short-path rerun passed
  without any source change.
- Safe GUI: 17 passed. Packaging: 181 passed. Updates: 309 passed, 4 Windows symlink skips.
- Docs: 9 passed; documentation hygiene passed.
- Every Python file changed from master passed explicit Ruff and compilation.
- Precommit mypy passed all 213 source files and repository/docs audits passed.
  The full non-Qt suite recorded 2,605 passed, 11 Windows symlink skips and one
  Windows access-denied error while renaming a staged long-path import directory in
  `test_bundle_transfer_without_windows_long_path_policy[False]`. Both transfer
  parametrizations passed in an isolated fresh-path native rerun (2 passed), with
  no source change. This is a successful isolated recheck, not an uninterrupted
  all-green harness run.

The managed source-check logs are preserved in the parent checkout's
`build/release-2.2.6/verification/source-checks/`, including
`library-short-path.log`, `precommit-short-path.log` and `long-path-native-recheck.log`.

## Artifact and visible acceptance evidence

The parent checkout retains `build/release-2.2.6/artifact-audit.json` and
`complete-source-audit.json`. Both audits passed before the test-only fixture repair:

- Full target: 7,985 files; the direct 2.2.5 patch has 13 changed/added files,
  8 removed files and 7,972 retained files. Exact patch reconstruction matches
  the complete target inventory.
- All 493 native inputs match the authenticated published 2.2.5 baseline; all
  487 native payload files are unchanged.
- All 213 embedded Studio modules match the exact built source. The comparison
  accounts explicitly for Windows CRLF checkout conversion. No result-sharing or
  data-sharing package/files are present.
- The full setup, direct patch, update JSON and their three SHA-256 sidecars are
  preserved as six audited release assets. The audit executes no installer or GUI.

The user-approved native visible packaged smoke passed (`ok: true`, version 2.2.6,
matching package metadata, runtime dependency imports and bounded layout/control
checks). Evidence: `packaged-smoke-report.json` and `packaged-smoke.log` in the
parent checkout's `build/release-2.2.6/`.

Registered startup and Library GUI coverage passed together in native Windows Qt:
67 passed, 869 deselected, 4 existing collection warnings. Startup sizes were
640x420 and 700x460; Library sizes were 900x640 and 1040x760. Coverage includes old
connected/pending credential reconnection, Continue offline, shutdown, busy/error
states, permissions, enrollment, import, cancellation and realistic long metadata.
Only these two registered modules ran through the approved full GUI tier.

The first attempt hit the obsolete fixture keys. After their test-only repair,
the long test-root prefix caused six Windows MAX_PATH fixture failures followed
by a native Qt abort. Fresh isolated startup (17) and Library (50) processes passed;
the final combined short-path run passed all 67 cases without an abort. These
attempts remain recorded rather than being presented as one uninterrupted green run.
Evidence: the parent checkout's `build/release-2.2.6/verification/`, especially
`library-startup-gui-visible-final.log`, with the earlier attempt logs retained.
Our generated short test roots were removed after verification.

## Public release verification

[FPVS Studio 2.2.6](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.6)
is the latest public stable release (GitHub release ID `404219576`), with the exact
user-requested body and six assets. The release/tag target is the exact built source
`2a4a4e44845b663f0e9f5767cf7ec4e9d1bd02ca`; later plan and test-only follow-ups do
not change the packaged application.

The independent anonymous public verification passed all six server/local asset
digests and seven real updater selection cases:

- 2.2.5 with authenticated installed inventory selects the direct patch.
- 2.2.5 without inventory and forced-full 2.2.5 select the full installer.
- 2.2.4, 2.0.0 and 1.4.0 select the full installer.
- Current 2.2.6 reports no update.

Evidence: the parent checkout's `build/release-2.2.6/published-release.json` and
`public-verification.json`. These discovery/digest checks execute no installer or GUI.

## Acceptance boundary

The visible tests use synthetic clients and temporary preferences; they do not
connect to the production Library, run experiments or execute installers. Real
lab-code enrollment, remembered access after a normal reopen, live revocation,
existing-project offline use and a second physical PC were not verified by these
checks. Installed upgrade/repair/uninstall and broader experiment acceptance remain
unrun; no prior-release waiver is carried forward.

The private service owns its dashboard, current-access filtering and global access
reset. Its deployment and revocation evidence are recorded separately by the parent
implementation task; desktop source verification does not claim those checks passed.
