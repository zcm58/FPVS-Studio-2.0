# FPVS Studio 2.4.3 updater GUI release

Status: Completed

Date: 2026-10-09

## Authorized outcome

Bump the patch version, commit/push the completed updater percentage changes, and
publish a new stable release. The public release body must be exactly:

Improvements to the updater GUI

## Delivery and verification

Build the committed master candidate using the canonical packaging scripts under
isolated `build/release-2.4.3` and `dist/release-2.4.3`. Retain the full installer and
include a direct patch from the authenticated public 2.4.2 ownership inventory.
Verify native dependency preservation, frozen source/version identity, full payload,
exact patch reconstruction, all asset sizes/digests and live updater selection.
Stage as a draft, verify its uploads, then publish and verify exact master/tag refs.

The source implementation already passes repo precommit: 2,921 tests, 20 subtests,
11 Windows symlink-permission skips, Ruff, compilation, mypy and repo/docs audits.
The shared Inno script compiles with a safe synthetic fixture. Run fresh metadata,
packaging and documentation checks after the version bump. Registered Qt, visible
packaged GUI and installed-update checks are unrun; publication was requested after
these boundaries were reported. Do not run an installer on the working installation.

## Acceptance

- [x] Version and editable metadata agree; focused release checks pass.
- [x] Exact source candidate committed and pushed to master.
- [x] Authenticated 2.4.2 baseline and matching build dependencies recorded.
- [x] Full installer, 2.4.2 patch, update JSON and checksum sidecars built.
- [x] Frozen/native/full-payload and exact patch reconstruction audits pass.
- [x] Draft assets match local digests; public release/body/tag verified.
- [x] Live updater selection and final clean master/remote refs verified.

Evidence and logs stay in the isolated ignored release directories. Earlier releases
and drafts remain intact.

Fresh version checks passed: packaging focused (181 tests) and docs focused
(10 tests). Source and installed editable metadata both report 2.4.3. The public
2.4.2 full installer SHA-256 is
`6f42a547bd4139f0a7d0b10b3b5dd38afe11bc0e01f09d7830b456d3efc42b63`;
its authenticated ownership inventory SHA-256 is
`3f3c2863b5acacd0a88fd5de71aa8ce36996bf062550aa8710843d99240f9134`.
All 7,062 baseline payload files match that inventory, and bundled dependency
versions match the local build environment without changes.

## Published outcome

[FPVS Studio 2.4.3](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.3)
is the latest stable immutable release (ID `408223639`). Its body is exactly the
authorized sentence above. All six assets were staged as a draft and their server
sizes/SHA-256 digests checked before publication. Anonymous public metadata, the
four JSON/checksum sidecar contents, GitHub's signed release attestation and all six
signed asset attestations passed verification after publication.

The release tag resolves to the committed and pushed candidate
`bb704e5e2295e69f127db93c2b0ec5f7500dd2d7`. A subsequent documentation-only
completion commit records this evidence on master; application and packaging source
remain identical to the audited candidate.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.3.exe` | 300,729,229 | `ac90e57075790431036b599db793ed36f7a7b874dddab2eb8d3ce22a07c01bfd` |
| `FPVS-Studio-Patch-2.4.2-to-2.4.3.exe` | 74,175,814 | `52f0d0d77f23c709df954838efdf41696a84978c7fe1ca366cdd709b5f49f65a` |
| `FPVS-Studio-Update-2.4.3.json` | 435 | `af0239ea204a4a94a0bee776bdc342d15c7841642c819161761f58181bc880f0` |

Each artifact has its matching `.sha256` sidecar. The full installer contains
7,987 owned payload files. The direct patch installs exactly 955 changed/added
files, removes 12 obsolete owned files and retains 7,032 files; reconstruction
matches the complete full-installer target. The target inventory SHA-256 is
`bf50fff4989efdaa26d5b16f518fcdbdff69026760694a17473c85c285db82a3`.

The four changed Python modules match committed source inside both Studio and the
independent updater. Bundled metadata and the updater's GUI-independent packaging
diagnostic report version 2.4.3. The canonical build used `-SkipInstall -SkipSmoke`
with isolated versioned paths and the authenticated 2.4.2 baseline.

All 482 DLL/Python-extension payload files from 2.4.2 remain byte-identical. The
canonical collector also includes five optional Python/Tcl/Tk files and associated
data that were absent from 2.4.2. Their bytes were separately authenticated against
the immutable public 2.4.1 installer (SHA-256
`3aa9557c89518863b6bc5858fbc84b12ba4e0c5c895565c91e04822238ead551`):
`_testcapi.pyd`, `_testinternalcapi.pyd`, `_tkinter.pyd`, `tcl86t.dll`, and `tk86t.dll`.
All 487 target native payload files match exact PyInstaller analysis input hashes
under the reviewed build environment, Python platform or Windows roots.

Live updater checks select the direct patch for 2.4.2 with its authenticated
inventory, the full installer for missing inventory, forced-full selection, 2.4.1
and pre-updater 1.4.0, and no update for 2.4.3. Every selected asset matches the
published/local digest and size, and the updater displays the exact release note.

## Check boundaries and retained evidence

Registered Qt tests, visible packaged GUI checks and actual installed full/patch
updates remain unrun under the repository's local Qt safety requirement. The user
requested publication after these limitations were reported. No real setup program,
installed-app mutation or project-data mutation was used by the artifact audit.

Evidence in `build/release-2.4.3/` includes `source-commit.txt`, `baselines.json`,
`runtime-versions.json`, `build-release.log`, `artifact-audit.json`,
`legacy-native-authentication.json`, `verified-draft.json`, `published-release.json`,
`public-verification.json` and signed release/asset verification reports. Published
assets are retained in `dist/release-2.4.3/installer/`. The authenticated baseline
and extraction are retained under `build/release-2.4.3-baseline/`.
