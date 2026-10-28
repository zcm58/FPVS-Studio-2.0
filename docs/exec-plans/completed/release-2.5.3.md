# Studio 2.5.3 release

Status: Completed

Date: 2026-10-28

## Authorized outcome

Bump Studio to 2.5.3, compile the updater bullet-formatting fix and publish it on
GitHub with compact, bullet-only release notes. Use isolated `release-2.5.3`
outputs; preserve dependencies, prior artifacts, the working installation and
all project/user data.

## Scope

Source `446e0ff` keeps release-note bullets on separate lines, bounds the preview
to four lines and 240 characters, and retains full summary text in the tooltip
and accessible description. The release-page action and update lifecycle retain
their current behavior. Release notes contain two short bullets under 240 characters.

## Verification and build

The fix passed 52 updater unit cases, GUI focused (95), docs focused (10), Ruff,
compilation and mypy over 245 source modules. Four line-preservation regressions
also failed against the previous implementation. Registered Qt coverage exists
at both dialog sizes and palettes and remains unrun.

Packaging-focused checks passed before and after the bump. Only editable app
metadata was refreshed using `--no-deps --no-build-isolation`. The preserved
environment compiled the isolated build with `build_release.ps1 -SkipInstall
-SkipSmoke -BuildLabel release-2.5.3`. The full installer, update JSON and both
checksum sidecars are published; no optional direct patch was generated.

## Boundaries

The user explicitly authorizes publication. Visible GUI, install/upgrade/uninstall,
physical EEG and display timing checks remain unrun. Do not execute an installer
or uninstaller on the working installation. Preserve documented native warnings;
publication does not establish acceptance of unrun checks.

## Progress

- Clean source and remote checked; no incoming changes.
- Packaging baseline passed all 181 tests.
- Canonical version advanced to 2.5.3.
- Packaging checks after the bump passed all 181 tests; docs checks passed ten.
- Among 145 installed distributions, only `fpvs-studio` changed (2.5.2 to 2.5.3).
  Source and installed versions agree, and `pip check` passes.
- PyInstaller 6.20.0 and Inno Setup 6.7.3 compiled the Studio bundle, independent
  updater and full installer. The build PATH excluded unrelated applications.

## Artifact verification

Both bundled package metadata versions and the updater's GUI-free diagnostic report
2.5.3; the diagnostic confirms frozen mode, protocol 1 and `gui_loaded=false`.
All 7,062 bundle files match the generated ownership inventory, whose SHA-256 is
`0e4556be20f09ee537704a83fb0fe13a7f2a8f5ec2ca8d7aa2d7dc0f74bc1d86`.

All 245 Studio application modules plus its entry and all 22 updater application
modules plus its entry equal current compiled source. A separate frozen-module
check confirms `fpvs_studio.gui.update_dialog` is present and source-equal in both
executables, so the bullet fix is included in Studio and Update & Repair.

All 486 Studio and 69 updater native input paths/hashes exactly match the preserved
local 2.5.2 audit. All 22 normalized warnings are unchanged, including the five known
MeshPy/PyTables missing-library warnings described in the
[2.5.1 record](release-2.5.1.md#existing-native-library-warnings). No foreign native
source paths were accepted. This comparison does not extract or execute an installer.

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.3.exe` | 298787887 | `20bab4786b392d5e96767a838227c8e23961fbf8d6e75aa920a8e75de8e560ed` |
| `FPVS-Studio-Setup-2.5.3.exe.sha256` | 95 | `562152b1f206dfd4f7f22412471b88a3993e5d190445e6892a4bfd7ef6520105` |
| `FPVS-Studio-Update-2.5.3.json` | 107 | `f4bbd1c4e0c2135aa8981236e6257e0a1ab7040cff65b7184d98c81fa52c3e05` |
| `FPVS-Studio-Update-2.5.3.json.sha256` | 97 | `0f0614d6c226aa749eaa8983f4cd10eb53eb9f3355412daebf112d3907e0ce99` |

The update manifest names 2.5.3/windows-x64 and an empty patch list. Both sidecars
match their artifacts. Logs, dependency snapshots, audits, frozen-dialog checks and
publication evidence remain under ignored `build/release-2.5.3-evidence/`;
bundle/installer outputs remain under `dist/release-2.5.3/`.

## GitHub publication

[v2.5.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.3), release
`427307683`, is the latest stable immutable release at publication. The annotated
tag object `23cb95478bf3e9090f02e58dd4b916ef0856bbac` resolves to exact build source
`96b96b85c3958feca8b9e269dce800b29ec9caa8`.

All four draft assets matched local names, sizes and GitHub SHA-256 values before
publication. GitHub's release attestation verifies the tag and assets. All four
independently downloaded public assets match their audited sizes/hashes and pass
`gh release verify-asset`. The release body matches the two short bullets below
(105 characters including the final newline).

Eight live public updater cases pass: older 2.4.4 and previous 2.5.2 select the
verified full installer; registered-style, forced-full and repair selection retain
it; current 2.5.3 reports no update and permits repair; newer 2.5.4 rejects downgrade
repair. Production bounded fetching authenticates the public update manifest.
These checks read no installed application, import no Qt and execute no installer.

## Published notes

- Show release-note bullets on separate lines.
- Keep long previews compact, with full text in tooltips.
