# Studio 2.4.6 electrode and participant reporting

Status: Active

## Authorized outcome

Build and publish Studio v2.4.6 with the approved electrode and participant
reporting changes. Commit and push the exact source candidate to master before
canonical isolated packaging. Preserve published v2.4.5 and provide a direct
patch from its authenticated installer inventory alongside the full installer.

## Scope and acceptance

- [x] Source and installed metadata agree on 2.4.6; packaging focused checks and
  safe non-Qt repo precommit pass.
- [ ] The exact committed candidate is on master before packaging.
- [ ] The extracted full installer matches the complete target inventory and the
  direct 2.4.5 patch reconstructs that exact target.
- [ ] Frozen source matches the candidate and all native/dependency inputs have
  authenticated baseline custody; bounded non-GUI packaging diagnostics pass.
- [ ] Six draft asset sizes/digests and source tag match before publication.
- [ ] Public release, exact notes, signed assets and updater choices are verified.
- [ ] Final evidence and qualification boundaries are recorded and pushed.

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
