# Studio 2.4.5 Toolbox handoff and shared reporting

Status: Active

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
- [ ] The exact committed candidate is on master before canonical isolated builds.
- [ ] Full installer extraction matches the target ownership inventory; the direct
  2.4.4 patch reconstructs that exact target.
- [ ] Frozen source matches the candidate and native dependencies have authenticated
  baseline custody; packaged non-GUI smoke passes.
- [ ] Draft asset sizes and SHA-256 values match audited local files before publishing.
- [ ] Public version, source tag, notes, assets and updater choices are verified.
- [ ] Final release evidence and qualification boundaries are recorded and pushed.

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
