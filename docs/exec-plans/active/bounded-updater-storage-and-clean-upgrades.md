# Bounded Updater Storage And Clean Upgrades

Status: Active

## Merge Decision (2026-09-05)

- The user authorized merging the updater branch into `master`, superseding the
  earlier feature-branch hold below. The local merge is complete; pushing is deferred.
- Fresh updater focused verification passed (166 tests, four Windows symlink skips),
  and repo precommit passed (923 tests, five Windows symlink skips), including mypy
  and repository/documentation audits.
- Keep this plan active for the unperformed installer lifecycle acceptance checks.
  Merge authorization does not mark those checks as passed.

## Approved Decisions (2026-08-30)

- Work on `codex/bounded-updater-storage-clean-upgrades`.
- Canceled and interrupted downloads are discarded; retries start from zero. Under
  the exclusive cache lock, remove recognized abandoned partials regardless of age.
  This replaces the original 24-hour grace period, which conflicted with the strict
  payload-count bound and provided no benefit without download resumption.
- Verify installers using the selected GitHub release asset's SHA-256 metadata;
  missing or invalid digests disable in-app download/launch without a size-only fallback.
- Support published GitHub releases, including accumulated upgrade histories. There
  are no private or custom builds to support. Establish legacy ownership from exact
  authenticated published artifacts, never from arbitrary files in an existing install.
- Preserve projects, settings, templates, runs, logs, and unrecognized files. Update
  cache maintenance is independent of the user's configured FPVS Studio Root Folder.
- No disposable Windows VM or separate test account is available. The initial scope
  allowed safe local verification only, with no agent-run installation or Qt execution.
  The 2026-08-31 user acceptance and manual beta test below supplement this decision;
  unperformed lifecycle checks must not be reported as passed.

## User Acceptance And Beta Test (2026-08-31)

- The user reports that the GUI looks fine and accepts the expected updater layout
  changes. Record this as manual GUI acceptance, not as an executed automated Qt suite.
- Build a local `1.3.1b1` candidate (v1.3.1 beta 1) on the current feature branch. Keep
  the package version, bundled metadata, and setup filename aligned. Use isolated
  `build/beta-1.3.1b1/` and `dist/beta-1.3.1b1/` paths to preserve existing artifacts.
- The user will manually run the installer on this machine. The agent may build and
  inspect the artifact, but must not launch the app, installer, or uninstaller, run
  destructive failure/recovery tests, create a VM/account, or publish a GitHub release.
- Installer/upgrade/uninstall outcomes remain pending until actually reported or
  verified. The packaged-app launch check is deferred to the user's manual test; safe
  source checks, static bundle checks, and native installer compilation do not replace it.

## Summary

Harden the end-user updater so repeated downloads and in-place upgrades cannot grow
disk usage without a bound. Cache retention is the mandatory first milestone; later
milestones cover interrupted/concurrent downloads, obsolete installed files, installer
integrity, and regression coverage.

## Start Here

Read `src/fpvs_studio/updates/AGENTS.md`, `packaging/AGENTS.md`, and
`docs/PACKAGING.md`. The main owners are:

- cache/download: `src/fpvs_studio/updates/cache.py`, `cache_io.py`, and `downloader.py`
- shutdown/UI coordination: `src/fpvs_studio/gui/update_lifecycle.py`,
  `update_dialog.py`, and `controller.py`
- installed-file replacement: `packaging/inno/fpvs_studio.iss`, `owned_files.iss`, and
  `updater_cache.iss`; build inventories belong to `scripts/build_installer_inventory.py`
- focused coverage: `tests/unit/test_update_cache.py`, `test_update_download.py`,
  `test_installer_inventory.py`, and `tests/gui/test_update_dialog.py`

## Required Outcomes

1. **Bound the update cache.** On normal startup, inspect only the app-owned update
   cache. Delete completed installers at or below the running version, retain at most
   the highest valid newer installer, and delete recognized abandoned `.part` files
   under the exclusive lock. After successful housekeeping, the cache may contain at
   most one completed installer and one actively locked partial download. Delete only
   updater-recognized filenames,
   and make uninstall remove the app-owned update cache. Never clean projects,
   settings, templates, `runs/`, `logs/`, or files outside this exact cache.
   The payload bound excludes small lock/verification metadata. Cleanup failure is
   nonfatal at startup, but explicit downloads must not add payloads if required pruning
   cannot complete. Never delete an active writer's staging file.
