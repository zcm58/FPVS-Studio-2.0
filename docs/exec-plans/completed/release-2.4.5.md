# Studio 2.4.5 Toolbox handoff and shared reporting

Status: Completed

Date: 2026-10-13

## Authorized outcome

Build and publish FPVS Studio v2.4.5 with the approved Studio, Toolbox and OpenFPVS
integration changes. Commit and push the exact source candidate to master, build a
full Windows installer and a direct patch from the authenticated v2.4.4 baseline,
then verify immutable release assets and updater selection.

## Scope and acceptance

- [x] Review the recording-profile declarations, completed-session handoff and
  default-on enrollment changes; preserve saved off choices and existing formats.
- [x] Source and installed metadata agree on 2.4.5; packaging focused checks and
  safe repo precommit pass.
- [x] The exact committed candidate is on master before canonical isolated builds.
- [x] Full installer extraction matches the target ownership inventory; the direct
  2.4.4 patch reconstructs that exact target.
- [x] Frozen source matches the candidate and native dependencies have authenticated
  baseline custody; packaged non-GUI smoke passes.
- [x] Draft asset sizes and SHA-256 values match audited local files before publishing.
- [x] Public version, source tag, notes, assets and updater choices are verified.
- [x] Final release evidence and qualification boundaries are recorded and pushed.

## Boundaries

The user requested this release after being informed that visible workflow and real
EEG qualification remain manual. This task runs safe non-Qt source checks and bounded
packaged diagnostics; it does not run a visible Qt session, acquire EEG, measure
physical display timing, install over the working application, upload research data,
publish Toolbox, or redeploy OpenFPVS. Synthetic handoff and live dummy-service
acceptance are recorded in the active integration plan and do not establish physical
hardware qualification. Release notes describe the desktop changes and retain that
distinction; verification evidence belongs here and in ignored build output.

Use the existing canonical build scripts with isolated versioned output and the
unchanged, authenticated dependency environment. Preserve all earlier release assets.

## Progress

Release preparation started from codex/studio-toolbox-integration, based on the
published v2.4.4 source. The approved integration changes were previously verified
through synthetic Studio to Toolbox processing and the live OpenFPVS dummy study.

Source and installed metadata now agree on 2.4.5, all 181 packaging-focused tests
pass, and pip check reports no broken requirements. Independent release review
found and fixed three handoff edge cases: malformed optional sharing settings no
longer block a local launch, a same-protocol stale Library enrollment cannot replace
the installed experiment identity, and a completed config is written only after
compact finalization cleanup succeeds. Focused regressions retain invalid metadata
for review and keep export/protocol-hash failures visible. The initial broad check
was stopped after these findings; the final candidate is being checked afresh.

The compatible Toolbox hardware-aware importer is currently on its integration
development branch; this release does not publish Toolbox. Public notes state that
dependency explicitly.

The final safe repo precommit gate passes: 2,980 tests and 20 subtests passed, with
11 existing Windows symlink-permission skips, in 700.23 seconds. Source Ruff,
compilation, mypy, harness GC and documentation checks pass. Final focused checks
also pass: 96 sharing/coordinator tests and 61 recording tests (one symlink skip).
The authenticated public v2.4.4 full installer was extracted without execution;
all 7,062 owned files and signed release/installer attestations pass. Its 23 bundled
dependency metadata records match the current environment. Existing source paths
also match all 486 Studio dependency binary hashes and 69 updater binary hashes.

## Published release and artifact acceptance

Source candidate `ddbe3805143ef19630efb2402b4b0066cbbdba64` was fast-forwarded
and pushed to master before the canonical isolated `release-2.4.5` build. The
annotated `v2.4.5` tag resolves to that exact source, checked before draft creation,
before publication, and against the public GitHub tag afterward. Immutable release
`412209252` is published as latest stable at
[FPVS Studio 2.4.5](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.5).

