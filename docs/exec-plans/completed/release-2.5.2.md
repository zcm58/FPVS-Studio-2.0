# Studio 2.5.2 release

Status: Completed

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

Packaging-focused verification passed before and after the bump. Only editable
app metadata was refreshed with `--no-deps --no-build-isolation`. The isolated
build used `build_release.ps1 -SkipInstall -SkipSmoke -BuildLabel release-2.5.2`.
The full installer, update JSON and both SHA-256 sidecars are published. No optional
direct patch was generated.

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
- PyInstaller 6.20.0 and Inno Setup 6.7.3 compiled the Studio bundle, independent
  updater and full installer using a build PATH limited to the environment, its
  Python runtime, Windows and Inno Setup.

## Artifact verification

Both frozen package metadata versions and the GUI-free updater diagnostic report
2.5.2; the diagnostic confirms frozen mode, protocol 1 and `gui_loaded=false`.
All 7,062 bundle files match the generated ownership inventory, whose SHA-256 is
`1a5c1d6e9886d8c5d5d2f59a5d7d374e25529488cd5d05ee61a8009ce96a02fe`.

All 245 Studio application modules plus its entry script and all 22 updater
application modules plus its entry script equal current compiled source. All 486
Studio and 69 updater native input paths and hashes exactly match the preserved
local 2.5.1 audit. No foreign application paths were accepted. All 22 normalized
build warnings match 2.5.1, including the five known MeshPy/PyTables missing-library
warnings described in the [previous release record](release-2.5.1.md#existing-native-library-warnings).
This comparison does not extract or execute either published installer.

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.2.exe` | 298810249 | `7188baa8e490622d1ed7a1c7cff1bf3523834ac39de239eefb0ad507a85a41e0` |
| `FPVS-Studio-Setup-2.5.2.exe.sha256` | 95 | `9571abdbecc5f15cde769fbdb6babbb8c8e09b3ffbb3fad67722ee9bf8c1be33` |
| `FPVS-Studio-Update-2.5.2.json` | 107 | `705feb85bf56dada1b6b9537ba8bd9edbb8575bb40feab2f960b44d3d7a18786` |
| `FPVS-Studio-Update-2.5.2.json.sha256` | 97 | `e393d3ec8b074bb9c388bc9f263ebd634d4be252a9dc04778471a7dab0b40021` |

The update manifest identifies 2.5.2/windows-x64 and an empty patch list. Both
sidecars match their artifact bytes. Build, dependency, artifact, warning and
publication evidence remains under ignored `build/release-2.5.2-evidence/`; bundle
and installer outputs remain under `dist/release-2.5.2/`.

## GitHub publication

[v2.5.2](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.2), release
`427277915`, is the latest stable immutable release at publication. Its annotated
tag object `4614f4cb654f28f9ab2e3bf818f4f25eee8855ad` resolves to exact build source
`1d320351096d4c3a68adced311c8debd3108c770`.

All four draft assets matched local names, sizes and GitHub SHA-256 digests before
publication. GitHub's release attestation verifies the tag and assets. All four
independently downloaded public assets match their audited sizes/hashes and pass
`gh release verify-asset`.

Eight live public updater cases pass: older 2.4.4 and previous 2.5.1 select the
verified full installer; registered-style, forced-full and repair selection retain
it; current 2.5.2 reports no update and permits repair; newer 2.5.3 rejects downgrade
repair. Production bounded fetching authenticates the public update manifest.
These checks read no installed application, import no Qt and execute no installer.

## Published notes

- Simplify the Experiment Library and project-version dialogs with shorter labels and less secondary text.
- Show the current Studio version when reopening saved editable bug reports and feature requests.
- Remove the electrode count from BioSemi ActiveThree labels and guidance while preserving trigger behavior.