2. **Make downloads interruption-safe.** Use one inter-process cache lock and a unique
   staging file per attempt. Cover open/read/stat/validation/replace in one cleanup
   lifecycle, and make application shutdown wait for or safely cancel updater work.
3. **Make upgraded app files match a fresh install.** An `N-1 -> N` upgrade must leave
   the same packaged application files as a fresh `N` install, excluding Inno
   uninstaller bookkeeping. Use an owned-file manifest or a staged replacement with
   rollback; do not blindly delete the whole install directory.
4. **Verify installers before reuse or launch.** Require a trusted SHA-256 digest for
   the selected release asset. A same-size file with different content must be rejected.
   Validate Authenticode too when release signing infrastructure exists, but creating
   that infrastructure is outside this plan.
5. **Lock the lifecycle down with tests.** Cover multiple cached versions, stale and
   active partials, every failure/finalization path, simultaneous attempts, shutdown,
   same-size corruption, post-update cleanup, and an obsolete installed-file sentinel.

## Sequence And Acceptance

1. Implement cache policy plus `tmp_path` unit tests before changing GUI or packaging.
2. Add download locking/final cleanup, then GUI shutdown coordination and registered
   Qt coverage.
3. Add digest verification and update the documented GitHub Release contract.
4. Add safe installed-file reconciliation and a Windows two-version packaging check.

Implementation acceptance means safe local checks pass and the startup release check
remains metadata-only, with download/install still explicit. Final release acceptance
additionally requires a disposable Windows update-over-old plus final uninstall that
leaves no obsolete app files or update installers. That lifecycle acceptance remains
pending until a suitable environment is available.

## Progress

- [x] Review implementation and approve policy defaults.
- [x] Establish clean feature branch and updater/packaging baseline (25 tests).
- [x] Bounded cache, cancellation, cross-process locking, and digest verification.
- [x] Non-blocking GUI lifecycle and registered regression coverage (not executed).
- [x] Owned-file reconciliation for published legacy and future installations.
- [x] Safe local focused/precommit checks and documentation.
- [ ] Disposable Windows fresh-install, chained-upgrade, failure, and uninstall checks.
- [x] User-reported visible GUI acceptance (2026-08-31); automated Qt suite not run.
- [x] Build and hand off the local `1.3.1b1` manual-test installer.
- [x] Fix the beta 1 profile lookup failure and hand off `1.3.1b2` for a manual retry.
- [x] Final implementation review and safe verification for feature-branch handoff
  (2026-09-02); native lifecycle acceptance remains pending.

## Repository Wrap-Up (2026-09-02)

- Independent read-only reviews of the updater backend and native installer found no
  blocking correctness or data-safety issues. No implementation change or new beta
  build was needed for this wrap-up.
- Fresh focused verification passed: updater 166 tests with four symlink-privilege
  skips, packaging 148 tests, and GUI source Ruff/compilation without Qt execution.
  Repo precommit passed with 923 tests and five symlink-privilege skips, plus mypy
  (136 source files), Ruff, compilation, and repo/doc audits. All 12 verification
  scopes validate. The actual Inno script compiled against the tiny synthetic fixture;
  the generated fixture was removed automatically without executing setup.
- Rechecked the retained beta 2 installer against its checksum; it still matches the
  SHA-256 recorded below. Windows' per-user uninstall registration still reports
  `1.3.0`. No successful beta 2 upgrade or packaged-app launch has been verified.
- Keep the plan active and the feature separate from `master` until installer
  acceptance is resolved. The next manual step is the normal beta 2 upgrade and app
  launch, followed by the read-only installed-tree comparison in the lifecycle
  checklist. That result alone must not be presented as completion of the separate
  fresh/chained upgrade, failure/recovery, and uninstall scenarios.
