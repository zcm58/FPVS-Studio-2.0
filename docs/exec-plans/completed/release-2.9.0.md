# Studio 2.9.0 release

Status: Completed

## Requested outcome

Authorized on 2026-11-10. Bump Studio and publish a new GitHub release with the
Settings category sidebar and scrollable right-side pages. Include the previously
requested restricted Windows build PATH and pre-upload DLL-origin verification.

Use 2.9.0 for this user-facing Settings redesign. Build from an isolated source
checkout and copied, pinned dependency environment. Preserve the existing controls,
per-computer preferences and project recording callbacks.

## Acceptance

- [x] Source Settings checks passed 99 visible cases at the prior feature commit.
- [x] Verify the reviewed DLL-origin changes and new version in the release checkout.
- [x] Expand frozen Settings smoke coverage to all categories and overflow scrolling.
- [x] Commit the exact build source and run focused, precommit and GitHub CI checks.
- [x] Build the full installer and update manifest with restricted build PATH.
- [x] Run native packaged Studio/updater checks and verify frozen Settings behavior.
- [x] Audit DLL origins and compare native dependencies with authenticated 2.8.2 output.
- [x] Create a draft with all assets, verify remote hashes and publish immutable/latest.
- [x] Verify fresh public downloads, attestations and updater selection.
- [x] Record the exact source, artifacts and checks, and archive this plan.

## Scope

Settings uses General, Recording, Appearance, Workspace, Advanced and Diagnostics.
Each category retains its controls and scroll position. Navigation and Close remain
fixed while page content scrolls. Native visible checks use the approved Windows
desktop and synthetic inputs. Installer acceptance uses extraction and disposable
output, with real acquisition hardware qualification outside this UI release.

The Windows artifact route produces a full installer, update JSON and SHA-256
sidecars. Direct patches are optional and require an authenticated matching baseline.
Release notes use short user-facing bullets. Detailed verification belongs here and
under ignored `build/release-2.9.0-evidence/`.

## Source preparation

- The isolated dependency copy retains the existing runtime versions. Refreshed
  editable package metadata and the source both report 2.9.0.
- Packaging focused verification passed 212 tests, including process PATH restoration,
  foreign DLL rejection and release receipt mismatch detection.
- The expanded visible Settings smoke helper passed 24 category/size/theme cases and
  two wheel-overflow cases in source before freezing the application.
- The published immutable 2.8.2 installer and sidecar passed asset attestation and
  digest verification. Its extracted inventory verifies all 7,987 owned files.

## Final source and build

The installer was built from `45e07c4ccf299697e239c55a02386bbfb00fb4a9` in the
clean `fpvs290-final` checkout under label `release-2.9.0`. The source tag points
to that commit. This completed record is a later documentation update.

The initial candidate passed the packaged checks. Comparison with 2.8.2 identified
different development-package versions and absent Python test and Tcl/Tk components.
The final build used a task-owned copy of the preserved full Python 3.10.11 base and
dependency environment. Editable metadata was refreshed to 2.9.0 with runtime
dependencies preserved. The final native and vendor code comparison passed.

- Local exact-source precommit passed 5,892 tests with 33 platform and permission
  skips. Windows and Darwin type checks and the repository audits passed.
- All six exact-source Windows/macOS source and transfer jobs passed. Windows
  reported 5,904 tests and 24 subtests passed with 21 skips.
  [Source CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42945464581).
- Documentation build and deployment passed on `3379da3`. The Docs workflow,
  configuration, site source and version file have identical Git inputs at the tag.
  [Docs CI](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/42944182269).
- The frozen Studio executable passed 24 Settings category, theme and size checks,
  two mouse-wheel overflow checks, 58 online-workflow states and dependency imports.
  Both packaged applications report 2.9.0. The updater passed Update and Repair
  smoke checks with synthetic requests.
- The native-origin audit approved 491 Studio and 69 updater files. The compiled
  module check matched 283 Studio and 25 updater modules to exact source. Native,
  vendor, bootstrap and standard-library checks matched authenticated 2.8.2.
- Inno extraction verified all 7,989 owned files against the compiled bundle and
  exact generated inventory. The installed inventory SHA-256 is
  `5e8f9bb5e7836ed2f7f85dbd93e3e79736d4e11acdd2465be0d5132002c0cb1c`.
  The pre-upload receipt matched both audited TOCs and all release assets.

## Publication

FPVS Studio 2.9.0 was published as latest, stable and immutable on November 10, 2026
at 8:40:42 p.m. CST, release ID `441174009`. The verified draft contained the
Windows full installer, the update manifest with an empty patch list and two
SHA-256 sidecars. [GitHub release](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.9.0).

Fresh anonymous downloads matched all four local files. GitHub release and asset
attestations verified. Candidate and live updater verification each passed nine
Windows cases and eight simulated source/platform cases, including repair,
downgrade refusal and source routing.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.9.0.exe` | 301,168,818 | `bc8c6b898ab1d1ff422b6f8097f6d229129678e6666794a8abf038b95a51ecd2` |
| `FPVS-Studio-Setup-2.9.0.exe.sha256` | 95 | `67c0e23194b56b8c736d773cb2aca3e1e52f79dfd3a261e3df4cf49145fe1b5d` |
| `FPVS-Studio-Update-2.9.0.json` | 107 | `2f4a500680e32c8f715f36b06d04001894e0aa0e904a849b2cd8740106767ccf` |
| `FPVS-Studio-Update-2.9.0.json.sha256` | 97 | `26221ac4575c8d89c7e75b2d5f2b7151006135fb722cd5b7b1317f9497021622` |

Detailed receipts remain in the isolated release checkout under ignored
`build/release-2.9.0-evidence/`, including `precommit-final.log`,
`packaged-smoke-final.json`, `bundle-verification-parity.json`,
`final/verification.json`, `public-verification.json` and
`live-update-verification.json`.
