# Library project updates and Masking release 1.9.0

Status: Completed

## Authorized scope

The user requested a version bump and release of the completed features. Use minor
version 1.9.0 for the new project-version workflow. Merge the feature into master,
publish the Windows full installer and a direct patch from the latest published
version, 1.8.1. Source-only version 1.8.2 has no published installer baseline.
Older and unregistered installations retain the full installer path.

Include on-open Library version checks, passive Home notices, explicit separate-copy
updates, version receipts and legacy linking. Also include the native Masking framework,
corrected Color circle sizing, nine condition markers and intervening master changes.
Keep authored projects and participant data outside installer ownership.

## Delivery and verification

1. Bump canonical metadata, refresh the editable package without dependency upgrades,
   run packaging checks and commit the exact candidate on master.
2. Build under ignored build/release-1.9.0 and dist/release-1.9.0 paths, using the
   authenticated published 1.8.1 installer inventory as the only patch baseline.
3. Verify full payload hashes, exact patch reconstruction, embedded changed modules,
   native inputs, release asset digests and live updater selection.
4. Upload a draft, verify all assets, publish, and record the source commit and URL.

The feature precommit gate passed 2,065 tests with 10 unavailable Windows symlink
skips, plus Ruff, compilation, mypy and repository audits. Its live Masking catalog
and temporary separate-import checks passed. Visible Qt/packaged GUI, clean-PC
installation, installed upgrade, physical display and EEG checks remain unrun.
This release request follows disclosure of the unrun GUI checks; do not claim them
as verified or run destructive lifecycle checks on the working installation.

## Published result

- Release source and annotated tag `v1.9.0` identify
  `30b14a1c8f350669897a6c7d6b8a09d3219045aa` on master.
- [Release v1.9.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.9.0)
  (ID 394249704) is published as the latest stable release. All six public asset
  sizes and GitHub SHA-256 digests match local artifacts; public checksum files and
  the update manifest were downloaded anonymously and verified.
- Packaging focused passed 181 tests before and after the version bump. Docs focused
  passed 9 tests. The frozen updater diagnostic confirms version 1.9.0 and protocol 1
  without loading GUI code. All 63 changed embedded application modules match compiled
  release source. The four project-update modules and Masking font/license are present.
- Full-installer extraction verified all 7,985 owned files. The patch changes/adds
  15 files, removes eight obsolete files and retains 7,970. Reconstructing from the
  authenticated published 1.8.1 inventory matches every target file hash.
- All 493 native-library inputs match published 1.8.1 bytes; no runtime dependency
  upgrades were introduced. Installer extraction did not execute setup.
- Live updater discovery selects the patch for the authenticated 1.8.1 inventory,
  the full installer for 1.8.0 and unregistered 1.8.1/1.8.2 cases, and no update for
  1.9.0. These are candidate-selection checks, not installed-upgrade acceptance.
- Build and verification evidence is retained under `build/release-1.9.0/`, with
  distributables in `dist/release-1.9.0/installer/`. Completed local project-update and
  Masking branches were deleted only after verifying they were fully merged.
- Visible Qt/packaged GUI, clean-PC installation, installed upgrade, physical display
  and EEG checks remain unrun, as disclosed in the release notes.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-1.9.0.exe` | 300960024 | `242445b4bdf6707b50d3c172279103f8043c1bf6b412f9c95d5cc49c468f3504` |
| `FPVS-Studio-Patch-1.8.1-to-1.9.0.exe` | 72343952 | `3dd1f19a1e14434bf0a06d5cb5e50fca839067a2725def9b20c5894cac0f8736` |
| `FPVS-Studio-Update-1.9.0.json` | 435 | `a5ed91538f96692c69754d1b47e678e8f2650044029bcf7ac8e79578a7f596d2` |

Each artifact has a published `.sha256` companion. No patch is advertised for an
unpublished 1.8.2 installer or for any other baseline.
