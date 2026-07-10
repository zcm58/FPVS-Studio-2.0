# AGENTS.md

## Repository Purpose

FPVS Studio is a Windows-focused PySide6 desktop authoring application for FPVS
experiments. PsychoPy presentation stays isolated behind runtime and engine boundaries.

## Efficient Working Route

- Fast path before broad reads: check `git status --short --branch`, read this file,
  then use `docs/agent/agent-index.md` to choose one task scope and its first reads.
- Treat `ARCHITECTURE.md` as the compact package and dependency map. Do not read every
  architecture or workflow document by default.
- Run the selected focused verification before broad inspection. Read only the files
  implicated by the request, search results, or failures.
- Read every nested `AGENTS.md` that governs a path before editing that path.
- For non-trivial work, read the active execution plan first. Do not treat completed
  plans or archived references as current behavior.
- Prefer the smallest behavior-preserving change. Preserve unrelated user changes,
  existing formats, processing order, and workflows.
- Do not read `output/`, environments, caches, builds, or archived references unless
  the task explicitly requires them. Treat untracked output as user-owned.

## Canonical Ownership

- Editable project models: `src/fpvs_studio/core/models.py`
- Single-condition execution contract: `src/fpvs_studio/core/run_spec.py`
- Multi-condition session contract: `src/fpvs_studio/core/session_plan.py`
- Execution results and export contracts: `src/fpvs_studio/core/execution.py`
- PySide6 application surface: `src/fpvs_studio/gui/`
- Image intake, normalization, derived assets, and manifests:
  `src/fpvs_studio/preprocessing/`
- Runtime orchestration, preflight, participant flow, and exports:
  `src/fpvs_studio/runtime/`
- PsychoPy presentation: `src/fpvs_studio/engines/`
- Hardware adapters: `src/fpvs_studio/triggers/`

Use the public owner instead of creating a second implementation. Detailed layer
contracts live in the nearest package `AGENTS.md` and the focused docs linked from
`docs/agent/agent-index.md`.

## Non-Negotiable Boundaries

- The compiler transforms editable project state into `RunSpec`; runtime and engines
  consume compiled contracts, not `ProjectFile`.
- Session compilation produces `SessionPlan`; runtime owns ordered session flow while
  engines render presentation screens and one `RunSpec` at a time.
- Runtime produces core-owned execution results. Exporters serialize those contracts;
  engine code must not own export formats.
- Keep runtime-only launch and machine settings outside `RunSpec` and `SessionPlan`.
- Only `src/fpvs_studio/engines/` may import PsychoPy, and imports must remain lazy.
- Core and preprocessing must remain independent of PySide6, PsychoPy, and hardware.
- Use PySide6 only for the GUI. Do not introduce CustomTkinter or fallback non-GUI
  application modes. Import `QAction` from `PySide6.QtGui`.
- Do not block the UI thread. Use Qt workers and signals; workers must not touch widgets.
- Use structured logging instead of `print` in production code.
- Project I/O must use the active project root and preserve persisted/export formats.
  App-level templates belong under `<FPVS Studio Root>/.fpvs-studio/templates/`.
- Keep `RunSpec` single-condition and represent compiled timing in frames. Fixation
  behavior must not alter FPVS base/oddball scheduling.
- Preserve current session randomization, compile-time fixation realization, runtime
  scoring, and participant feedback ownership unless an approved plan changes them.
- Do not add silent trigger, display, dependency, or runtime fallbacks.
- Treat `Main_App/Legacy_App/**` and `Tools/SourceLocalization/**` as protected legacy
  boundaries if present; edit only when explicitly requested.

## GUI Acceptance

- Use `src/fpvs_studio/gui/components.py` before adding local visual primitives or
  one-off styles.
- No clipping is the default. Every changed surface must fit at its documented
  minimum/default size with realistic longest content and all relevant states.
- The Setup Wizard must fit all six steps at `1120x720` without required scrolling,
  child-widget clipping, or unintended truncation.
- Intentional elision needs an accessible full-value path and explicit coverage.
- Add or update registered pytest-qt coverage for changed GUI behavior, but do not run
  Qt tests locally by default. Local GUI verification uses non-Qt checks plus a
  documented visible/manual smoke path. Run Qt locally only in a user-approved safe
  visible environment; offscreen Qt execution is CI-only.

## Skills and Plans

Repo-local skills in `.agents/skills/` cover PySide6 cleanup, pytest-qt coverage,
project paths, legacy boundaries, and PsychoPy migration. Use
`docs/agent/agent-index.md` to select them. Global web, React, mobile, and deployment
skills are not architecture precedent for this desktop application.

Feature-sized or cross-layer work belongs in `docs/exec-plans/`. Planned, active, and
completed states must match their directories. Preserve and update the current active
plan when working within its scope; archive completed work so it is not mistaken for
active guidance.

## Standard Verification

The verification driver selects `.venv3.10`, then `.venv`, then the current compatible
Python interpreter. Use the narrowest relevant scope from `docs/agent/agent-index.md`:

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

`focused` runs scope checks plus changed-file Ruff/compilation. `precommit` adds repo
audits, mypy, and the safe non-Qt suite. `full-ci` is the explicit CI tier and includes
registered Qt tests. Add `-List` to a routed command to inspect its steps and use
`./scripts/verify.ps1 -CheckConfig` after changing the harness.

## Documentation Freshness

Update `ARCHITECTURE.md`, `docs/agent/agent-index.md`, and the nearest scoped document
when ownership, boundaries, supported workflows, or verification routes change. Keep
detailed contracts in one canonical document and link to them instead of duplicating
them in always-read guidance.

## Done Means

- The requested behavior is complete and unrelated contracts remain intact.
- Focused verification passes; precommit runs when shared behavior changed.
- Skipped platform, GUI, or external checks are reported with residual risk.
- Generated artifacts are cleaned without deleting user data or retained output.
- Agent and architecture docs reflect changed ownership or workflows.
