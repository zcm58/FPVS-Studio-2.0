# FPVS Studio 2.2.6 Library Reconnection Release

Status: Active

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

## Candidate and verification

- Stable base: `0deed9f` (published Studio 2.2.5).
- Isolated branch: `codex/library-reconnect-2.2.6`.
- Integrated startup feature: parent commit `47a5bbd`; results-sharing conflict context removed.
- Integrated native v2 behavior: parent commit `cf70ae0`.
- Canonical version: `pyproject.toml`, `2.2.6`.
- Reuse the existing Python 3.10 environment with this worktree's source on PYTHONPATH.
  Do not install or update runtime dependencies for source verification.
- [x] Library focused, safe GUI focused, packaging, updates and docs focused pass.
- [ ] Repo precommit (non-Qt suite, mypy and audits) passes.
- [ ] Commit and publish the exact source from stable master.
- [ ] Build the full installer and direct 2.2.5 patch in isolated versioned folders.
- [ ] Verify full/patch inventories, exact reconstruction, local/server digests and updater selection.
- [ ] Publish the exact user release note and verify source/tag/asset identities.

Focused source verification on the candidate:

- Library: 274 passed, 3 Windows symlink skips. The initial long temporary-path run
  had 10 publisher-fixture failures; the complete fresh short-path rerun passed
  without any source change. Evidence: `build/release-2.2.6/verification/library-short-path.log`.
- Safe GUI: 17 passed; registered Qt coverage remains excluded.
- Packaging: 181 passed. Updates: 309 passed, 4 Windows symlink skips.
- Docs: 9 passed; documentation hygiene passed.
- Every Python file changed from master passed explicit Ruff and compilation.
- Precommit mypy passed all 213 source files and repository/docs audits passed;
  the full non-Qt unit suite is still running. Do not claim the complete gate passed yet.

## Acceptance boundary

Source-only preparation runs no Qt, installer, uninstaller, runtime or experiment.
Registered startup GUI coverage checks old connected/pending access returns to lab
setup with Continue offline. Manual visible checks remain pending: connect with a
lab code, inspect minimum/default dialog sizes, reopen to confirm remembered v2
access, exercise revocation and open existing projects offline. Packaged startup,
installed upgrade and a second physical PC remain pending until explicitly verified
or the user records a waiver. Prior release waivers do not apply to this release.

The private service owns its dashboard, current-access filtering and global access
reset. Its deployment and revocation evidence are recorded separately by the parent
implementation task; desktop source verification does not claim those checks passed.
