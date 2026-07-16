# Architecture

This is FPVS Studio's compact repository map. Detailed workflow and method contracts
belong in the focused documents routed by `docs/agent/agent-index.md`.

## Application Shape

FPVS Studio is a Windows-focused PySide6 authoring application. The GUI edits project
models and compiles engine-neutral execution contracts. Runtime coordinates sessions;
presentation is isolated behind an engine interface, with PsychoPy loaded lazily only
inside the engine package.

## Package Map

- `src/fpvs_studio/app/`: thin application entry points and startup wiring.
- `src/fpvs_studio/assets/`: packaged release-facing static assets.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding,
  Home/Setup workflows, and shared components/theme helpers.
- `src/fpvs_studio/core/`: editable models, validation, compilation, `RunSpec`,
  `SessionPlan`, execution results, persistence, `.fpvsconfig` interchange, portable
  `.fpvsbundle` services, and other engine-neutral domain logic.
- `src/fpvs_studio/preprocessing/`: image intake, inspection, normalization, derived
  variants, and manifest provenance; independent of GUI, runtime, and PsychoPy.
- `src/fpvs_studio/tools/`: reserved for Studio-native utilities. Current Image Resizer
  UI remains under the GUI package and delegates to preprocessing.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session orchestration,
  participant history, fixation scoring, trigger coordination, and execution exports.
- `src/fpvs_studio/engines/`: presentation interface and lazy PsychoPy implementation.
- `src/fpvs_studio/triggers/`: optional hardware adapters used by runtime. Normal event
  codes are `1`-`255`; `0` is manual reset only. The `oddball_onset` code remains `55`
  unless the user explicitly enables and records
  `allow_nonstandard_oddball_trigger_code`.
- `src/fpvs_studio/updates/`: GUI-neutral GitHub Releases checking, installer download,
  and explicit installer-launch helpers.
- `tests/`: unit, integration, and registered pytest-qt coverage.
- `packaging/`: PyInstaller/Inno configuration and release assets for Windows builds.

Every source package has a nested `AGENTS.md`; read the one governing files you edit.

## Contract Flow

```text
ProjectFile
  -> compiler -> RunSpec (one condition)
  -> session compiler -> SessionPlan (ordered RunSpec entries)
  -> runtime -> engine playback + core execution results
  -> exporters -> project logs and optional detailed run artifacts
```

- Compilation owns protocol scheduling, asset resolution, randomized session order,
  and realized fixation target selection.
- Editable project protocol settings own requested base Hz and integer oddball cadence;
  compilation resolves them to whole-frame timing and records requested rates in each
  `RunSpec`.
- Core validation owns the approved monitor-rate list. Runtime reads the primary
  Windows display path's exact rational mode and combines it with the engine's neutral
  fullscreen refresh observation. The GUI requests this combined verification, and
  runtime preflight repeats it once per session without changing compiled schedules.
- Runtime owns machine launch options, session transitions, participant flow, fixation
  scoring, trigger I/O coordination, and result assembly.
- Engines render compiled events and participant-facing screens; they do not own
  compilation, session decisions, project persistence, or exports.
- Full export mode writes detailed artifacts under `runs/`. Compact mode keeps
  project-level reporting under `logs/` without detailed run folders.
- GUI project-bundle import/export is current active work; its approved boundaries and
  verification remain in `docs/exec-plans/active/project-bundle-import-export.md`.

## Dependency Rules

- GUI may call core, preprocessing, runtime, trigger, and update services but must not
  absorb their domain logic.
- Runtime consumes compiled core contracts and engine interfaces; it must not import
  PySide6 widgets.
- Only engines may import PsychoPy, and those imports stay lazy.
- Core and preprocessing remain engine-neutral. Trigger hardware details stay outside
  project execution contracts.
- App-level template profiles live at
  `<FPVS Studio Root>/.fpvs-studio/templates/`, outside experiment projects.
- Project-facing paths remain project-relative POSIX strings.

## Source-of-Truth Documents

- Product/protocol scope: `docs/FPVS_Studio_v1_Architecture_Spec.md`
- GUI design and workflow: `docs/FRONTEND.md` and `docs/GUI_WORKFLOW.md`
- Run/session/runtime contracts: `docs/RUNSPEC.md`, `docs/SESSION_PLAN.md`, and
  `docs/RUNTIME_EXECUTION.md`
- Engine boundary: `docs/ENGINE_INTERFACE.md`
- Environment and packaging: `docs/ENVIRONMENT.md` and `docs/PACKAGING.md`
- Plans and technical debt: `docs/PLANS.md` and `docs/exec-plans/`

Use `docs/index.md` for the full developer-documentation map.

## Task Context Recipes

Start with `docs/agent/agent-index.md`. Match one of its 12 verification scopes, read
only that row's initial context and the nearest nested `AGENTS.md`, then search for the
specific symbol or behavior. Do not open broad source/test trees merely to confirm a
passing audit.

For feature-sized or cross-layer changes, also read `docs/PLANS.md` and the relevant
active plan. Completed plans are historical implementation notes, not current contracts.

## Verification

The scope-aware driver selects `.venv3.10`, falls back to `.venv`, and then uses the
current compatible Python interpreter:

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

- `focused`: scope tests/checks plus changed-file Ruff and compilation.
- `precommit`: mechanical/docs audits, mypy, changed-file checks, and safe non-Qt pytest.
- `full-ci`: full Ruff, mypy, and pytest with registered Qt tests explicitly enabled.

Add `-List` to a scoped command to inspect its steps and use
`./scripts/verify.ps1 -CheckConfig` after harness edits. GUI-focused local verification
does not run Qt. Document a visible manual smoke path; run Qt locally only when the user
approves a safe visible environment. Offscreen Qt is restricted to the explicit CI tier.

Legacy PowerShell wrappers remain supported for developer workflows, packaging, and CI,
but agent routing should use the driver so environment selection and test safety remain
consistent.

## Documentation Freshness

Update this map when a top-level package, source-of-truth owner, dependency boundary,
contract flow, active workflow, or verification route changes. Update the nearest nested
`AGENTS.md` or focused document in the same change.

Keep this file compact. Behavioral detail belongs in the relevant package guide, focused
contract document, execution plan, or repo-local skill. Verify documentation changes
with the `docs` scope; do not duplicate raw command lists in multiple active documents.

## Versioning and Packaging

The application version is declared in `pyproject.toml`; the distribution name is
`fpvs-studio` and the user-facing name is FPVS Studio. Packaging and in-app updater
requirements live in `docs/PACKAGING.md`, `packaging/AGENTS.md`, and the updates package
guide. Use the `packaging` or `updates` verification scope rather than discovering raw
test commands again.

## Module Decomposition

File length is evidence, not an architecture rule. Split a module only when it mixes
responsibilities, forces broad context reads, or prevents focused testing. Current
measured candidates and constraints live in
`docs/exec-plans/tech-debt-tracker.md`.
