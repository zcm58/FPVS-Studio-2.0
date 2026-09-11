# Multi-Session Release v1.5.3

Status: Completed

## Outcome

Published [v1.5.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.5.3)
on 2026-09-11. The annotated tag points to release source
`cdf2e526c70dd85ff46f15ea4d3dc2c8484b3540`, already pushed to `master`.
All three GitHub asset sizes and SHA-256 digests match the final local artifacts.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.5.3.exe` | 257,361,697 | `6434198f92e75374ba4943fc2e72683580e6a7d3a44e968ae9b2716327bbdf6d` |
| `FPVS-Studio-Patch-1.5.2-to-1.5.3.exe` | 27,874,869 | `b97bd5f8fc5711ce339c662f3a7e7a7667751a87bb3500185de77a37bffb08cf` |
| `FPVS-Studio-Update-1.5.3.json` | 435 | `c4efde63a03b6153552a12b786d43a72ab2e85b384939732faa08b4ee148425e` |

The public updater recognizes 1.5.3 as current and offers the update from 1.5.2.
Its actual metadata downloader verifies the published patch JSON, and its baseline
checker verifies the authenticated extracted 1.5.2 installation without running it.

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
- Build in isolated `build/release-1.5.3-verified/` and `dist/release-1.5.3-verified/` paths. Preserve
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
- Separate `.venv3.10` build environment preserves the ordinary `.venv` dependency
  set. Initial package-metadata pins passed precommit and packaged smoke, but a full
  inventory comparison exposed additional dependency drift. Baseline PYZ constants
  identify the additional exact pins for the final build. The first build is retained
  under the original `release-1.5.3` label and is not a publication candidate.
- Synthetic same-PID, same-plan acceptance passed for two visits in both full and
  compact modes. All 60 first-visit full files retain their hashes; history/task rows,
  summaries and electrode snapshots remain separate. Evidence is retained under
  `build/release-1.5.3-acceptance/`. Automatic approval review blocked cleanup of two
  failed temporary fixtures; those task-owned fixtures remain.
- `master` was fast-forwarded and pushed at release source commit
  `cdf2e526c70dd85ff46f15ea4d3dc2c8484b3540`. The source feature branch remains available.
- Release-environment precommit passed: 1,410 tests, six Windows symlink-permission
  skips, mypy on 153 files, and repository/documentation audits.
- The user explicitly approved native visible GUI checks. All 17 focused registered
  cases passed: Home/Run fresh, repeat, disabled, cancellation, worker/lifecycle
  behavior; confirmation at 600x260 with long PID/session text; setting persistence;
  all eight Setup steps at 1120x820 in both themes.
- Isolated native Inno lifecycle acceptance passed all 15 steps, including patch/fresh
  parity, corruption refusal, interrupted-patch recovery, full repair, upgrade, and
  uninstall with six user-data sentinels preserved. The production application's
  registration was unchanged; its installer/uninstaller was not executed.
- Both the initial and final published v1.5.3 bundles passed the approved visible smoke:
  metadata, themed update controls, dismissal, test-mode visibility and runtime imports.
- All 46 known package versions now match the authenticated baseline. Final-environment
  precommit and the full/compact repeat-visit demonstration passed again. The bundle
  comparison then exposed two debug DLLs collected from Meta Horizon's PATH entry.
  The publication candidate removes only that unrelated application path for the
  build process, preserving baseline-matching native dependency paths. Ordinary
  process/global settings and developer dependencies remain unchanged.
- An overly broad PATH experiment was stopped before completion and retained under
  `release-1.5.3-clean`; `release-1.5.3-final` is also retained for comparison. Only
  the `release-1.5.3-verified` artifacts were published.
- Final extracted full installer: all 7,106 owned files match the bundle. Patch:
  exactly 28 changed/added files, 26,603,540 payload bytes, 7,078 retained files, and
  937 obsolete Tcl/Tk/test-support/metadata removals. Applying the delta and removals
  reconstructs the target inventory exactly. No unchanged file is in the patch payload.
  All 50 external native runtime binaries match the published baseline; no Meta DLL
  is included. Target inventory SHA-256:
  `46ade5913516dca59016f0164a021d782d95db7746ee367f9e388f7050ae7159`.
- Final evidence is under `build/release-1.5.3-acceptance/`: `final-verification.json`,
  `gui-acceptance.json`, `verified-packaged-smoke-report.json`,
  `verified-bundle-provenance-and-delta.json`,
  `artifact-audit-4f9a6643f4/report.json`, and `github-published-verification.json`.
  Baseline provenance, exact dependency freeze and build logs remain under
  `build/release-1.5.3-baseline/`.

## Remaining Platform Acceptance

The release was not installed into the user's production application or a clean
Windows VM. Clean-PC installation and actual EEG/display/trigger playback remain
manual checks. Native lifecycle evidence uses isolated inert fixtures; it does not
claim production install or hardware acceptance. Six source tests were skipped
because this account lacks Windows symlink-creation privileges. Existing raw Cognitive
Decline data and the user's unrelated updater-plan edit/output remain preserved.
