# Studio 2.5.2 release

Status: Active

Date: 2026-10-28

## Authorized outcome

Bump Studio to 2.5.2, compile the recent changes and publish a stable GitHub release.
Use isolated `release-2.5.2` outputs and preserve existing artifacts, dependency
versions, the working installation, projects and preferences.

## Scope

- Simplify the Experiment Library and project-version dialogs while preserving
  descriptions, version uncertainty, permissions, errors and separate downloads.
- Refresh restored editable bug/feature reports to the running Studio version;
  preserve exact receipt-locked payloads and report identity.
- Remove the electrode-count qualifier from ActiveThree labels and help. Preserve
  recording IDs, acquisition profiles, marker bytes and serial configuration.

## Build and verification

Run packaging-focused verification before and after the version bump. Refresh only
editable app metadata with `--no-deps --no-build-isolation`, compare installed
dependency versions, and compile with `build_release.ps1 -SkipInstall -SkipSmoke
-BuildLabel release-2.5.2`. Publish the full installer, update JSON and both SHA-256
sidecars. No optional direct patch is planned.

Audit frozen versions, compiled application code, ownership inventory and hashes,
native-library sources, update metadata and the GUI-free updater diagnostic. Stage
all assets in a draft, verify GitHub sizes/digests, then publish the matching tag.
Verify immutable-release attestation, independent public downloads and the public
updater's version/repair selection.

The immediately preceding non-Qt precommit passed 3,759 tests with 12 Windows
symlink-permission skips. The subsequent ActiveThree text-only change passed
264 focused tests with one skip, plus Ruff, compilation and mypy. Release work
changes only package version metadata and release records.

## Boundaries

The user explicitly authorizes GitHub publication. Packaged visible GUI,
install/upgrade/uninstall, physical EEG and display timing checks remain unrun.
Do not execute an installer or uninstaller on the working installation. Preserve
the existing documented native-library warnings and disclose verification limits;
publication does not establish acceptance of those unrun checks.

## Progress

- Clean source and remote checked; no incoming changes.
- Packaging baseline passed all 181 tests.
- Canonical version advanced to 2.5.2.
- Packaging checks after the bump passed all 181 tests; docs checks passed ten.
- Only `fpvs-studio` changed among 145 installed distributions (2.5.1 to 2.5.2).
  Source and installed versions agree; `pip check` passes.

Build, artifact and publication evidence will be recorded here after verification.
