# Studio 2.4.7 crash recovery release

Status: Active

## Authorized outcome

Build and publish the validated Studio crash recovery fixes as version 2.4.7 from
the isolated `fix/crash-condition-recovery` worktree. Preserve unrelated edits and
the packaging environment in the primary checkout. Retain the published 2.4.6
release and provide a direct patch from its authenticated inventory alongside the
full installer, independent updater, update manifest and checksum sidecars.

## Preparation and acceptance

- [x] Copy the existing Python 3.10 packaging environment into the worktree and
  refresh only editable Studio metadata with `python -m pip install --no-deps
  --no-build-isolation -e .`; do not upgrade dependencies.
- [x] Authenticate the published 2.4.6 installer using its immutable GitHub release
  attestation, asset digest and size; extract it without running setup and verify
  every owned-file hash against its complete inventory.
- [x] Run `./scripts/verify.ps1 -Scope packaging -Tier focused`.
- [ ] Run the safe repo precommit gate. Final packaging waits for the validated
  source commit.
- [ ] Build the full installer and direct 2.4.6 patch through the canonical release
  script with an isolated `release-2.4.7` build label.
- [ ] Verify extracted full-installer parity, exact patch reconstruction, frozen
  source identity, dependency metadata and sanitized native DLL source paths in
  both PyInstaller analysis records against the authenticated baseline. Restrict
  build-process `PATH` to required verified native dependency directories.
- [ ] Verify updater patch/full/repair selection, all six draft asset digests and
  sizes, exact notes and source tag before publication.
- [ ] Verify public metadata, downloaded assets, signed release/asset attestations
  and updater selection after publication; record remaining qualification limits.

## Baseline and build commands

The authenticated latest stable release is `v2.4.6`. Its full installer has size
300,721,672 bytes and SHA-256
`f3bea0e8bf2fe63cbab258c000a081e14e959c5cfe291f08710e211ee0c4949b`.
Its 7,987-file ownership inventory has SHA-256
`05075c4977e36538aa03704b36ae731438bf8627ed54c940996378a0772f30fb`.
The currently installed inventory independently matches that inventory digest.

Use `gh release verify v2.4.6 --repo zcm58/FPVS-Studio-2.0` and
`gh release verify-asset v2.4.6 <downloaded-installer> --repo
zcm58/FPVS-Studio-2.0` for the retained baseline. The existing `innounp.exe` extractor
has SHA-256 `1c8453c198dd3fe7947f3705e59d2294ddce3dfa9f96a737e94449b119f44181`.

After source validation and commit, use:

```powershell
.\scripts\build_release.ps1 -SkipInstall -SkipSmoke `
  -BuildLabel release-2.4.7 `
  -InnoCompiler "$env:LOCALAPPDATA\Programs\Inno\ISCC.exe" `
  -BaselineInventory 'build/release-2.4.7-baseline/extracted/{app}/fpvs-owned-files-v1.txt' `
  -BaselineInventorySha256 05075c4977e36538aa03704b36ae731438bf8627ed54c940996378a0772f30fb
```

The full installer, patch, manifest and their three checksum sidecars are attached
to one draft release before publication. GitHub immutable releases are enabled;
their signed attestations authenticate the locked tag and assets. Authenticode is
not configured; do not describe the executables as Authenticode signed.

## Preparation evidence

The isolated Python 3.10.11 environment was copied without changing the primary
environment. All 142 dependency distributions retain their versions; only the
isolated editable Studio metadata changed from 2.4.4 to 2.4.7. Both the importable
source path and metadata point to the worktree, and `pip check` passes. The
packaging-focused route passes all 181 tests without GUI execution.

The downloaded 2.4.6 installer passes its GitHub release and asset attestations,
published size and SHA-256 checks. Extraction verifies all 7,987 owned-file hashes
and the complete inventory digest. All 23 non-Studio metadata records in that
bundle match the isolated environment.

Prebuild native custody checks compare the preserved 2.4.4 analysis source paths,
mapped to the isolated environment, with the authenticated 2.4.6 payload bytes:
488 Studio inputs and 69 updater inputs match. The five additional baseline Python
test/Tcl/Tk native files also exactly match their existing PsychoPy `DLLs` sources.
Retain that verified native directory in the restricted build `PATH`; exclude
unrelated application paths such as MATLAB. This is preparation evidence only:
the final build's actual native analysis inputs and payload bytes require another
comparison before publication.

Baseline archives and extraction remain under ignored
`build/release-2.4.7-baseline/`; environment, attestation, packaging-check and native
custody evidence is under `build/release-2.4.7-evidence/`.

## Boundaries

No dependency upgrades, Qt windows, experiment presentation, research uploads or
installer execution are authorized by this packaging preparation. The updater's
bounded non-GUI packaging diagnostic is permitted. `-SkipSmoke` stages artifacts
without establishing visible packaged acceptance. Visible Qt review, actual
installed upgrade, clean-machine installation and physical timing/hardware remain
manual qualification unless separately authorized. Backend activation is owned by
the parent recovery plan and is not part of these packaging commands.
