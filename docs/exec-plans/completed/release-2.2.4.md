# FPVS Studio 2.2.4 Release

Status: Completed

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

## Publication

- Published stable release `v2.2.4`, marked Latest, at
  <https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.4>.
- Tagged source: `5074c0447f12636cbd6882c13849454c0a9e704d`.
- GitHub release ID: `401024020`. All six assets were verified by size and GitHub
  SHA-256 digest in the draft and again after publication; no old release was replaced.
- Full installer: `FPVS-Studio-Setup-2.2.4.exe`, 299019747 bytes, SHA-256
  `f542c3230ded3fd0960b814c759fff12606d67659d4746e6350339c86bee3dac`.
- Direct patch: `FPVS-Studio-Patch-2.2.3-to-2.2.4.exe`, 72172066 bytes, SHA-256
  `5741e7ea04bcc079dce33f3649a6f99166bc5567cbcfb7f638a7dcae6db3f955`.
- Update JSON: `FPVS-Studio-Update-2.2.4.json`, 435 bytes, SHA-256
  `de43f3aecd91a1fa39d160a477e6a18c14f091ec282284d8270657f7b9c16290`.
- Each asset also has a matching `.sha256` file. Exact artifacts remain under
  `dist/release-2.2.4/installer/`; the full bundle is in
  `dist/release-2.2.4/FPVS Studio/`.

## Acceptance Evidence

- Editable metadata was refreshed with `--no-deps`, leaving the established native
  dependency environment unchanged. The build used the preserved sanitized PATH and
  isolated output directories through the existing executable/installer entry points.
- The retained 2.2.3 installer matched live GitHub metadata: 299022455 bytes, SHA-256
  `9d14f75cc0a1638dd4f8fd97ce7f5fb9780febf153ecdba059ff7d360921be4a`.
  All 7061 extracted owned files and the source manifest were rehashed before reuse.
- Baseline inventory SHA-256:
  `6af542d8dc9ac445f4ea8ea39b13bf8258517fe82c912198452d84171089675b`.
  Target inventory SHA-256:
  `9037a79a974a5307b4ea5428b67ced6056d69a4e4e153ff3f2e530628e56b459`.
- All 7061 full-installer payload files match the final bundle. The direct patch
  changes/adds 14 files, removes eight old metadata files, and retains 7047 unchanged
  files. Extracted patch bytes plus the authenticated baseline reconstruct the full
  target exactly, with zero unchanged payload rewrites. Source, target, payload and
  transaction manifests, update JSON and checksum files all passed.
- All 488 native-library inputs originate in the verified environment or Windows;
  DLL/PYD bytes are unchanged from 2.2.3. All 212 embedded FPVS modules match source
  bytecode, and exactly one complete bundled package metadata directory reports 2.2.4.
- Packaging focused: 181 passed. Repo precommit static checks, compilation, mypy
  (212 source files), harness and docs audits passed. Non-Qt suite: 2540 passed,
  11 Windows symlink-privilege skips, one sandbox named-pipe access failure. The
  isolated multiprocessing-lock test passed outside the sandbox.
- With the user's explicit safe-visible approval, the packaged Studio smoke passed:
  version/metadata, required runtime imports, update dialog/theme/buttons, dismissal,
  and test/pilot controls. The independent updater passed both its no-GUI packaging
  check and bounded visible diagnostic, reporting no network or installer activity.
- Live updater readback selects the 2.2.3 patch, detects 2.2.4 as current, and selects
  the full installer for repair. Live MSMS AB Test 1.1.1 metadata is compatible with
  Studio 2.2.4.
- Evidence is retained under `build/release-2.2.4/`: baseline, artifact, native/source,
  packaged-smoke, updater diagnostics, GitHub draft/publication and live-selection
  reports, plus build/audit helpers and logs.

## Remaining Boundaries

No production installer/uninstaller, clean-PC test, update over the user's working
installation, full registered Qt suite, or physical experiment/EEG reception test
was run. The bounded visible checks do not establish those results. Existing optional
native dependency warnings remain unchanged from the authenticated 2.2.3 payload;
required packaged runtime imports passed. User projects, installed Studio, settings,
prior releases, and untracked `output/` were not changed by packaging.
