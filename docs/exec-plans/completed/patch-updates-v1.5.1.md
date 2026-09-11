# Patch Updates And v1.5.1

Status: Completed

## Authorized Outcome

Release v1.5.1 with installed-build experiment test mode and automatic discovery,
download, verification, and installation of compatible direct patch updates. Keep
full installers available for new installations and incompatible patch baselines.
The release note is exactly:

> Fixed a bug preventing compiled app versions from accessing experiment test mode

## Workflow And Boundaries

- Existing versions continue selecting the full installer. v1.5.1 introduces patch
  discovery for future releases; a separately downloaded v1.5.0-to-v1.5.1 patch can
  bootstrap a verified v1.5.0 installation.
- `updates/` owns trusted release metadata, compatible selection, bounded transfer,
  cache ownership, and final verified launch. GUI retains its worker lifecycle,
  Download Update and Install and Restart flow with clear patch/full download copy.
- Packaging compares the exact released baseline bundle to the complete target
  bundle. Inno installs changed/added files with the same application identity,
  verifies baseline files, reconciles obsolete owned files, and records the complete
  target inventory. User settings and experiment data are outside patch ownership.
- Publish the full installer, direct patch installer, and versioned update manifest
  together. Do not replace assets under an existing published version.
- Preserve the active updater storage/clean-upgrade plan and its unresolved historical
  acceptance items. This feature does not mark those earlier items complete.

## Verification

1. Updater tests: trusted manifest and asset identity, base matching, actual-file
   verification, cancellation, cache reuse/pruning, and final launch checks.
2. Packaging tests: changed/added/removed files, wrong baselines, unsafe paths,
   complete target inventory, native Inno compilation, and patched/fresh equivalence.
3. Registered GUI tests: patch/full copy and size at the existing minimum/default
   dimensions; installed-build test-mode setting visibility and persistence.
4. Focused updates/packaging/gui/docs routes plus repo precommit. Local Qt execution
   requires a user-approved visible environment; never use offscreen Qt.
5. Authenticate the v1.5.0 baseline, build v1.5.1, verify release artifact hashes and
   exact release notes, and check the public release after publication.

## Progress

- Test-mode source-only restriction removed; focused GUI/docs and mypy passed.
- Final repo precommit passed Ruff, compilation, mypy, and repository audits, then
  reported seven existing Windows temporary-path failures in bundle tests, 1,313
  passes, and five symlink permission skips. The short-path run below passes all
  seven affected tests; no unrelated project-bundle behavior was changed.
- Published v1.5.0 installer authenticated against GitHub asset digest; all 8,030
  retained bundle files and exact manifest bytes match its extracted payload.
- Updater backend: 226 non-Qt tests passed, four existing Windows symlink skips.
- Packaging focused: 168 tests passed. Native lifecycle: 15 stages passed, including
  rejection of corrupt baselines, links and new-path collisions; patch/fresh parity;
  explicit exit-12 failure, known retry, full repair, and uninstall preservation.
  Evidence: `build/patch-installer-lifecycle/native-3qoui7w1/report.json`.
- Full non-Qt suite with short `--basetemp=build/ut151`: 1,320 passed, five symlink
  permission skips. This avoids the default harness's Windows temporary-path limit.
- All 13 changed GUI/updater modules embedded in the executable match the final
  source. Only the FPVS Studio package version changed in the retained build
  environment; runtime dependency versions were preserved.
- Extracted final installers verified without execution: the full installer matches
  all 8,030 target files. The patch replaces/adds 12 files, removes eight obsolete
  owned files, and retains 8,018 files to reproduce the identical target bundle.
  Evidence: `build/release-1.5.1-artifact-verification/verify-7obgck74/report.json`.
- Published [v1.5.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.5.1)
  on 2026-09-11 from `5ae59b4bb4e9b8ddcb96b1643497be74dd92ff49`. Public latest
  release, tag target, exact release note, and all three GitHub asset sizes/digests
  verified. The full installer is 259,056,966 bytes; the direct patch is 27,615,178
  bytes. The update manifest is 435 bytes.
- Production updater functions read the public release and authenticated JSON,
  verified all 8,030 extracted v1.5.0 baseline files, and selected the direct patch.
  The existing full-only selection chose the full installer. Only runtime-root
  detection was redirected to the extracted baseline; no installation was changed.
  Evidence: `build/release-1.5.1/public-updater-verification.json`.
- Visible Qt tests and the packaged GUI smoke were not run because approval for a
  safe visible session was not received. Registered coverage and manual acceptance
  steps are present, but visible layout and packaged interaction remain unverified.
  No production installer or experiment was executed during release preparation.

## Published Artifact SHA-256

- Full installer: `abac838eb7c8d8dc52fbd626a10a04654382c484690b44da3333277150d1386b`
- Direct patch: `cd45069685588a15e91dc30537c4069e701128702ed72e20d3a84468562ca2ea`
- Update manifest: `fbd663a3f543408a5291d5452ad7117e5028913b8881cc310ef14bf5810f152a`
