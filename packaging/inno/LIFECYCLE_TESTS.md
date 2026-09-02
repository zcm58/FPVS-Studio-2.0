# Native Windows lifecycle acceptance (explicit opt-in only)

Status: **Pending installer lifecycle.** The user accepted the visible updater GUI on
2026-08-31. No agent-run installer, uninstaller, or Qt application has been executed.
Python fixture tests and Inno compilation do not validate native Windows file-handle,
rollback, or uninstall behavior.

The user requested a local `1.3.1b1` beta to install manually on their own machine.
That is an ordinary upgrade test, not authorization for agent-run installation or the
destructive failure scenarios below. The beta uses the normal app identity and install
location, so it replaces the existing installation rather than installing side-by-side.
Record the manual result separately; do not infer that all lifecycle scenarios passed.

The first local candidate was built on 2026-08-31 and remains at
`dist/beta-1.3.1b1/installer/FPVS-Studio-Setup-1.3.1b1.exe` (248.7 MiB), with a
sibling SHA-256 file. Source and bundled versions, setup product version, and all
10,858 current bundle file hashes were checked without execution. The retained
expected manifest for this candidate is
`build/beta-1.3.1b1/installer-inventory/current-owned-files.txt`. The user reported
that beta 1 stopped on Preparing to Install with `Unknown constant "userprofile"`.
The failing guard runs before application-file replacement or ownership-journal writes.

The user approved fixing this profile lookup and rebuilding as `1.3.1b2` for another
manual test. The fix uses Windows' shell-folder API without creating directories and
retains the fail-closed profile-root protection. The new candidate uses separate
`build/beta-1.3.1b2/` and `dist/beta-1.3.1b2/` output. Close the failed beta 1 setup
and FPVS Studio before manually running beta 2, then confirm `1.3.1b2` and that
existing projects still open. Successful installation and packaged-app launch results
have not yet been reported.

Beta 2 is ready at `dist/beta-1.3.1b2/installer/FPVS-Studio-Setup-1.3.1b2.exe`
(248.7 MiB), with a sibling checksum file. The corrected Inno script compiled, the
source regression reproduced the original error before the fix, and packaging checks
passed with 148 tests (repo precommit: 923 passed, five symlink-privilege skips).
Use `build/beta-1.3.1b2/installer-inventory/current-owned-files.txt` for the eventual
read-only comparison after the user reports installation complete; its 10,858 file
hashes match the final bundle. These checks do not assert that setup or the app launched.

On 2026-09-02, the safe wrap-up checks again passed (923 non-Qt tests, five
symlink-privilege skips; updater/packaging focused checks and native fixture compilation).
Independent updater and installer reviews found no blocking code issues. The retained
beta 2 installer checksum is unchanged, but the per-user Windows uninstall registration
still reports `1.3.0`. Beta 2 installation/launch and this lifecycle checklist therefore
remain pending; no agent-run setup, uninstaller, or application was used for wrap-up.

Run this checklist only after explicitly approving a disposable Windows VM or separate
test account with no working FPVS Studio installation. A custom `/DIR` on the working
account is **not isolation**: Inno uses the same application ID and uninstall registry
entry. Snapshot the disposable environment before each failure scenario. Do not point
these checks at a lab project or a real user's installation/cache.

## Safe developer checks (no install or application launch)

```powershell
./scripts/verify.ps1 -Scope packaging -Tier focused
python scripts/check_installer_compile.py --inno-compiler "C:\Path\To\ISCC.exe"
```

The compile helper creates a tiny non-executable synthetic bundle in a fresh directory
under `build/installer-compile-checks/`, compiles the actual Inno script, never runs its
output, and removes only that generated fixture. Inno Setup 6.5+ is required for
handle-bound SHA-256 hashing; no extra interpreter is required on end-user machines.

## Fixtures and ownership

- Use exact published installers authenticated against their GitHub asset SHA-256.
  The committed legacy inventory includes every published release and accumulated
  ancestry. Do not rebuild an old tag to reconstruct its shipped files.
- Build the new setup from one fixed final bundle. Keep its generated
  `build/installer-inventory/current-owned-files.txt` as the expected file inventory.
- Prepare distinct disposable snapshots for fresh new installation, fresh `1.3.0`
  upgraded to new, and oldest-published → `1.3.0` → new. Also test skipped-version
  upgrade directly from the oldest published version.
- Select an obsolete sentinel path actually present in a historical inventory and
  absent from the new inventory. Restore its **exact historical bytes** when needed.
  An arbitrary invented filename does not prove installer ownership.
