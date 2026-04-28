# AGENTS.md

## Source Tree Scope

Code under `src/` is the production application. Keep this file to stable v1
invariants; use `ARCHITECTURE.md` and the task recipes there for the current
package map.

## Stable v1 Invariants

- The only built-in protocol template is `fpvs_6hz_every5_v1`.
- V1 keeps base rate fixed at 6.0 Hz, oddball every 5th image, and oddball
  frequency at 1.2 Hz.
- Users choose `continuous` or `blank_50` duty cycle; do not expose editable
  base/oddball frequencies in v1 UI.
- Project-facing schemas must remain engine-neutral.
- Derived stimuli belong under the active project folder in `stimuli/derived/...`.
- Persist project-facing paths as project-relative POSIX-style strings in JSON.
- Supported source image formats are `.jpg`, `.jpeg`, and `.png`.
- All images inside a stimulus set must share resolution; base and oddball sets
  in a condition must also match.
- The fixation task is the only behavioral task in v1 and must not alter FPVS
  base/oddball scheduling.

## Layer Guardrails

- Core models, validation, compilation, `RunSpec`, `SessionPlan`, and
  execution-result contracts stay engine-neutral.
- GUI code uses backend services and document/controller bindings; do not move
  compilation, fixation scoring, preprocessing, or runtime session flow into
  widgets.
- Runtime consumes compiled contracts and owns session flow, launch settings,
  participant history, preflight, and execution exports.
- Only `src/fpvs_studio/engines/` may import PsychoPy, and those imports must
  stay lazy inside engine implementations.
- Preprocessing owns image inspection, import, derived assets, and manifests;
  it must not depend on GUI, runtime, or PsychoPy.
- Long GUI work belongs in Qt worker patterns such as `QThread`/`QRunnable`, not
  direct UI-thread loops.

## Change Discipline

- Preserve existing JSON, `RunSpec`, `SessionPlan`, and export formats unless a
  user explicitly asks to change a contract.
- Prefer small direct edits over speculative abstractions.
- If behavior is ambiguous, preserve the existing contract and surface the
  ambiguity instead of adding hidden fallback behavior.
