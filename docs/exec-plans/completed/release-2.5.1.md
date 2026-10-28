# Studio 2.5.1 local release build

Status: Completed

Date: 2026-10-28

## Authorized outcome

Bump the version, compile a new local release, and commit and push the source.
Use isolated `release-2.5.1` build outputs and preserve existing installers,
the working installation, projects, preferences and dependency versions.

## Scope

- Selected-port checks for Brain Products hardware and editable BioSemi ports,
  with regression coverage for exact BioSemi marker bytes and runtime handoff.
- Quieter launch screens, clearer startup reporting notices, project-opening
  priority and one-time interrupted-session acknowledgements.
- More resilient diagnostic logging and crash recovery, safe reporting failure
  details and stronger credential redaction.

## Build and verification

Run packaging-focused verification, refresh only editable app metadata, and compile
the full installer with `build_release.ps1 -SkipInstall -SkipSmoke -BuildLabel
release-2.5.1`. Run the updater's GUI-free packaging diagnostic and inspect the built
versions, ownership inventory, artifact hashes and native-library source paths.
No authenticated 2.5.0 baseline is present on this build host, so this build uses a
full installer and update manifest without an optional direct patch.

The existing 3,747-test non-Qt precommit gate passed for the unchanged application
source in `266a49e`, with 12 Windows symlink-permission skips. Release-specific
verification and artifact evidence are recorded below.

## Boundaries

This request compiles a local candidate and pushes source; it does not publish a
GitHub Release. Packaged visible GUI, fresh install, upgrade/uninstall, physical EEG
and display timing acceptance remain pending. No installer or uninstaller will run
on the working installation. Skipping the visible smoke is recorded explicitly and
does not establish release acceptance or a cause for the unreproduced startup hang.

## Progress

- Packaging-focused baseline passed: 181 tests.
- Version advanced from 2.5.0 to 2.5.1 in the canonical package metadata.
- Packaging-focused verification after the bump passed all 181 tests; documentation
  checks passed ten. The existing full application precommit result remains the
  source gate; this follow-up changes only version metadata and release records.
- Editable metadata was refreshed with `--no-deps --no-build-isolation`. Of 145
  installed distributions, only `fpvs-studio` changed (2.4.4 to 2.5.1); `pip check`
  passes. Source and installed package versions both report 2.5.1.
- PyInstaller 6.20.0 and Inno Setup 6.7.3 compiled the isolated Studio bundle,
  independent updater, full installer, update JSON and checksum sidecars. The build
  process PATH excluded unrelated application directories. Existing outputs and the
  working installation were preserved.

## Artifact checks

The GUI-free updater diagnostic reports version 2.5.1, frozen mode, protocol 1 and
`gui_loaded=false`. Studio and embedded updater package metadata both report 2.5.1.
All 7,062 bundle file paths and hashes match the generated ownership inventory,
whose SHA-256 is `13e3d1511b0d9ecc7f85772ae9135446c6cb794ccf15adeaa6b58955ecc2b776`.

All 245 frozen Studio application modules plus its entry script, and all 22 updater
application modules plus its entry script, compare equal to current source code
compiled with the same frozen filename and optimization level. No application
modules were imported or executed by this static audit. All 486 Studio and 69 updater
native source records resolve only within the build environment, its Python runtime
and Windows; no foreign application-library sources were accepted.

The update manifest names 2.5.1/windows-x64 with an empty patch list. Both generated
checksum sidecars match their artifacts. Evidence, build logs, dependency-version
snapshots and audit scripts remain under `build/release-2.5.1-evidence/`; bundle and
installer outputs remain under `dist/release-2.5.1/`.

| Local artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.5.1.exe` | 298789930 | `664ef3e89b9be5b1bebfcb20e4f3642f817e4970b88fa8dafbb10a17055fac9f` |
| `FPVS-Studio-Setup-2.5.1.exe.sha256` | 95 | `9e96120bd9f5ac905b4e30bdee69b43e71eead2634baaaf317e761b4210e7c9b` |
| `FPVS-Studio-Update-2.5.1.json` | 107 | `725fc28da771797aa9fb77fe4077f261bced9075976801c273f94a67bec01cf2` |
| `FPVS-Studio-Update-2.5.1.json.sha256` | 97 | `d8d4fc737cb8b33f368a485596132e7f1433a0d01c373a1a845c65c6b295b0b1` |

## Existing native-library warnings

Five PyInstaller warnings also appear in the prior local 2.4.4 build log. The
affected MeshPy extension and both Blosc2 DLLs are byte-identical between those
local bundles. PyTables carries a repaired Blosc2 copy with all three hashed
compression dependencies bundled; the warnings refer to its redundant legacy copy.
MeshPy's bare GCC runtime dependencies remain absent. Static source and packaged
`pyglet` 1.4.11 metadata show that the current ShapeStim path selects legacy GLU
tessellation before the optional MeshPy import. These observations preserve the
warnings and do not substitute for native presentation qualification.

The audit checks bundle contents and compiled artifact checksums. It does not
extract the resulting Inno payload, compare dependency bytes with the absent
authenticated 2.5.0 baseline, establish packaged GUI startup, or qualify installed
lifecycle, EEG hardware or display timing. No release was uploaded or published.