- Add an unrelated `lab-notes.txt` sentinel and an unrelated subdirectory within the
  install folder. Add project/settings/template/run/log sentinels outside the install
  folder. Snapshot hashes; all must survive upgrade and uninstall unchanged.

## Fresh and chained upgrade

1. Install the old release(s) in the disposable account, adding sentinels before the
   final upgrade. Record the original uninstall registry entry and shortcuts.
2. Run the new installer with Inno logging enabled, both directly and from the app's
   explicit **Install and Restart** action. Verify ordinary installation/launch UX.
3. Confirm obsolete **known-hash** files disappear, current packaged files match the
   fresh new installation, unknown/modified files survive, and old package metadata
   no longer shadows the current app version.
4. Read-only file parity check (use the source environment for this diagnostic, not
   as an end-user runtime dependency):

   ```powershell
   python scripts/check_installer_tree.py `
     --install-root "C:\DisposableTest\FPVS Studio" `
     --expected-manifest "build\installer-inventory\current-owned-files.txt" `
     --legacy-inventory "packaging\inventory\published-legacy-inventory.json"
   ```

   It reports missing/modified current files, remaining obsolete known content,
   deliberately preserved modified files, and unsafe/unreadable paths. It never
   deletes files. Current inventory and pending-history manifests are installer
   bookkeeping; unknown user files and empty directories are intentionally preserved.
5. Perform the existing packaged/manual launch smoke on a machine without system
   Python. Verify projects, templates, settings, test launch, and normal relaunch.

## Failure, interruption, and retry

- **Locked/read-only obsolete file:** hold a known obsolete sentinel open without
  delete sharing (and separately mark it read-only), then install new. Current files
  should install successfully, the sentinel should remain, and its path plus original
  hash must remain in `fpvs-pending-owned-files-v1.txt`. Release the lock/attribute and
  run the new installer again; removal should succeed and the journal should shrink.
- **Modified same-size file:** replace an obsolete file's bytes with different content
  of identical length. It must survive, with original hashes retained for safe retry;
  size alone must never authorize deletion.
- **Cancel/fail before file replacement:** cancel after ownership preparation. Confirm
  no obsolete file was removed and the original application is usable.
- **Failure during replacement:** use a disposable snapshot to induce an Inno copy
  failure/cancellation. Reconciliation must not run before `ssPostInstall`. Inspect
  Inno rollback and ensure the captured previous ownership remains available to retry.
- **Journal write/commit failures:** deny writes to pending bookkeeping during prepare
  (installation must stop before replacing files), and during final commit (already
  captured history must remain, permitting retry). A process kill during the atomic
  write must not truncate the prior journal. Inspect and account for any interrupted
  installer-owned temporary bookkeeping; never remove unrelated files to hide it.
- **Unsafe destinations:** exercise a drive/profile root, a project root, `..`, a
  junction/reparse ancestor, and a file/hardlink at an expected directory/file path.
  Setup must refuse unsafe replacement or retain unsafe cleanup candidates without
  touching the target outside the installation folder.
- **Malformed manifest:** inject a bad header, duplicate record, absolute path,
  alternate data stream, or traversal. Setup must stop safely, not delete or overwrite
  arbitrary files. Restore the valid fixture before continuing.

## Uninstall and updater cache

1. Populate only the disposable account's canonical
   `%LOCALAPPDATA%\FPVS Studio\updates` cache with recognized completed installers,
   legacy/UUID partials, verification receipts, and unrelated sentinels. Include fake
   names such as `FPVS-Studio-Setup-1banana.exe`, its `.part`/`.verified.json` forms,
   malformed UUID suffixes, links, and a subdirectory. These are not owned payloads.
2. With the updater idle, uninstall. Known payloads/receipts should be removed;
   unrelated files/subdirectories must survive. If nothing else remains, the exact
   idle lock and empty cache directory may be removed; neither is removed recursively.
3. Repeat with a live updater holding byte `[0,1)` of `.fpvs-update.lock`. Cleanup
   must skip nonfatally. Repeat with a peer that has opened the lock but not acquired
   it: final exclusive lock deletion must fail, preventing split lock identities.
4. Race a new writer after the first cleanup releases its lock. No active staging file
   may be deleted. A pinned root or remaining payload must prevent empty-root removal.
5. Verify the normal uninstaller log still handles accumulated app files and shortcuts;
   `UninstallLogMode` remains `append`. Project/settings/template/run/log sentinels and
   unrelated files remain intact. Record any busy/permission residuals honestly.

Do not mark release lifecycle acceptance complete until these checks have actually
run in an approved disposable environment; compilation and synthetic tests alone are
not evidence of a successful real upgrade/uninstall.
