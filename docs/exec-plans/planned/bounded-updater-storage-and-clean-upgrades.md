# Bounded Updater Storage And Clean Upgrades

Status: Planned

## Summary

Harden the end-user updater so repeated downloads and in-place upgrades cannot grow
disk usage without a bound. Cache retention is the mandatory first milestone; later
milestones cover interrupted/concurrent downloads, obsolete installed files, installer
integrity, and regression coverage.

## Start Here

Read `src/fpvs_studio/updates/AGENTS.md`, `packaging/AGENTS.md`, and
`docs/PACKAGING.md`. The main owners are:

- cache/download: `src/fpvs_studio/updates/downloader.py`
- shutdown/UI coordination: `src/fpvs_studio/gui/update_dialog.py` and `controller.py`
- installed-file replacement: `packaging/inno/fpvs_studio.iss`
- focused coverage: `tests/unit/test_update_download.py`,
  `tests/gui/test_update_dialog.py`, and `tests/unit/test_package_metadata.py`

## Required Outcomes

1. **Bound the update cache.** On normal startup, inspect only the app-owned update
   cache. Delete completed installers at or below the running version, retain at most
   the highest valid newer installer, and delete inactive `.part` files older than 24
   hours. After housekeeping, the cache may contain at most one completed installer
   and one actively locked partial download. Delete only updater-recognized filenames,
   and make uninstall remove the app-owned update cache. Never clean projects,
   settings, templates, `runs/`, `logs/`, or files outside this exact cache.
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

Done means all required outcomes pass, the startup check remains metadata-only, users
still explicitly choose download and install, and a clean-VM update-over-old plus final
uninstall leaves no obsolete app files or update installers.

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
Run registered Qt coverage only when the user approves a safe visible `full` run.
Complete the documented Windows fresh-install, update-over-old, and uninstall smoke
path before release.
