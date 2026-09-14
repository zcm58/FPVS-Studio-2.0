# FPVS Studio v1.7.0 release

Status: Completed (2026-09-14)

## Authorized scope

The user requested a version bump, all implementation changes on the main development
branch, a GitHub release with full installer and direct patches, and obsolete branch
cleanup. The repository's default branch is `master`; no branch rename is requested.
Use version `1.7.0` for the new standalone updater/repair feature. Preserve user-owned
experiment output and existing published artifacts.

## Release inputs and gates

- Include the completed independent-updater implementation, native installer integration,
  faster patch candidate selection, and its tests/documentation.
- Refresh only editable app metadata; preserve existing runtime dependencies and use the
  verified sanitized Windows build PATH.
- Prepare direct patches from `1.5.3`, `1.6.0`, and `1.6.1`. The first two inventory
  hashes are authenticated by the published v1.6.1 update JSON; extract the third from
  the retained v1.6.1 full installer after verifying its public GitHub SHA-256.
- Run packaging focused verification and repo precommit. Reuse completed implementation
  GUI/native lifecycle evidence and run the approved bounded visible packaged smoke for
  the new version. Do not install over the user's app.
- Build under `build/release-1.7.0/` and `dist/release-1.7.0/`; validate complete bundle,
  full installer, sparse patch reconstructions, embedded inventories, and release JSON.
- Commit/push source, create a draft release targeting that commit, verify uploaded asset
  bytes against local digests, then publish as latest. Never replace old release assets.
- After publication, delete only fully merged branches with no active worktree or unique
  commits. Retain the default branch, release tags, and any branch with unmerged work.

## Acceptance record

Packaging focused: 179 passed after the version/metadata bump. Repo precommit passed
Ruff, compilation, repository/documentation audits, mypy (167 source files), and 1,534
tests; seven Windows symlink-privilege checks were skipped. Evidence is retained at
`build/release-1.7.0-baseline/precommit.log`.

- Source commit and release tag: `05ac05104d6da9994f684d0578678087ef96bfe3` on
  `master`. Editable package metadata was refreshed to 1.7.0 without updating runtime
  dependencies. All 206 captured build inputs remained unchanged during packaging.
- All 486 native-library source paths match the published v1.6.1 build. The independent
  updater is 44,386,370 bytes. Its frozen version/protocol diagnostic passed with no Qt
  imports, and its visible standalone-repair/failure smoke passed. The main Studio
  packaged smoke passed with matching 1.7.0 metadata and fitting updater controls.
- The full installer and three patches built successfully. Read-only extraction verified
  all 7,059 target files, exact inventories, patch transaction metadata, and reconstruction
  of the full target from each authenticated baseline. No production setup was executed.
- Published [v1.7.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.7.0)
  as latest, stable release ID `388729353`, after comparing every draft asset's size and
  GitHub SHA-256 with the local audit. The published assets were checked again afterward.
- Live helper metadata checks selected the correct patch from 1.5.3, 1.6.0, and 1.6.1
  in 0.750, 0.359, and 0.359 seconds respectively on this machine. Current-version
  detection and same-version full repair passed. These are metadata checks, not an
  installed-upgrade timing guarantee for old clients.
- Deleted fully merged local branches `codex/multi-session-projects` and
  `codex/setup-ux-design-review`; neither had another worktree. Only `master` remains
  locally and remotely. User-owned `output/` was preserved and excluded from commits.
- Implementation evidence includes 79 visible GUI tests and all 15 isolated native
  installer lifecycle scenarios. Clean-PC acceptance and installation over a user's
  working copy were not performed; release notes state this limitation.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| Full installer | 298722395 | `e6560cc643869474d29faee97e9e124d5c3d9f2a65bd0c0fe648205743af8de1` |
| Patch 1.5.3 to 1.7.0 | 71907069 | `6c6165a810b35028affb0e5d3a2f56fde6cc5e958c4581f7b6bd113cd7ab3220` |
| Patch 1.6.0 to 1.7.0 | 71879706 | `1616a3bdd9f25752b313b4ee16b3c0eb9a5bdcfecd879b2c86c13f0882ffb155` |
| Patch 1.6.1 to 1.7.0 | 71879697 | `319dd6e434383561cc3ee183993caf140c6137ef1c4e3af00f50f7ee8ca2bd7c` |
| Update JSON | 1085 | `39d7d7e6a8b49394b1c904d2565472e9f993ee028c0bf64e140a393090ef8112` |

Detailed ignored evidence remains under `build/release-1.7.0-baseline/`:
`build.log`, `build-input-audit.json`, `studio-smoke.json`, `artifact-audit/report.json`,
`github-draft-verification.json`, `github-publication-verification.json`, and
`live-selection.json`. Helper reports are under `build/release-1.7.0/pyinstaller-updater/`.
Published assets are retained under `dist/release-1.7.0/installer/`.
