# Attentional Blink pilot mode and release

Status: completed

## Accepted workflow

The user authorized local attentional-blink pilots without EEG hardware, collecting
the standard full demographics and saving T1/T2 accuracy, followed by a release to
GitHub with a full Windows installer and patches for compatible updater baselines.

## Implementation and acceptance

1. Add an app Settings preference, off by default and available for AB only.
   Pilot takes precedence over Test Mode within AB; other categories retain their
   existing launch behavior. Reuse the standard participant form and visit rules.
2. Pilot uses null triggers and skips Sophia/display/graphics checks while retaining
   fullscreen playback, compiled timing and timing records. Keep launch preferences
   outside ProjectFile, RunSpec and SessionPlan.
3. Persist participant demographics and explicit pilot identity with incremental
   burst responses in full and compact exports; show Pilot in the accuracy GUI and
   supply flat demographic columns in Excel/CSV. Preserve old journal loading.
4. Verify runtime persistence, demographics, mode precedence and category isolation;
   add registered GUI coverage and run safe focused plus non-Qt precommit checks.
5. Bump the source version, commit/push master, build from that commit, authenticate
   eligible patch baselines, verify installers/digests and publish the GitHub release.

## Visible smoke path

Open AB > Settings, enable Pilot; launch from Home and Run, fill all demographics,
complete one burst and abort. Inspect T1/T2 Accuracy and Excel for Pilot, PID and
demographics. Turn Pilot off and confirm Test Mode returns; open Oddball and confirm
its ordinary participant/fixation workflow. Settings fits at 700 x 680.

## Verification

- Implementation complete: AB-only app preference, standard demographics, explicit
  pilot records, flat Excel/CSV demographic columns, and GUI identification.
- Non-Qt precommit: 1,590 passed, seven Windows symlink skips; Ruff, compilation,
  mypy (169 source files), repository and documentation audits passed.
- Packaging-focused route: 179 passed. GUI-focused Ruff/compilation passed.
- Version 1.8.0; authenticated published installer inventories from 1.5.1, 1.5.2,
  1.5.3, 1.6.0, 1.6.1 and 1.7.0. No pre-updater patch will be advertised.
- Full installer and six direct patches built from source commit
  `3c1962487121ef8c4eed653deb6d9f2876ad8cdb` on master, using unchanged runtime package
  versions and refreshed app metadata. The independent updater passed its non-GUI
  diagnostic. All 34 changed application modules in the executable match compiled
  committed source.
- Extracted full payload: 7,983 owned files. Every direct patch reconstructs that
  exact target. All 493 native input entries match authenticated published bytes:
  five Python/Tk support files absent from 1.7.0 match 1.5.1/1.5.2; the rest match 1.7.0.
- Full installer: 300,750,293 bytes, SHA-256
  `a36b222fde4984238eb223823afa1df2cdf8b57f08832f400ed475e6e330dbaa`.
- [GitHub release v1.8.0](https://github.com/zcm58/FPVS-Studio-2.0/releases/tag/v1.8.0)
  (ID 389305186) is published as the latest stable release with eight assets. All
  public sizes and SHA-256 digests match the verified local files.
- The production updater fetched the live manifest and validated its digest, selecting
  the correct direct patch for all six authenticated installed-baseline inventories.
  Pre-updater and unregistered installations select the full installer; version 1.8.0
  reports no update.
- The GUI fixture clears the pilot preference between tests so it cannot leak
  between registered GUI cases. This test-only cleanup does not change bundled code.

## Skipped checks

On 2026-09-15 the user explicitly instructed: "skip the visible gui checks, just
publish the release to master". Native pilot GUI tests, packaged Studio GUI smoke
and updater GUI smoke were skipped under that instruction. No GUI pass is claimed.
Physical EEG/display timing and an installed upgrade were not run; artifact
reconstruction and updater selection checks do not establish those outcomes.

## Retained evidence

This local task keeps build, source, native, artifact, GitHub publication, live updater
selection and explicit GUI-check waiver reports under
`C:/Users/zcm58/Documents/Codex/2026-09-15/fix-x20/work/release-1.8.0/`.
The canonical bundle/installers remain in the main checkout's ignored
`build/release-1.8.0/` and `dist/release-1.8.0/` directories. Hash-verified deliverable
copies are in this task's `outputs/FPVS-Studio-1.8.0/` directory.
