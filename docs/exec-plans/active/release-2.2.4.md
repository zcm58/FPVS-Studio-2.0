# FPVS Studio 2.2.4 Release

Status: Active

## Scope

Bundle and release the requested Studio 2.2.4 update containing the MSMS AB
repeated-target timing and all-character trigger support. Preserve the user's
untracked output and previous published/build artifacts. The MSMS AB Test 1.1.1
experiment is already published with a minimum Studio version of 2.2.4.

## Release Route

- Bump only the canonical package version in pyproject.toml and refresh editable
  metadata without changing dependency versions.
- Build Studio and the independent updater under isolated release-2.2.4 folders,
  using the existing packaging entry points and authenticated native dependencies.
- Authenticate the published 2.2.3 installer and its extracted ownership inventory;
  generate a direct 2.2.3-to-2.2.4 patch alongside the full installer/update JSON.
- Run safe source checks and bounded package diagnostics. Visible packaged smoke
  needs explicit safe-session approval, requested separately. Never install over the
  user's working app or run an experiment as part of this release.
- Commit the versioned source, prepare the matching Git tag and draft GitHub release,
  upload all assets, and verify remote sizes and SHA-256 digests before publication.
- Record the exact artifacts, source commit, verification, and unperformed physical
  EEG/clean-PC acceptance in this plan; archive it when publication is complete.

## Verification

Packaging baseline: 181 focused tests passed. The preceding MSMS changes passed
compiler, engine, runtime, config and safe GUI checks plus broad non-Qt verification;
the one sandbox named-pipe failure passed in an ordinary execution context. Refresh
the relevant checks for the versioned source before publishing.

## Progress

- Version bump and isolated build preparation underway.
- User approved the bounded visible Studio/updater smoke checks; run them after
  the isolated build finishes. No installed-app mutation or experiment launch.
