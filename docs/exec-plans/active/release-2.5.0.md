# Studio 2.5.0 release

Status: Active

## Authorized outcome

Publish the Brain Products / BrainVision trigger setup and computer default EEG
hardware workflow, after approved visible GUI checks. Preserve and merge the other
PC's mouse-response fixes and BrainVision labels. Release notes remain brief bullets.

## Acceptance

1. Reconcile both checkouts, then exercise onboarding, recording setup, manual and
   detected COM ports, pulse validation, inheritance and Settings in a visible,
   isolated Qt profile. Repair concrete failures and rerun affected checks.
2. Run packaging focused and repository precommit verification. Record passes and
   skips separately from physical EEG/display validation, which needs lab hardware.
3. Commit version 2.5.0 on master, refresh editable metadata without dependency
   upgrades, and build a full installer plus a direct authenticated 2.4.8 patch.
4. Verify extracted payload hashes, exact patch reconstruction, native dependency
   custody, packaged startup, updater diagnostics and selection. Publish and verify
   remote asset hashes and updater metadata.

## Progress

- Local implementation preserved in f4825d0; remote commits 43cfec7 and 0cd0bc7
  merged in 6b67d09. The documentation merge keeps the updated BrainVision label
  and the new discovery/amplifier/rate fields.
- Visible Qt checks started with the Windows platform and workspace test settings.
  Final combined run passed all 303 selected tests. Screenshots cover the picker
  at 640x300, BrainVision setup at 700x640, Settings at 700x560 and Welcome at
  760x520, including long labels, at device pixel ratio 1.0. Tests also exercise
  both theme palettes. Evidence is under `build/release-2.5.0-evidence/`.
- Visible testing repaired compact Welcome spacing, aligned the onboarding
  BrainVision label, and updated three tests to existing asynchronous behavior.
  A transient Windows clipboard lock passed unchanged on retry and in the final run.
- Packaging focused: 181 passed. GUI safe focused: 83 passed. Documentation: ten
  passed. Ruff, compilation and mypy for all 242 source files pass. Full non-Qt
  precommit is running while the committed candidate is packaged; publication
  waits for its result and all artifact checks.
- Published 2.4.8 baseline installer, signed release/asset attestations and all
  7,989 owned file hashes verified. Dependency versions and reviewed native source
  bytes match baseline. Build-only `editables==0.5` was added to refresh app metadata
  with `--no-deps --no-build-isolation`; `pip check` passes.

## Boundaries

No physical amplifier/TriggerBox, EEG sampling or display timing qualification is
claimed. Installer lifecycle checks use isolated disposable paths, if exercised.
The user's installed app, project roots and preferences remain preserved.
