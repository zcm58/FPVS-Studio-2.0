# Architecture

This file is the compact map for agent work. Keep detailed design decisions in `docs/`
and update this map when package boundaries or source-of-truth contracts move.

## Application Shape

FPVS Studio is a Windows-focused PySide6 desktop authoring app. The GUI creates and edits
project models, compiles them into neutral execution contracts, and launches runtime flows.
Timing-critical presentation is isolated behind runtime and engine interfaces; only engine
code may lazily import PsychoPy.

## Package Map

- `src/fpvs_studio/app/`: application entry points and startup wiring.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding, and
  design-system helpers.
- `src/fpvs_studio/core/`: editable project models, validation, compilation, run/session
  contracts, project persistence, and engine-neutral domain logic.
- `src/fpvs_studio/preprocessing/`: source image import, inspection, derived assets, and
  manifests. This layer must stay independent of GUI runtime and PsychoPy.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session execution, participant
  history, and runtime flow over compiled contracts.
- `src/fpvs_studio/engines/`: presentation engine interface and PsychoPy implementation.
- `tests/`: unit, integration, and pytest-qt GUI coverage.

## Contract Flow

`ProjectFile` models compile into single-condition `RunSpec` entries. Session settings and
ordered conditions compile into a `SessionPlan` that owns realized fixation target-count
selection. Runtime consumes `RunSpec` or `SessionPlan` and produces core-owned execution
results. Exporters serialize those results without moving contracts into engine code.

## Dependency Rules

- GUI may use core services and runtime launch APIs, but must not own compilation,
  fixation scoring, or session flow.
- Runtime may consume compiled contracts and coordinate flow, but must not depend on
  PySide6 widget code.
- Engines render presentation screens and may use PsychoPy lazily inside engine modules.
- Core and preprocessing must remain engine-neutral.

## Deeper Docs

- Product and v1 scope: `docs/FPVS_Studio_v1_Architecture_Spec.md`
- GUI behavior and smoke-test guidance: `docs/GUI_WORKFLOW.md`
- Engine boundary: `docs/ENGINE_INTERFACE.md`
- Run contract: `docs/RUNSPEC.md`
- Session contract: `docs/SESSION_PLAN.md`
- Runtime/export flow: `docs/RUNTIME_EXECUTION.md`
