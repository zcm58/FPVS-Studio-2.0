# Studio 3.1.4 release

Status: Completed

GitHub published [FPVS Studio 3.1.4](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v3.1.4)
as the latest stable immutable Windows x64 release on 2026-11-22 at 03:52 UTC.
Release ID is `454179335`. The tag points to
`da9dd5843b8c4ea4f309db00aad82b16c21677ca`.

- The patch release includes faster stimulus scans, session preparation, Manage
  Projects, Participant Results, and Toolbox handoff, plus the Experiment Library
  preview for the FPVS Oddball Demo.
- Packaging passed 215 tests. Updater verification passed 377 tests with four
  Windows symlink permission skips. [Exact-source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44980779153)
  passed all six jobs, including 6,610 Windows tests with 28 skips, both macOS
  architectures, and portable-project return checks.
- Native origin audits covered 485 Studio and 69 updater files. All 481 shared
  installed DLLs and Python extensions matched the 3.1.3 inventory by hash. The
  new bundle removed two unused Tk extensions, retained WXAgg, and matched the
  demo preview image hashes against the source files.
  The packaged updater backend diagnostic passed.
- The [hosted installer run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/44981420232)
  verified fresh install, upgrade from 3.1.3, uninstall, and all 7,070 owned files
  on both installs. It confirmed removal of obsolete files and preservation of
  settings, projects, and unrelated files. Native Studio runtime and updater
  checks passed within the hosted Library dialog's previously observed desktop
  cap of 1,028 × 749 for a requested 1,040 × 760 window.
- All four draft assets matched their local sizes and SHA-256 digests before
  publication. The downloaded public assets matched the verified build and
  passed GitHub release attestation verification. The live updater offered the
  full installer to 3.1.2 and 3.1.3 and reported 3.1.4 as current.

The 299,556,194-byte Windows installer has SHA-256
`9353e8a1f5e1c4795b61d884f6da2aa938d233bd03a4a67c9fb5059b71f0d46e`.
The installer and update files are retained under `dist/release-3.1.4/installer/`
and the evidence under `build/release-3.1.4-evidence/`.
