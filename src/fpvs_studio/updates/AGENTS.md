# AGENTS.md

## Scope of this directory

`src/fpvs_studio/updates/` contains backend-only update-checking, installer download,
and installer-launch helpers for the end-user application update flow.

`cache.py` owns bounded retention and verification receipts; `cache_io.py` owns
no-follow file operations and the shared OS cache lock. `downloader.py` coordinates
explicit transfers, and `installer.py` owns the final guarded launch. Release
identity rules are shared through `validation.py`. The cache/installer protocol and
remaining Windows acceptance checks are documented in `docs/PACKAGING.md`.

## Requirements

- Do not import PySide6 in this package; GUI presentation belongs in
  `src/fpvs_studio/gui/`.
- Do not import PsychoPy or runtime engine modules.
- Treat GitHub Releases as release metadata, not as arbitrary executable input.
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
  creation report success and let the GUI await actual worker completion.

## Verification

- Run `./scripts/verify.ps1 -Scope updates -Tier focused`. The configured
  route owns update behavior and import-boundary checks.
