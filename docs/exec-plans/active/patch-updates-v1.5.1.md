# Patch Updates And v1.5.1

Status: Active

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
- Earlier repo precommit reported seven bundle-path failures, 1,237 passes and five
  Windows symlink skips. Reassess separately from patch updater regressions.
- Published v1.5.0 installer authenticated against GitHub asset digest; all 8,030
  retained bundle files and exact manifest bytes match its extracted payload.
- Updater backend: 226 non-Qt tests passed, four existing Windows symlink skips.
- Packaging focused: 168 tests passed. Native lifecycle: 15 stages passed, including
  rejection of corrupt baselines, links and new-path collisions; patch/fresh parity;
  explicit exit-12 failure, known retry, full repair, and uninstall preservation.
  Evidence: `build/patch-installer-lifecycle/native-3qoui7w1/report.json`.
- Full non-Qt suite with short `--basetemp=build/ut151`: 1,320 passed, five symlink
  permission skips. This avoids the default harness's Windows temporary-path limit.
- v1.5.1 executable and installer artifact verification is in progress. Visible Qt
  approval is pending. Per the repository default, unapproved Qt checks remain skipped
  and will be reported; the user has explicitly authorized publication. Artifact integrity
  and native installer acceptance remain required before publication.
