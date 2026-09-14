# FPVS Studio v1.7.0 release

Status: Active

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
`build/release-1.7.0-baseline/precommit.log`. Artifact/publication evidence will be
recorded after completion.
