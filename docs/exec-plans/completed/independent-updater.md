# Independent FPVS Studio Updater

Status: Completed (implementation and isolated build acceptance, 2026-09-14)

## Approved scope

On 2026-09-14 the user authorized full implementation of a separate updater bundled
with Studio's installer, controlled from the existing GUI, and independently available
through a Start Menu Update & Repair entry. This supersedes repeated full baseline
verification at discovery/download: those operations select a candidate from authenticated
release metadata and installed-version/inventory identity; Inno verifies the complete
baseline immediately before mutation and verifies the installed target afterward.

Keep the existing Inno installer, sparse patch format, authenticated GitHub release
boundary, bounded download cache, and preservation of projects/settings/templates/runs/logs.
Do not rebuild Studio on end-user machines. No publication/version bump is part of this
implementation until explicitly requested. Preserve existing latency improvements.

## Ownership and flow

- `updates/helper_*` owns versioned bounded subprocess protocol, independent target
  registration identity, authenticated discovery/download, staged helper runtime,
  parent process identity/wait, installer handoff, results and guarded restart.
- `updater_main.py` is a thin independent entry: pipe worker, managed apply GUI, or
  standalone Update & Repair. Backend worker mode imports no Qt; the independent GUI
  reuses `gui/update_dialog.py` and the existing worker lifecycle.
- Studio callbacks delegate work to the helper. Source development uses the same entry
  in a separate Python process; packaged Studio requires its bundled helper explicitly.
- The onefile helper includes its own minimal Python/Qt dependencies and metadata,
  excludes main authoring/runtime/PsychoPy modules, and is installed under `Updater/`.
- Check quickly, download with package integrity checks, save/close Studio on explicit
  Install and Restart, wait for the identified process to exit, invoke Inno with
  `/NOLAUNCH=1`, then restart only after successful installation. Never force termination.
- Apply/standalone runs from a bounded separate staging area so the installed updater
  can be replaced. Malformed metadata never triggers an integrity-bypassing fallback.
  A failed patch offers explicit full repair; failure/cancellation must never relaunch
  an unverified target. Same-version full repair is explicitly supported.

## Acceptance

Verify no baseline scanning in candidate discovery/download; bounded private IPC and
no arbitrary process/file execution; cancellation, timeout/EOF, identity changes,
concurrent helpers/cache use, failed installer status/no restart, successful single
restart, repair, and staged self replacement. Keep full native patch baseline/target
checks and existing isolated lifecycle sentinels. Run updates/gui/packaging focused
verification and repo precommit; build an isolated candidate and run the previously
approved bounded visible packaged smoke. Never install over the user's application.
Record unperformed installed/clean-PC acceptance honestly. Register new Qt coverage.

## Implementation and evidence (2026-09-14)

- The helper is implemented with bounded JSONL messages, explicit nonce acceptance,
  registered target identity independent of helper version, and a pinned Studio process
  handle. The installation coordinator serializes setup through restart. It never
  terminates Studio; a second running instance blocks installation.
- Candidate checks authenticate the release manifest and inventory identity without
  scanning application payloads. Download SHA-256 and final guarded package verification
  remain required; Inno owns baseline and target file verification.
- Main and startup update callbacks use the subprocess client. Standalone Update &
  Repair supports same-version full repair. Its error surface retains full error text
  and exposes repair after failed installation. A synchronous committed event protects
  installer failures from being mislabeled as pre-install cancellation.
- The independent PyInstaller build has its own runtime and package metadata, excludes
  main authoring/runtime/scientific dependencies, and delays all Qt imports until GUI
  mode. The installer builds it before final ownership inventory generation and includes
  a Start Menu shortcut. Helper staging and uninstall cleanup use narrow owned names.
- Initial isolated helper compile: about 48 MB and 146 Python modules. The compiled
  no-Qt metadata diagnostic and native windowed IPC check both completed in under two
  seconds outside the managed sandbox. Final build evidence will supersede this initial
  candidate after integration checks finish.
- Registered visible updater GUI coverage: **79 passed** in the user-approved Windows
  session. Includes standalone repair, layout, handoff, close-before-start, cancellation,
  and late-cancel/failed-install regressions. The managed sandbox could not support a
  native Qt startup; the same checks succeeded outside it. Tests use isolated settings
  and mocked network/installers.
- Source helper visible smoke passed with synthetic data and no network/setup operations:
  `build/independent-updater-source-smoke.json` and its repair/apply screenshots.
- Native Inno lifecycle: all 15 scenarios passed in
  `build/patch-installer-lifecycle/native-abichpnx/`, including corrupt baselines,
  collisions, links, interrupted-patch recovery, full repair, and uninstall preserving
  six user-data sentinels. Production registration was unchanged.
- Frozen-process launch now gives each child its own runtime, sanitizes child library
  paths, and temporarily restores native DLL search for process creation. Unaccepted
  pipe-worker cancellation has an eight-second watchdog, atomically disarmed at handoff;
  EOF-first teardown lets the onefile bootloader finish cleanup before forced fallback.
- Final local gates passed: repo precommit **1,534 passed / 7 Windows symlink permission
  skips**, full-source mypy (**167 files**), Ruff, import boundaries, and repository/docs
  audits. Focused updates **309 passed / 4 permission skips**, packaging **179 passed**,
  and GUI static/compilation checks passed. A sandbox-denied existing named-pipe test
  passed in the ordinary Windows execution context; no test behavior was weakened.
- Final isolated build completed under `dist/independent-updater-integration/`.
  The installer is `installer/FPVS-Studio-Setup-1.6.1.exe`, **298,737,710 bytes**,
  SHA-256 `603f5f4b76ceec3c53f0eecda12bfffb3b97e94aeec8d4b1adbdbf1b9b2b2253`.
  This is a development acceptance artifact using unchanged package version metadata;
  never replace the already-published v1.6.1 assets with these bytes.
- Final helper: **44,385,450 bytes**, SHA-256
  `a3d7e737b20b35097c659d94dbcd62e9e4fbfe3180de1e5cad91e07b455a7d79`.
  It contains 147 Python modules with no Studio controller/runtime/scientific modules.
  Its strict no-Qt diagnostic, windowed pipe protocol check, and visible synthetic
  repair/failure smoke passed. The Studio packaged smoke also passed.
- Final 7,059-file ownership inventory contains the exact helper bytes. All 206 build
  input hashes were unchanged across compilation. The actual Inno script compiled
  successfully, including its new helper-cache cleanup. Evidence is under
  `build/independent-updater-integration/`, including `integration-build-audit.json`,
  `studio-smoke.json`, and `pyinstaller-updater/gui-smoke.json` plus screenshots.
- Read-only extraction confirmed the installer embeds the exact helper SHA-256 and
  byte-identical 7,059-file inventory. See `installer-container-audit.json`; no setup
  was executed for this container audit.
- The requested implementation is complete. Production installation over an existing
  user's app and clean-PC acceptance were not executed; those remain release checks.
  No version bump, publication, commit, or push occurred during this implementation.
