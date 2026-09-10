# AGENTS.md

## Source Tree Scope

Code under `src/` is the production application. Keep this file to stable v1
invariants; use `ARCHITECTURE.md` and the task recipes there for the current
package map.

## Stable v1 Invariants

- The only built-in protocol template is `fpvs_6hz_every5_v1`.
- Experiment category is a locked project choice: FPVS Oddball Paradigm or Attentional-Blink;
  Standard FPVS is a disabled Coming soon placeholder. Valid projects cannot mix categories.
- FPVS Oddball Paradigm defaults are 6.0 Hz and oddball every 5th stimulus (1.2 Hz).
  Attentional-Blink uses 10 Hz digit/letter streams with 100/300/500 ms SOAs.
  See `docs/EXPERIMENT_CATEGORIES.md` for defaults and migration.
- Oddball image conditions support `continuous`, `blank_50`, and `sinusoidal`.
  The visual designer maps oddball cycles to existing protocol settings. AB image
  pairs are retired: no template, ISI editor, compilation or playback is available.
- Project-facing schemas must remain engine-neutral.
- Generated stimulus variants belong under the active project folder in
  `stimuli/generated-variants/...`.
- App-level condition-template profiles belong under the configured FPVS Studio
  root in `.fpvs-studio/templates/`, outside the top-level experiment folder list.
- Persist project-facing paths as project-relative POSIX-style strings in JSON.
- Supported source image formats are `.jpg`, `.jpeg`, and `.png`.
- Launchable image stimulus sets must each resolve to a known, uniform resolution.
  Uniform rectangles are supported, and a condition's base and oddball sets may use
  different source resolutions because playback size is controlled by compiled role
  geometry.
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
