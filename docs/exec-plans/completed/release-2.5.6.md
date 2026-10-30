# Studio 2.5.6 release

Status: Completed

Date: 2026-10-30

## Authorized outcome

Bump the version, compile automatic Library project update detection and publish
a stable GitHub release with compact bullet-only notes. Current source/public
version is 2.5.5; the next patch is 2.5.6. Preserve dependencies, existing artifacts,
the working installation, projects and preferences. Use isolated `release-2.5.6` outputs.

## Scope and verification

Source `3862f41` checks linked projects on open and every five idle minutes, offers
eligible new published versions once per project/release/session, defers during
presentation/modal/background activity, and respects opt-out. Installation remains
an explicit separate-project import. The change passed 3,980 non-Qt tests with 12
Windows permission skips, Library focused (416 with three skips), GUI focused (98),
docs focused (10), Ruff/compilation and mypy over 249 source modules.

Run packaging checks before/after the bump. Refresh only editable app metadata
with `--no-deps --no-build-isolation`, preserving dependency versions. Compile using
`build_release.ps1 -SkipInstall -SkipSmoke -BuildLabel release-2.5.6`. Publish the
full installer, update manifest and both checksum sidecars; no optional patch.
Audit frozen source/versions, inventory/hashes, native input paths and warnings.
Compare with preserved local 2.5.3 evidence, since no local 2.5.5 build is available.
Verify draft asset digests before publishing, then immutable-release attestations,
independent public downloads and the production updater's version/repair selection.

## Boundaries

The user explicitly authorizes publication. Qt/visible GUI, installation lifecycle,
physical EEG and display timing checks remain unrun. No installer/uninstaller is
executed on the working installation. Preserve and disclose existing native-library
warnings. Publication does not establish acceptance of unrun checks.

## Progress

- Clean source; remote pulled and already current.
- Canonical version advanced to 2.5.6.
- Packaging checks passed 183 cases before and after the bump; docs checks passed ten.
- Only `fpvs-studio` changed among 145 installed distributions (metadata 2.5.3 to
  2.5.6); source metadata had already been 2.5.5. All dependencies remain unchanged,
  source/installed versions now agree, and `pip check` passes.

## Build and artifact evidence

PyInstaller 6.20.0 and Inno Setup 6.7.3 compiled the Studio bundle, independent
updater and full installer using a constrained build PATH. All 7,062 bundle files
match the ownership inventory, whose SHA-256 is
`60e1b57ecf5602d153bc00de710c56e38f364c182619337a18a02548ea66c383`.

Both frozen package metadata versions and the GUI-free updater diagnostic report
2.5.6. The diagnostic confirms frozen mode, protocol 1 and `gui_loaded=false`.
All 249 Studio modules plus its entry and all 22 updater modules plus its entry
equal current compiled source. `fpvs_studio.gui.project_update_controller` is
present and source-equal in the frozen Studio executable.

All 486 Studio and 69 updater native input paths/hashes exactly match the preserved
local 2.5.3 audit. All 22 normalized build warnings match that baseline, including
the five known MeshPy/PyTables missing-library warnings described in the
[2.5.1 record](release-2.5.1.md#existing-native-library-warnings). No foreign native
source paths were accepted. This comparison does not extract or execute an installer,
or establish parity with a published 2.5.5 installation.

| Published artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.6.exe` | 298824768 | `c10e1f1016342d858bad3a81bf0f79b6db290aac4260c7b2d5ffecd3bf6890d8` |
| `FPVS-Studio-Setup-2.5.6.exe.sha256` | 95 | `b546c42da7d2f47a1100932c2b5806f8203ac147ca8b39c8c80c3b114f9d06c4` |
| `FPVS-Studio-Update-2.5.6.json` | 107 | `c7cde5e3e6057398ed286db7492b085898de2c621f6a9ffb3a115f680877ad2b` |
| `FPVS-Studio-Update-2.5.6.json.sha256` | 97 | `f3ca7f91973d7c595c671f08af183182cbd8da815a9c2ba8a7adaefae8ec4fb5` |

The update manifest identifies 2.5.6/windows-x64 with an empty patch list. Both
sidecars match their artifacts. Evidence and rerunnable audits remain under ignored
`build/release-2.5.6-evidence/`; installer/bundle outputs remain under
`dist/release-2.5.6/`.

## GitHub publication

[v2.5.6](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.5.6), release
`429058425`, is the latest stable immutable release at publication. Annotated tag
`4d2ca2987b760023bb2ffc87237012ebd214e498` resolves to exact build source
`7e176441c9f143c79c6fd59dee4b4b9359caf388`.

All four draft assets matched local names, sizes and GitHub SHA-256 digests before
publication. GitHub's release attestation verifies the tag/assets. All four
independently downloaded public files match their audited sizes/hashes and pass
`gh release verify-asset`. The release body contains only the two short bullets
below; validation normalizes Windows/Unix line endings before comparing their text.

Eight live public updater cases pass: older 2.4.4 and previous 2.5.5 select the full
installer; registered-style, forced-full and repair selection retain it; current
2.5.6 reports no update and permits repair; newer 2.5.7 rejects downgrade repair.
Production bounded fetching authenticates the public manifest. These checks read
no installed application, import no Qt and execute no installer.

## Published notes

- Automatically detect new Library project versions.
- Offer updates when safe, keeping existing projects intact.
