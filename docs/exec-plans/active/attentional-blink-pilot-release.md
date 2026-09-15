# Attentional Blink pilot mode and release

Status: active

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
- Native GUI smoke, installer construction, artifact verification and publication
  remain pending. No physical EEG/display timing check has been run.