- No installer, uninstaller, Qt application, production cache cleanup, or GitHub
  release was run. User-owned `output/`, projects, and the existing installation
  remain untouched. Retain the beta artifacts/manifests for acceptance; the historical
  installer copies noted below remain outside Git and were not retried for cleanup.

## Beta 1 Failure And Beta 2 Correction (2026-08-31)

- The user's beta 1 install stopped on Preparing to Install with `Unknown constant
  "userprofile"`. `OwnedSafeInstallRoot` used `ExpandConstant('{userprofile}')`, which
  is not an Inno constant. This guard runs before manifest extraction, ownership-journal
  writes, and application-file replacement, so this failure did not replace app files.
- The checkout changed to `master` during diagnosis. After explicit user approval,
  returned to `codex/bounded-updater-storage-clean-upgrades`, retaining all existing
  uncommitted work, to correct the installer and rebuild for a manual retry.
- Resolved `CSIDL_PROFILE` with the supported `GetShellFolderByCSIDL(..., False)`;
  do not create directories or depend on inherited profile environment variables.
  Validate the result and fail closed for empty or noncanonical local paths. Existing
  profile/system/project-root exclusions and ownership/deletion rules remain intact.
- Added a reviewed literal runtime-constant allowlist and profile-guard ordering coverage.
  The allowlist reproduces the original failure without executing setup; compilation
  alone does not validate runtime constant strings. These are source regression checks,
  not proof of a successful native install.
- Built `1.3.1b2` in fresh `build/beta-1.3.1b2/` / `dist/beta-1.3.1b2/` outputs.
  The beta 1 artifact's original checksum is unchanged, and its manifests remain intact.
  No agent-run app/setup/uninstaller, installed-app mutation, publication, commit, or push
  was performed for this retry.
- Both new source regressions failed before the fix and passed afterward. Packaging
  focused verification passed with 148 tests. Repo precommit passed with 923 non-Qt
  tests and five symlink-privilege skips, plus mypy, Ruff, compilation, and repo/doc
  audits. An independent review found no blocking issue in the scoped fix or coverage.
- Inno Setup 6.7.3 compiled both the tiny synthetic fixture and the real beta installer.
  A read-only Windows `CSIDL_PROFILE` lookup returned a valid local profile without
  creating a directory. Neither compile output was executed by the agent.
- Replacement installer: `dist/beta-1.3.1b2/installer/FPVS-Studio-Setup-1.3.1b2.exe`,
  260,763,149 bytes (248.7 MiB), unsigned. Its sibling `.exe.sha256` records:
  `4a0630f6964ee0f5ddfa2c0e0f360af3b0e1cc9fbb1b343e22cdd2970dcd2d7b`.
- Source, editable-package metadata, bundled metadata, and setup product version all
  match `1.3.1b2`. Static runtime asset/module checks passed. All 10,858 current file
  hashes match `build/beta-1.3.1b2/installer-inventory/current-owned-files.txt`; the
  legacy manifest matches the 17 published releases. The user's manual beta 2 install
  and packaged-app launch are still pending; this does not complete lifecycle acceptance.

## Beta Build Record (2026-08-31)

- Built the current feature worktree as `1.3.1b1`, using Python 3.10.11,
  PyInstaller 6.20.0, and Inno Setup 6.7.3. Source, editable-package metadata,
  bundled metadata, and setup product version agree. No dependencies were upgraded;
  only the editable FPVS Studio package metadata was refreshed.
- The executable and installer stages support an optional guarded `BuildLabel`.
  `beta-1.3.1b1` isolates their output from existing artifacts; default build paths
  are unchanged. Native path/junction/cleanup regression fixtures passed.
- Installer: `dist/beta-1.3.1b1/installer/FPVS-Studio-Setup-1.3.1b1.exe`,
  260,745,426 bytes (248.7 MiB). A sibling `.exe.sha256` file records its checksum:
  `22bc6e89b6f29fc1186de9c497db2e86a76623760d985d755a88d196ecc6a089`.
  This is an unsigned local candidate, not a published or authenticated release asset.
- Static checks confirmed the new updater modules, PsychoPy presentation modules,
  Python/Qt Windows binaries, fonts/licenses, and PortAudio libraries in the bundle.
  The generated current ownership inventory matches all 10,858 bundled paths and
  SHA-256 hashes; the legacy manifest matches all 17 authenticated published releases.
  Keep `build/beta-1.3.1b1/installer-inventory/current-owned-files.txt` for the later
  read-only installed-tree comparison.
- Dependency-analysis warnings were reviewed without launching the app: Tables has
  its patched dependency set in `tables.libs`, and the missing SciPy `_cdflib` and
  pycparser lexer/parser table names are stale hook references for the installed
  versions. No concrete FPVS blocker was identified; native launch is still untested.
- Packaging focused verification passed with 146 tests. Repo precommit passed with
  921 non-Qt tests and five symlink-privilege skips, plus mypy, Ruff, compilation,
  and repository/doc audits. Verification configuration validates all 12 scopes.
- Both real build stages completed; the installer and packaged app were not run.
  No GitHub release, tag, commit, push, or installed-app mutation was performed.
  The user will test the normal in-place upgrade manually. This does not complete
  the unperformed fresh-install, chained-upgrade, failure/recovery, or uninstall checks.

## Implementation Record (2026-08-30)

- Downloads are bounded to the selected asset size (maximum 4 GiB), use unique staging
  files, and share an OS lock with startup and uninstall cleanup. Guarded Windows
  handles reject hardlinks/reparse points and keep the installer unchanged between
  final SHA-256 verification and process creation.
- Startup independently schedules offline cache housekeeping before root-folder
  onboarding. The application owns updater workers, defers shutdown while cancellation
  finishes, and never hashes or waits synchronously on the GUI thread. Close, Escape,
  window close, parent destruction, and application quit have registered Qt coverage.
- The installer has native Inno reconciliation, durable pending-deletion history, and
  exact known-hash ownership. The legacy inventory was generated from all 17 public
  installers through 1.3.0: 13,286 paths and 13,658 distinct path/hash records. No old
  installer was executed. Future builds generate their own final-bundle inventory.
- Inno Setup 6.5+ is required; the actual installer script compiled with 6.7.3 using
  a tiny non-executable fixture. The fixture setup was never run and was auto-removed.
- Focused `updates`, `gui`, `packaging`, and `docs` checks passed. Repo precommit passed
  with 914 non-Qt tests, five symlink-privilege skips, source mypy, Ruff, compilation,
  and repository/doc audits. Actual Windows junction, process-lock, and pinned-file
  updater tests passed. Verification configuration validates all 12 scopes.
- Runtime lifecycle acceptance remains pending; use
  [the explicit Windows checklist](../../../packaging/inno/LIFECYCLE_TESTS.md).
  No real installer/uninstaller, Qt app, production cache cleanup, release, or remote
  branch mutation was performed. Operating-system DNS resolution cannot be interrupted
  by the cancellation event; socket reads have five-second timeouts and cancellation
  checkpoints, so a stalled resolver can delay final shutdown.
- Temporary extracted payloads and compile fixtures were removed automatically.
  Removal of the separately downloaded historical installers/extractor was denied by
  tool safety policy. These task-owned copies remain under
  `build/updater-inventory-8c2587e2fe894775be4c8caf8643c6df/`; the authenticated inventory
  and provenance are retained in `packaging/inventory/`. No user-owned `output/`, build,
  installed-app, or project data was removed.

## Non-Goals And Safety Bounds

- Do not introduce automatic download or unattended installation.
- Do not change release-channel or prerelease-selection behavior except as needed to
  obtain trusted digest metadata.
- Do not set Inno `UninstallLogMode=overwrite`.
- Do not delete the currently running installer; prune it on the next successful app
  startup after the installed version has advanced.
- Keep all cleanup best-effort and logged; cleanup failure must not damage user data or
  prevent FPVS Studio from starting.

## Verification

Run the `updates`, `gui`, and `packaging` focused scopes, followed by repo precommit.
Run registered Qt coverage only when the user approves a safe visible environment.
Complete the documented Windows fresh-install, update-over-old, and uninstall smoke
path before release.
