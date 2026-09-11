# Multi-Session Release v1.5.3

Status: Active

## Authorization And Scope

The user requested v1.5.3 full and patch installers, confirmation that the same PID's
visits stay distinguishable, updating the main branch, and uploading the release to
GitHub. Publication and the main-branch update are explicitly authorized. Preserve the
unrelated local updater-plan edit and user-owned output.

## Release Workflow

- Keep the existing numeric participant visit labels: `P1_session01`, `P1_session02`,
  with separate PID and Session Number fields in CSV/XLSX and runtime exports.
- Verify repeat visits using synthetic data, including full/compact mode, preservation
  of the first session, aborted visits, legacy history and current GUI coverage.
- Set the central package version to 1.5.3 and update user-facing session guidance.
- Build in isolated `build/release-1.5.3/` and `dist/release-1.5.3/` paths. Preserve
  dependency versions, refreshing only editable application metadata as necessary.
- Authenticate the exact published v1.5.2 setup and extract its owned-file inventory
  for the direct `1.5.2-to-1.5.3` patch. A rebuilt source tag is not a baseline.
- Merge tested source into `master`, the repository's main branch. Build the complete
  target bundle, full installer, direct patch and update JSON from matching source.
- Upload all artifacts to a draft release, compare GitHub byte sizes and SHA-256
  digests to local files, then publish after required acceptance is established.

## Acceptance Boundaries

- Runtime/packaging/updater and repo precommit checks run without Qt or real hardware.
- Registered Qt and packaged GUI checks require the safe visible environment approval
  specified in AGENTS.md and the smoke script; offscreen execution is prohibited.
- Do not run production installer/uninstaller or destructive lifecycle tests against
  the user's working installation. Existing unperformed lifecycle checks remain
  explicit limitations; do not claim they passed.
- Staging with `-SkipSmoke` can prepare concrete artifacts while visible verification
  is pending; it is not evidence of a successful packaged launch.

## Progress

- Source feature commit: `1b32c7f` on `codex/multi-session-projects`.
- Packaging baseline checks passed: 168 tests. Updater checks passed: 226 tests,
  four Windows symlink-permission skips. Repeat-visit runtime checks passed: 269 tests,
  one Windows symlink-permission skip.
- Cognitive Decline is already configured for repeat sessions with preserved backups
  and verified unchanged raw data from the implementation task.
- Authenticated published v1.5.2 setup: 259,071,415 bytes, SHA-256
  `795ca89b6a73dc21b2bb0b96a6b100727f903ce2d371045792579c680854b10a`.
  All 8,030 owned files verify. Baseline inventory SHA-256 is
  `88f79f2293e073bb8f7f6ec4e7f0ecffa550b9be7cc591c9716b715ed6f796a5`.
- Separate `.venv3.10` build environment is being pinned to the baseline's shipped
  dependency versions. The ordinary `.venv` dependency set is preserved.
- Synthetic same-PID, same-plan acceptance passed for two visits in both full and
  compact modes. All 60 first-visit full files retain their hashes; history/task rows,
  summaries and electrode snapshots remain separate. Evidence is retained under
  `build/release-1.5.3-acceptance/`. Automatic approval review blocked cleanup of two
  failed temporary fixtures; those task-owned fixtures remain.
