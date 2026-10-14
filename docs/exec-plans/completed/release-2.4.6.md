# Studio 2.4.6 electrode and participant reporting

Status: Completed

## Authorized outcome

Build and publish Studio v2.4.6 with the approved electrode and participant
reporting changes. Commit and push the exact source candidate to master before
canonical isolated packaging. Preserve published v2.4.5 and provide a direct
patch from its authenticated installer inventory alongside the full installer.

## Scope and acceptance

- [x] Source and installed metadata agree on 2.4.6; packaging focused checks and
  safe non-Qt repo precommit pass.
- [x] The exact committed candidate is on master before packaging.
- [x] The extracted full installer matches the complete target inventory and the
  direct 2.4.5 patch reconstructs that exact target.
- [x] Frozen source matches the candidate and all native/dependency inputs have
  authenticated baseline custody; bounded non-GUI packaging diagnostics pass.
- [x] Six draft asset sizes/digests and source tag match before publication.
- [x] Public release, exact notes, signed assets and updater choices are verified.
- [x] Final evidence and qualification boundaries are recorded and pushed.

## Release content

New completed research sessions share launch-frozen age, sex, handedness,
colorblind status and nullable reviewed electrode lists with approved OpenFPVS
projects. Random project/study subject UUIDs distinguish participants from repeat
visits without uploading original participant numbers. Completed Toolbox handoffs
carry the same visit electrode evidence. Saved opt-outs, legacy outbox bytes,
offline retries and no historical backfill remain unchanged. Metadata-only sessions
can contribute when fixation statistics are unavailable.

OpenFPVS already displays these summaries and protected electrode downloads;
its pages load when opened/reloaded without polling. Website behavior requires
no desktop polling. Compatible Toolbox source is tested but not released by this task.

## Boundaries

Run the existing safe source/packaging checks and canonical scripts without
dependency upgrades. Do not operate a Qt window, acquire EEG, measure physical
timing, install over the working application, upload research data, publish
Toolbox or redeploy OpenFPVS. Visible GUI, installed upgrades and real hardware
remain manual qualification. Earlier synthetic/live acceptance does not establish
those checks. Release notes use concise change bullets; audit evidence belongs here.

## Source verification

All 181 packaging-focused tests pass, and pip check reports no broken requirements.
The fresh safe repo precommit gate passed 3,043 tests and 20 subtests, with 11
existing Windows symlink-permission skips, in 1,273.31 seconds. Ruff, compilation,
mypy, harness and documentation audits pass. The 1,500-session archival test passed
in this run. Qt and physical hardware were not operated.

The signed published v2.4.5 full installer and all 7,987 owned-file hashes are
authenticated. Its inventory digest is
`da0a84aaead53b6ae24ee01d0f72a21afc8979491dcfe427fc15452b34b5abf5`.
Bundled dependency versions match the current environment; the editable metadata
refresh used no dependency upgrades. Canonical output and evidence are isolated
under `release-2.4.6` and `release-2.4.6-evidence`.

## Published release and artifact acceptance

Source candidate `dc6936d7cdf9c88f13a37a688e6c9f66ee9af8c0` was committed,
fast-forwarded and pushed to master before the canonical isolated build. The
annotated `v2.4.6` tag resolves to that exact commit. Immutable release `412825202`
is published as latest stable at
[FPVS Studio 2.4.6](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v2.4.6).

The extracted full installer matches all 7,987 target owned-file hashes. The
direct 2.4.5 patch reconstructs that exact target with 11 changed/added files,
7,976 retained files and eight removals. Target inventory SHA-256 is
`05075c4977e36538aa03704b36ae731438bf8627ed54c940996378a0772f30fb`.
All 235 Studio source modules and 23 updater source modules/entry match the
candidate in their frozen archives. The updater diagnostic confirms version
2.4.6, protocol 1, frozen execution and no GUI imports.

All native payload bytes, 491 Studio native analysis inputs, 69 updater native
inputs and bundled dependency versions match the authenticated v2.4.5 baseline.
Non-app dependency paths/bytes are unchanged except the regenerated standard-library
ZIP, whose 151 modules retain identical headers and normalized compiled code.
No historical optional inclusion exception or dependency upgrade was needed.

The draft source identity, exact UTF-8 change bullets and all six uploaded asset
sizes/digests were checked before publication. Public metadata, source tag, notes,
all six asset sizes/digests and four downloaded sidecars pass. Signed release and
asset attestations pass. Eleven candidate and public updater cases pass:
authenticated 2.4.5 selects the patch; missing inventory, forced full, repair and
older versions select full; current 2.4.6 reports no update, while explicit repair
selects full. Evidence is retained in ignored `build/release-2.4.6-evidence/`.

## Published assets

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `FPVS-Studio-Setup-2.4.6.exe` | 300721672 | `f3bea0e8bf2fe63cbab258c000a081e14e959c5cfe291f08710e211ee0c4949b` |
| `FPVS-Studio-Patch-2.4.5-to-2.4.6.exe` | 72190859 | `a10852df67e8bbce8e943c224106f73347893110e7a087f251830acdb143fdb2` |
| `FPVS-Studio-Update-2.4.6.json` | 435 | `78d3d780fb29c3d35e424e1f73724f783037396ecbdda92548aae8bab3062923` |
| `FPVS-Studio-Setup-2.4.6.exe.sha256` | 95 | `7f70f86fec7d2ed14fc4687f6263733acf4d7d26e5673613da56134b451a4919` |
| `FPVS-Studio-Patch-2.4.5-to-2.4.6.exe.sha256` | 104 | `289584c93d16c026b36d9a2fac396cbe895967652c72138abf45e438f843989c` |
| `FPVS-Studio-Update-2.4.6.json.sha256` | 97 | `bc484f0726b4c50b6d551b8392c8a5abc06d1dadbe63e71e1d8ad8e9f3e0ecbd` |

## Remaining qualification

Visible Qt/desktop GUI review, clean-machine installation, an actual installed
upgrade and real EEG/Recorder/BDF+/physical display timing were not run. Compatible
Toolbox source remains on its development branch pending Toolbox v3.0 release and
hardware qualification. The already deployed OpenFPVS overview and electrode
downloads remain live; no backend deployment, migration or reporting upload was
repeated for this Studio release.
