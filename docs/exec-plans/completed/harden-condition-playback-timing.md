# Harden Condition Playback Timing

Status: Complete

## Objective

Make condition playback explicitly GPU-ready before stream frame zero, keep the timed
loop minimal, preserve flip-locked oddball triggers, measure both stream boundaries,
score fixation responses from hardware timestamps, and deterministically release each
condition's graphics resources before preparing the next condition.

## Participant Workflow

1. Runtime completes pre-condition tasks and the existing participant Space gate.
2. The engine prepares exactly one condition: resolve contained project assets,
   decode/upload unique render variants, prime timed drawables, synchronize queued GPU
   work, and enforce a conservative graphics-memory readiness check.
3. Warmup and the compiled pre-stream fixation phase run outside the stream clock.
4. Playback consumes the existing `RunSpec` frame and trigger schedules unchanged.
5. A neutral terminal boundary flip ends the final compiled frame, captures final
   responses, and completes timing-QC coverage.
6. Runtime scores the secondary fixation task and exports results after playback; the
   engine releases condition-local textures, buffers, arrays, and references before the
   next condition.

## Non-Negotiable Contracts

- `RunSpec` remains single-condition and frame-based; no project, machine, or PsychoPy
  state enters persisted compiled contracts.
- All PsychoPy/OpenGL access remains lazy and under `src/fpvs_studio/engines/`.
- Oddball and condition markers remain scheduled with `window.callOnFlip(...)` on their
  compiled onset frames. The physical backend write stays synchronous and flip-locked;
  validation/model construction moves outside the callback where possible.
- The terminal boundary is not a compiled stimulus frame, does not increment completed
  frames, and emits no trigger.
- Fixation remains a secondary attention task and cannot alter the FPVS stimulus or
  trigger schedule.
- Project image paths remain contained, project-relative inputs resolved against the
  active project root. No runtime image assets are written.
- No timed disk streaming, silent graphics fallback, automatic quality reduction, or
  background preparation of the next condition is allowed.

## Implementation Boundaries

### Engine

- Introduce a condition-local preparation/readiness owner with idempotent cleanup and
  partial-build rollback.
- Prime image/text and fixation drawables, then perform one explicit pre-onset graphics
  completion barrier.
- Add renderer and graphics-memory diagnostics without leaking PsychoPy/OpenGL types
  into runtime/core contracts.
- Correct the PsychoPy `_pixbuffID` cleanup mismatch and surface cleanup failures.
- Replace per-frame validated-model construction with raw primitive collection and
  post-playback materialization.
- Add the terminal neutral flip and complete first/final interval accounting.

### Runtime and core-owned execution results

- Preserve runtime ownership of scoring and exports.
- Score fixation RT from hardware timestamps against actual target-onset flip times,
  not the frame in which a buffered key was retrieved.
- Carry neutral preparation/memory/timing diagnostics only where they are useful for
  runtime policy and durable QC.
- Keep routine project preflight path containment intact; full decode/upload remains a
  condition-preparation operation.

### Trigger backend

- Prevalidate marker payloads before playback.
- Keep callback work to clock read, prepared backend write, and lightweight raw logging.
- Preserve explicit failure propagation and existing BioSemi one-byte semantics.

## Memory Policy

- Estimate every unique prepared render variant from decoded source dimensions and
  representation, including mipmaps, retained arrays, and safety overhead.
- Reject known software renderers for timing-valid production playback.
- On Windows, use available DXGI budget information when callable; otherwise return an
  explicit unverified result rather than silently claiming residency.
- Preserve conservative headroom and treat budget/readiness failure as a pre-onset
  launch error. Test/null presentation paths remain usable without pretending to be
  hardware-qualified.
- Measure cleanup behavior and close/recreate the graphics context only as an explicit
  recovery path if deterministic resource deletion fails.

## Verification

- Focused engine coverage for readiness, explicit synchronization, terminal offset,
  final response capture, raw interval materialization, fixation priming, trigger
  callback order, cleanup success/failure, and no reuse across conditions.
- Runtime scoring coverage for hardware-timestamp RT and dropped-frame-independent
  target matching.
- Memory-policy unit coverage with injected adapter/budget observations; no live-GPU
  dependency in normal unit tests.
- Existing continuous and 50%-blank compiler schedules must remain byte-for-byte
  unchanged.
- Focused `engine`, `runtime`, `triggers`, `core`, and `docs` verification, followed by
  `repo` precommit verification.
- Real fullscreen, high-refresh, trigger-hardware, DXGI-budget, and physical display
  checks remain documented visible/manual verification on the intended lab rig.

## Assumptions

- The existing participant Space-to-stream delay is not an experimental timing
  variable; preparation may remain after the gate as long as frame zero cannot begin
  before readiness succeeds.
- Missing physical photodiode equipment limits claims to software flip alignment and
  recorded frame timing, not verified photon onset.
- Timing-valid runs should be flagged when a refresh is missed; playback continues to
  a safe terminal boundary so complete QC and trigger artifacts can be exported.

## Outcome

- Each condition now owns a fresh, condition-local set of unique image/text render
  variants and two immutable fixation variants. All are decoded, created, primed, and
  GPU-synchronized before warmup or stream frame zero.
- Cleanup explicitly releases texture, mask, pixel-buffer, and legacy display-list
  resources, waits for deletion completion, clears strong references, and invalidates
  the graphics session if cleanup or playback leaves GPU state uncertain.
- Production launch now applies conservative pre-upload and post-upload graphics
  readiness gates using the active renderer, DXGI budgets, system-memory headroom, and
  representation-aware memory estimates. Test mode remains explicitly non-qualified.
- The timed loop uses prebound draw plans and primitive collectors, with garbage
  collection paused. Disk access, texture creation, Pydantic construction, fixation
  property mutation, and schedule lookup are outside the loop.
- A terminal neutral flip now closes the final continuous-image or 50%-blank display
  interval. Oddball trigger writes remain scheduled on the exact compiled onset flip.
- Fixation RT uses actual flip/key timestamps only for PTB or ioHub. Other or incomplete
  timestamp paths fall back atomically to frame scoring, with the source exported.
- Condition and session exports retain graphics-readiness, cache-cleanup, keyboard, RT
  source, and timing-QC provenance, including compact history files.

## Verification Results

- Verification configuration: passed for all 12 registered scopes.
- Focused engine: 148 passed.
- Focused runtime: 154 passed.
- Focused triggers: 23 passed.
- Focused core: 94 passed, 1 skipped because Windows symlink privileges were absent.
- Focused project I/O: 48 passed.
- Focused documentation: 8 passed; hygiene checks passed.
- Focused GUI: Ruff and compilation passed; local Qt execution was intentionally not
  run under the repository policy.
- Repository precommit: Ruff, compilation, mypy (130 source files), repository audits,
  documentation hygiene, and 587 unit tests passed; the same symlink privilege test was
  skipped.
- Residual manual verification: run a short fullscreen session on the intended display
  and serial-trigger hardware. Without a photodiode, software flip alignment cannot
  prove physical photon onset.
