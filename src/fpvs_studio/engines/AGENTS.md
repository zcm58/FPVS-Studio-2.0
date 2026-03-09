# AGENTS.md

## Scope of this directory

`src/fpvs_studio/engines/` defines the presentation-engine abstraction and the v1 PsychoPy-backed implementation boundary.

This is the only place in the repo where PsychoPy should appear.

## Current phase expectations

For this phase, the engine layer should provide a narrow but real renderer. The
important part is still the interface design, but the PsychoPy path now needs to
play compiled runs end to end.

## Requirements

- Define a stable base protocol/ABC for presentation engines.
- Keep input/output types engine-neutral (`RunSpec`, execution-result models, validation models).
- Keep engines consuming one `RunSpec` at a time; runtime owns `SessionPlan` iteration.
- Add an engine registry/factory.
- Add a real but minimal `PsychoPyEngine`.
- Render runtime-owned instruction, inter-block break, and completion screens without moving session sequencing into the engine.
- Render runtime-owned end-of-condition fixation feedback screens without moving scoring/session decisions into the engine.
- Keep the public surface small and swappable.

## Hard restrictions

- Do not let PsychoPy-specific types leak into core models or runtime exports.
- Do not import PsychoPy outside this directory.
- Do not import PsychoPy eagerly at module import time; keep it lazy inside the engine implementation.
- Do not couple project JSON structure to PsychoPy internals.

## Likely interface shape

The engine interface should be able to support, at minimum:

- display probing
- display validation
- session open/close
- transition/completion text screens
- `run_condition(RunSpec, ...)`
- abort

It is acceptable for advanced trigger hardware integration or future engine
features to remain deferred, as long as the interface, typing, and dependency
boundaries stay correct.
