# FPVS Studio 2.2.2 release

Status: Completed

The user requested a version bump, a full Windows installer and a direct patch,
with exactly this release note:

> Recording device name is now shown on the home screen prior to launching an experiment.

## Release scope

- Bump the canonical package version from 2.2.1 to 2.2.2.
- Build from the committed source in an isolated `release-2.2.2` build label.
- Authenticate the published 2.2.1 full installer and extract its ownership manifest
  without executing setup; use that exact manifest for the direct patch.
- Preserve the packaging environment's dependency versions and check native payload
  changes against the authenticated baseline.
- Audit the full installer, patch payload and update metadata before publication.
- Create the GitHub Release as a draft, verify every uploaded asset's size and
  SHA-256, then publish with the exact requested release note.

## Verification boundaries

Packaging focused passed 181 tests before the version bump. The preceding Home
change passed focused GUI checks and static repo checks; its two unchanged Windows
unit-test failures passed on targeted rerun outside the sandbox. Registered Qt
coverage was added but not run. This release task does not authorize installing over
the user's working installation or running unapproved visible Qt checks. Record
source, frozen non-GUI and artifact checks separately from those pending outcomes.

## Source and publication

- Source commit `a796a66ee4eaef0c6c4c92373a3ffd7b2d4c30ae` was committed and pushed
  before packaging; annotated tag `v2.2.2` points to that commit.
- [FPVS Studio 2.2.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.2.2)
  is the public latest release. All six asset sizes and GitHub SHA-256 digests
  match the audited local files; the release body matches the requested sentence.

## Verification results

- After the version bump, packaging focused passed 181 tests and documentation
  focused passed nine tests. Editable and bundled package metadata report 2.2.2.
- The authenticated 2.2.1 installer contains 7,985 owned files; its ownership
  manifest SHA-256 is `d696a73fff9dba743ba073d98faa9962230d4e2cbd637796bb9882cbc23afbfe`.
- Full-installer extraction matches all 7,061 target files. The patch changes/adds
  33 files, removes 937 and retains 7,028, reconstructing the exact full target.
  Source, target, transaction and payload manifests and update JSON all match.
- All retained native libraries match the baseline. The 488 native build inputs
  come from the repo Python environment or Windows. This Python distribution omits
  baseline Tk/Tcl resources and CPython test extensions: five native files and
  922 Tk/Tcl resource files are removed, alongside obsolete package metadata.
- All 211 embedded FPVS Studio modules match source-compiled code after normalizing
  filenames. Frozen updater non-GUI packaging diagnostics passed with version 2.2.2.
- Live updater selection chooses the direct patch for 2.2.1; 2.2.2 reports no
  update and repair selects the full installer.

## Installer hashes

- `FPVS-Studio-Setup-2.2.2.exe`: 299,042,200 bytes; SHA-256
  `ccbf10e43a17fe47181964a4e05df720e3fd3c03ad482b98f938a335fcf0e153`.
- `FPVS-Studio-Patch-2.2.1-to-2.2.2.exe`: 72,362,454 bytes; SHA-256
  `d9e07a5bfd3ebf569f1fd50817527d69c4d6604ceda425764eb3fbdcf8d27977`.

## Check boundaries and retained evidence

Visible Studio/updater GUI smoke, installed upgrade/repair/uninstall, clean-PC
installation, physical display timing and EEG checks were not run. No installer
was executed. Source tests, frozen non-GUI diagnostics and extracted artifact checks
do not establish those manual outcomes.

Ignored evidence is retained under `build/release-2.2.2-baseline/` and
`build/release-2.2.2/`; distributable artifacts are under
`dist/release-2.2.2/installer/`.