The full installer matches all 7,987 target owned-file hashes. The direct
2.4.4-to-2.4.5 patch reconstructs that exact target: 957 changed/added files,
7,030 retained files and 12 removals. Target inventory SHA-256 is
`da0a84aaead53b6ae24ee01d0f72a21afc8979491dcfe427fc15452b34b5abf5`.
All 235 Studio source modules and 23 updater source modules/entry match the candidate
in their frozen archives. The updater's bounded packaging diagnostic confirms
version 2.4.5, protocol 1, frozen execution and no GUI imports.

All 482 existing native libraries remain identical to v2.4.4. This build collector
also includes five optional Python/Tk binaries, 922 Tcl/Tk data files and two empty
installation markers that v2.4.4 omitted. Every one of those 929 added non-app paths
matches the freshly authenticated, signed v2.4.3 installer and its inventory.
The audit admits only that exact path/hash map, bound to this target inventory.
All 491 Studio dependency binary analysis inputs and 69 updater native inputs have
authenticated custody. The 23 bundled dependency versions match v2.4.4.
Eight dependency RECORD changes describe installation receipts/markers; four empty
markers were removed. The regenerated standard-library ZIP retains identical code
and headers across all 151 modules. All other existing non-app dependency bytes
remain unchanged. This is reviewed collection variation, not a dependency upgrade.

The first artifact audit rejected an existing file with mixed LF/CRLF working-tree
line endings; every non-line-ending byte matched its committed source. The corrected
audit normalizes only CRLF and still compares all frozen compiled code to the exact
candidate. Extraction reuse rehashed every payload and repeated all final checks.

Draft notes had a Windows line-ending difference caught before publication. The
same draft was retained, its notes normalized to exact UTF-8 bytes and all six
uploaded assets/source identity rechecked before publication. No artifact was
reuploaded or modified after audit. Public metadata, source tag, exact notes, all
six asset sizes/digests and four downloadable sidecar contents pass. The signed
release and all six signed asset attestations pass.

Ten updater cases pass both against candidate assets and the public release:
authenticated 2.4.4 selects the direct patch; missing inventory, forced full and
repair select full; 2.4.3, 2.4.2, 2.4.1 and 1.4.0 select full; current 2.4.5 has no
update, while explicit current-version repair selects full. All tests and artifact
records are retained in ignored `build/release-2.4.5-evidence/`.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.5.exe` | 300726513 | `4c102d4e892998186bba77f11fb2eab25ee900f4fb80594bdf26c18285f9d55e` |
| `FPVS-Studio-Patch-2.4.4-to-2.4.5.exe` | 74187393 | `2995f46974ae4b282f96e3f72156159f0a97bcc900c9b5ea631e623c2a6edc8b` |
| `FPVS-Studio-Update-2.4.5.json` | 435 | `84025706f813c8a8d2b374962d12997d6f1c9b2bd0eb26b2831c67611a59c33e` |
| `FPVS-Studio-Setup-2.4.5.exe.sha256` | 95 | `a07314084507ac2cdeecd62de8083f34dd012589bcc581a8ad5663dc996302d8` |
| `FPVS-Studio-Patch-2.4.4-to-2.4.5.exe.sha256` | 104 | `09a40f4663fc3fc33d2d6756fd1c77bebd06625677cb234c819649f77444ccce` |
| `FPVS-Studio-Update-2.4.5.json.sha256` | 97 | `af0607f552617a1d8f341a89924c39d5368986b7e1c6c78a7ba30d5354b6c00e` |

## Remaining qualification

Visible Qt/desktop GUI review, clean-machine installation, actual installed upgrade,
real EEG/Recorder/BDF+ operation and physical display/headset timing were not run.
They remain manual qualification in the active integration and Unicorn plans.
New hardware-aware import requires the compatible Toolbox development build or
forthcoming release; publishing Studio does not release Toolbox. The OpenFPVS
backend was already deployed and live-tested with dummy data in the integration
task; no deployment, migration or reporting upload was repeated for this release.
