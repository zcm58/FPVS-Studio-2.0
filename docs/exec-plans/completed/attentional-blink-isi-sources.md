# Attentional-blink ISI sources and designer spacing

Status: Completed (2026-09-09)

Allow an image or the configured blank background during the existing timed ISI.
Give image ISIs their own imported source, alongside Base, T1 and T2. Preserve old
projects' base-image separator through explicit legacy reference migration. Keep
T1 + ISI + T2 inside one normal slot, with existing fixation and target markers.

1. Extend editable/portable/compiled contracts and source lifecycle; verify legacy
   loading, independent sources, blank frame scheduling and asset round trips.
2. Add the designer choice and source card; remove the surrounding Design frame,
   improve spacing, and increase Setup's default height to 820 pixels.
3. Verify focused non-Qt and approved visible GUI checks, fake-engine playback,
   documentation and precommit. No real experiments or hardware triggers are run.

Implemented four independent source references, explicit image/blank settings and
legacy migration, configuration/bundle preservation, source lifecycle handling,
independent ISI geometry, blank frame events and stimulus-free engine drawing.
The designer exposes the choice and optional folder, previews blank with the actual
configured background, removes the enclosing frame and enlarges the timing diagram.
Setup grows from its untouched Home default to 1120x820; manually chosen window
sizes are preserved. The embedded editor is checked at 1000x530, standalone at
1040x760, and the actual Setup window at 1120x820 in both themes.

Verification:
- Safe unit suite: 1203 passed, 5 Windows symlink skips. Includes image/blank
  configuration and portable-bundle round trips, independent source geometry,
  exact frame counts, target markers and fake-engine blank presentation.
- Final designer/Design Qt run: 67 passed in an approved visible environment.
- Updated window-size and surrounding-step layout checks: 2 passed separately.
- Light/dark full-window captures reviewed: build/isi-design-light.png and
  build/isi-design-dark.png. Folder dialogs and runtime launch are stubbed in tests.
- Ruff, focused GUI compilation, diff checks, docs hygiene and harness audits pass.
- Precommit stops at the pre-existing controller.py:373 mypy return-type error;
  the remaining safe suite and audits passed separately.
- No real PsychoPy display session, photodiode check or hardware trigger run was made.
