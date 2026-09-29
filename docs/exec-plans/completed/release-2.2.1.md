# FPVS Studio 2.2.1 release

Status: Completed

The user requested a patch-version release for the clearer BioSemi serial-port
launch error, with a full installer and direct patches. The release notes contain
exactly this sentence, without headings, bullets, or additional text:

> Updated the error message that presents when a user attempts to launch an experiment without being connected to BioSemi.

## Source and publication

- Source commit `6547556c353ad7b15ed8d588ef2ac8df391eaa42` was committed and pushed on `master` before packaging.
- Annotated tag `v2.2.1` points to that exact source commit.
- [FPVS Studio 2.2.1](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.1)
  is the public latest release with the full installer, patches from 2.1.0 and
  2.2.0, update JSON, and four checksum files. All eight asset sizes and GitHub
  SHA-256 digests match the local audited files. The public release body matches
  the requested sentence exactly.

## Verification

- The error-message change passed repo precommit: 2,242 tests passed, with 10
  Windows symlink-permission skips; Ruff, compilation, mypy and repo audits passed.
- After the version bump, packaging focused passed 181 tests and documentation
  focused passed nine tests. Editable and bundled package metadata are 2.2.1.
- Baseline installers were authenticated against current public GitHub sizes and
  hashes; their ownership manifests were freshly extracted and verified.
- All 7,985 full-installer payload files were extracted and verified. Each patch
  changes/adds 11 files, removes eight and retains 7,974, reconstructing the exact
  full target. All 493 native-library inputs match the authenticated 2.2.0 baseline.
- Both changed embedded Python modules match source-compiled code after normalizing
  source filenames. The frozen updater non-GUI packaging diagnostic passed.
- Live updater selection chooses the correct direct patch for authenticated 2.1.0
  and 2.2.0 inventories. Unsupported or missing inventories choose the full
  installer; 2.2.1 reports no update.

## Installer hashes

- `FPVS-Studio-Setup-2.2.1.exe`: 300,983,551 bytes; SHA-256
  `0b618dc1dbc87ee24b64ad89a67bcdb4b8a2b0cc4d17e839bde9c319a5f86cb2`.
- `FPVS-Studio-Patch-2.1.0-to-2.2.1.exe`: 72,358,653 bytes; SHA-256
  `5ed6bd262ab3894e2131b2977847e4e19df05db40696edf16c1ba57238b93314`.
- `FPVS-Studio-Patch-2.2.0-to-2.2.1.exe`: 72,358,642 bytes; SHA-256
  `f17b38d75518125d5722efd0b5ffd73b8b1c66483508e0025e058780d061eab9`.

## Check boundaries

Visible Studio/updater GUI smoke, installed upgrade/repair/uninstall, clean-PC
installation, physical display timing and BioSemi/EEG checks were not run.
No installer was executed. Source tests, frozen non-GUI diagnostics and extracted
artifact checks do not establish those manual outcomes.

Ignored evidence is retained under `build/release-2.2.1/`; distributable artifacts
are under `dist/release-2.2.1/installer/`.
