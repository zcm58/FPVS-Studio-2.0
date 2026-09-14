# AGENTS.md

## Scope of this directory

`src/fpvs_studio/updates/` contains backend-only update checking, download, private
helper protocol, staging, and installation coordination for the independent updater.

`cache.py` owns bounded retention and verification receipts; `cache_io.py` owns
no-follow file operations and the shared OS cache lock. `downloader.py` coordinates
explicit transfers, and `installer.py` owns the final guarded launch. Release
identity rules are shared through `validation.py`. The cache/installer protocol and
remaining Windows acceptance checks are documented in `docs/PACKAGING.md`.
`patches.py` owns authenticated release JSON, fast candidate selection, and the retained
read-only full baseline verifier. `helper_client.py` is Studio's subprocess interface;
`helper_protocol.py` bounds messages, `helper_service.py` handles operations and explicit
handoff acceptance, and `helper_runtime.py` owns registered installation identity, staged
helper execution, process waits, installation locking, and restart. The independent entry
is `src/fpvs_studio/updater_main.py`; its windows remain under `gui/`.
`process_launch.py` gives child processes independent frozen-runtime lifetimes and
restores Windows DLL search state after process creation.
Keep patch application, complete baseline/target verification, and recovery in Inno.

## Requirements

- Do not import PySide6 in this package; GUI presentation belongs in
  `src/fpvs_studio/gui/`.
- Do not import PsychoPy or runtime engine modules.
- Treat GitHub Releases as release metadata, not as arbitrary executable input.
- The independent helper may offer a smaller candidate patch after authenticated release
  metadata and registered version/inventory identity checks. Full installed baseline
  and target bytes are verified by Inno before/after mutation, as approved in
  `docs/exec-plans/completed/independent-updater.md`. Never label a candidate fully verified.
  Preserve full installers and an explicit selection reason when
  no compatible patch exists. Never treat invalid metadata as valid fallback input.
- Registered target version/root are independent of the helper's own version. Require
  exact per-user registration and guarded paths; do not accept arbitrary target paths
  or downgrade requests. Full repair may explicitly reinstall the current version.
- Bound and validate private pipe messages. Before accepting installation, reacquire
  official GitHub asset identity, verify cached bytes, and pin the identified Studio
  process handle. A ready message is not consent: require the matching nonce acceptance
  before waiting for Studio's exit and launching setup. Never force-close Studio.
- Run packaged helpers from bounded, guarded user-local staging and recheck their
  content hash through process creation. Keep at most two recognized helper payloads;
  refuse new staging when abandoned partial cleanup fails. Never use recursive cleanup
  or project folders for updater staging.
- Hold the independent install lock through process wait, final registration check,
  installer completion, and restart. Managed setup uses `/NOLAUNCH=1`; only the helper
  restarts Studio after exit success and expected registration. A failed patch target
  check (exit 12) requires repair even if registration already shows the target version.
- Keep update downloads in user-writable cache or temp folders, never in the install
  directory or project folders.
- Use HTTPS release and asset URLs only.
- Keep installer launch explicit; callers must get final user confirmation before
  executing a downloaded installer.
- Startup cache maintenance is best-effort and logged. Only recognized direct
  regular-file children in the exact absolute updater cache may be removed. Refuse
  linked/reparse roots, ancestors, files, and multiply-linked files; never sweep
  projects or remove arbitrary directories.
- Hold one exclusive inter-process cache lock through cleanup, reuse, transfer,
  verification, promotion, and launch. Backend code never truncates or unlinks the
  lock identity. Once locked, all recognized leftover partials are abandoned and
  removed; cancellation discards staging, and retries start from zero.
- Download attempts must fail before adding payload if required pruning fails.
  Enforce trusted asset-size and stream limits, bounded network reads/timeouts, and
  cancellation checkpoints; cleanup errors must not mask the original failure.
- Require a valid selected GitHub SHA-256 for reuse and launch. A cache receipt is
  only offline bookkeeping, not an execution trust anchor. Verify file bytes under
  a no-write/delete guard through process creation on Windows.
- Return newer releases with missing/invalid digest as available but not downloadable,
  never as up-to-date. Match exact release/asset versions, with only the documented
  published legacy filename exception.
- Installer verification/launch is one worker stage after confirmation/save, never
  a GUI-thread hash. Honor cancellation before Popen; after successful process
  creation setup owns mutations. Report installation commitment explicitly so a late
  cancellation cannot hide a failed install as cancellation before installation.
  Studio may exit only after the helper accepts the handoff and its local worker ends.
- Keep same-executable children independent with PyInstaller's public environment-reset
  flag. Sanitize only child runtime paths and temporarily restore native Windows DLL
  search for helper/setup/Studio launch. Never abandon a successfully spawned installer
  because restoring the parent's search path failed.
- Unaccepted pipe workers may exit after an eight-second cancellation grace to release
  stalled DNS and file handles. Atomically disarm that watchdog at handoff acceptance;
  it must never terminate accepted installation. Close input and await worker/bootloader
  cleanup before using forced process termination as a last resort.

## Verification

- Run `./scripts/verify.ps1 -Scope updates -Tier focused`. The configured
  route owns update behavior and import-boundary checks.
