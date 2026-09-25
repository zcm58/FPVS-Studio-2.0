# Masking target, mask and catch-slot markers

Status: Completed

## Authorized behavior

Keep each condition's stream-start marker (Masking codes 1–12). Emit the project's
oddball code, normally 55, on every actual target onset; emit mask code 56 on every
target-slot mask onset. On catches emit 57 at the omitted target's scheduled onset,
then 56 when its mask appears. The user explicitly confirmed this catch timing.

Add opt-in modifier-owned event trigger settings, preserving old projects without
these settings. Target onset reuses the existing project oddball-code policy.
Use the existing compiled TriggerEvent and flip-synchronized engine/serial paths;
do not change stimulus timing, question flow, hardware pulse behavior or scoring.

## Work and verification

1. Add persisted marker settings, compatibility guards and collision validation.
2. Compile target/mask/catch-slot events and verify their frame indices for all SOAs,
   ordinary runs and both explicit/legacy catches. Preserve scene schedules exactly.
3. Exercise existing fake-window playback for the emitted sequence without hardware
   or Qt. Verify config/preset/project round trips and legacy behavior.
4. Back up and update the actual Masking project using existing persistence helpers;
   compile all 30 sequences and write a brief participant-independent trigger schema.
5. Run focused routes and repo precommit; report unrun physical display/EEG checks.

Baseline compiler focused route: 288 passed. No Studio release or Library publication
is requested in this turn; updated project files require the supporting Studio code.

## Implementation evidence

- `MaskingSettings.event_triggers` is omitted by default. Enabled modifiers store mask
  and catch-slot codes; target onset reuses the project oddball policy. Project/config/
  preset guards are 1.10.0/1.8.0/1.3.0; RunSpec and SessionPlan stay unchanged.
- Compiler, code-collision and sampled-catch agreement checks retain the exact previous
  scenes, RNG consumption, ordering and task flow. Existing flip callbacks deliver
  the additional generic events without hardware-adapter changes.
- Authoring reassignment, catch creation, aligned task edits and config/preset/bundle
  copies preserve marker settings and the required schema.
- Focused routes: compiler 346 passed; engine 322 passed; project I/O 261 passed and
  two unavailable Windows-symlink skips. New marker coverage totals 84 tests.
- Actual authoring project was backed up, atomically updated and reloaded. Three seeds
  each compile all 30 runs with 2,430 markers: 30 starts, 1,080 targets, 1,200 masks
  and 120 catch slots. Removing trigger lists yields the identical previous SessionPlan.
  No existing asset, response, log or run file was modified.
- The project-local `Masking-trigger-schema.md` describes the codes and timing. The
  ignored `build/masking-event-markers/` directory retains the original project, the
  validated draft, the update helper and verification evidence.
- No Qt GUI, physical display, serial device or EEG recording acceptance was run.
  Released Studio 2.1.0 does not support the new authoring settings.
- Repo precommit: changed-file Ruff/compilation, mypy (206 source files), architecture
  checks and docs hygiene passed. Safe suite: 2,239 passed, 10 Windows-symlink skips,
  two failures in existing Windows filesystem operations. The bundle-import rename
  failed with WinError 5 and passed the targeted recheck. The serialization retry test
  still observed four attempts where it expects three; the save and readback succeeded.
  These production/test paths are unchanged from HEAD. A clean full-suite pass is not
  claimed; the focused project I/O route passed all 261 tests before this broader run.
