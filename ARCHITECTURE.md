# Architecture

This is FPVS Studio's compact repository map. Detailed workflow and method contracts
belong in the focused documents routed by `docs/agent/agent-index.md`.

## Application Shape

FPVS Studio is a Windows-focused PySide6 authoring application with a source-only
experiment test mode supported on Windows and Linux development hosts. The GUI edits
project models and compiles engine-neutral execution contracts. Runtime coordinates
sessions; presentation is isolated behind an engine interface, with PsychoPy loaded
lazily only inside the engine package.

## Package Map

- `src/fpvs_studio/app/`: thin application entry points and startup wiring.
- `src/fpvs_studio/assets/`: packaged release-facing static assets, including the
  licensed Open Sans face used by authored modular tasks.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding,
  Home/Setup workflows, and shared components/theme helpers. New-experiment Setup
  starts with category alone, then project details. Setup composes nine
  model-backed pages (Project, Conditions, Design, Timing, Image Size, Session, Fixation,
  Response, Review); shared dialog/form styling remains in `gui/components.py`.
  Design embeds a shared category-specific visual editor. Setup's Next action applies
  the draft through the existing navigation gate; the standalone host retains Apply.
  The GUI separates a schematic stream overview from proportional target-pair timing.
  `core/experiment_design.py`
  owns oddball cycle descriptions and optional frame-based previews. Oddball Apply
  uses existing protocol settings. `core/attentional_blink.py` owns requested and
  resolved target-pair timing; `core/compiler_attentional_blink.py` expands those
  pairs into executable frame events inside the existing normal-slot cadence.
  ISI can use an independent image pool or an explicit blank event; preview and
  engines consume that choice without changing slot timing.
  Only the AB category exposes ISI; backward-masking prototype controls are removed.
  Manage Projects routes metadata-only renaming through `core/project_service.py`;
  the live document synchronizes the new name without saving other pending edits.
- `src/fpvs_studio/core/`: editable models, validation, compilation, `RunSpec`,
  `SessionPlan`, reusable condition-task definitions, execution results, persistence,
  `.fpvsconfig` interchange, portable `.fpvsbundle` services, and other engine-neutral
  domain logic.
- `src/fpvs_studio/preprocessing/`: image intake, inspection, normalization, derived
  variants, and manifest provenance; independent of GUI, runtime, and PsychoPy.
- `src/fpvs_studio/tools/`: reserved for Studio-native utilities. Current Image Resizer
  UI remains under the GUI package and delegates to preprocessing.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session orchestration,
  participant history, fixation reporting and explicit-path Excel export, fixation
  scoring, trigger coordination, and execution exports.
  Attentional-blink runs add phase onset records and event CSVs in full and compact
  exports; timing ownership and clock origins are defined in `docs/RUNSPEC.md` and
  `docs/RUNTIME_EXECUTION.md`.
- `src/fpvs_studio/engines/`: presentation interface, lazy PsychoPy implementation,
  condition-local GPU-ready resource ownership, and Windows graphics-budget probing.
- `src/fpvs_studio/triggers/`: optional hardware adapters used by runtime. Normal event
  codes are `1`-`255`; `0` is manual reset only. The `oddball_onset` code remains `55`
  unless the user explicitly enables and records
  `allow_nonstandard_oddball_trigger_code`.
- `src/fpvs_studio/updates/`: GUI-neutral GitHub Releases checking, bounded updater
  cache ownership/locking, cancelable checksum-verified downloads, and explicit
  verified installer-launch helpers.
- `tests/`: unit, integration, and registered pytest-qt coverage.
- `packaging/`: PyInstaller/Inno configuration, published legacy ownership inventory,
  and release assets for Windows builds. Installer-owned file reconciliation remains
  here, separate from project data and the runtime updater cache.

Every source package has a nested `AGENTS.md`; read the one governing files you edit.

## Contract Flow

```text
ProjectFile
  -> compiler -> RunSpec (one condition)
  -> session compiler -> SessionPlan (ordered RunSpec entries + pre/post task specs)
  -> runtime -> task flow + engine playback + core execution results
  -> exporters -> project logs and optional detailed run artifacts
```

`ProjectFile` uses schema `1.4.0`; `SessionPlan`, execution-result, and `.fpvsconfig`
contracts remain schema `1.2.0`, and the single-condition timed `RunSpec` remains schema
`1.1.0`. Project loaders migrate schemas `1.0.0` through `1.3.0` in memory;
reading or launching an older project does not rewrite it. The `1.3.0` project migration
enables fixation color changes, accuracy scoring, and the participant tutorial once,
while a later current-schema save may preserve an explicit user opt-out. Compatibility
otherwise preserves a zero-second lead-in, empty condition-task bindings, and legacy
word-size pixel rounding until those settings are explicitly authored. A legacy zero
fixation-target duration becomes the current 300 ms default because the newly enabled
task requires a positive duration.
Modular-task font selection is additive within the schema `1.2.0` compiled task/session
contract: missing values resolve to Arial, and the selection never enters the `RunSpec`
timed-frame contract.

`ProjectFile.experiment_category` is immutable after creation. `core/experiment_categories.py`
owns category labels and conflict checks; `core/project_separation.py` preserves legacy
mixed designs in separate experiments after an explicit user action. Category inference,
template compatibility and no-mixing boundaries are defined in
[`EXPERIMENT_CATEGORIES.md`](docs/EXPERIMENT_CATEGORIES.md).

- Compilation owns protocol scheduling, asset resolution, randomized session order,
  realized fixation target selection, presentation-setting inheritance, balanced
  word-height realization, and the frame count from which core defines a sinusoidal
  contrast envelope.
- Editable project protocol settings own requested base Hz and integer oddball cadence;
  compilation resolves them to whole-frame timing and records requested rates in each
  `RunSpec`.
- Core validation owns the approved monitor-rate list. Runtime reads the primary/default
  display's native configured mode through a platform adapter and combines it with the
  engine's neutral fullscreen refresh observation. Windows keeps its exact rational
  `QueryDisplayConfig` path; KDE Linux uses structured KScreen mode and VRR metadata,
  with XRandR used for X11. The GUI requests this combined verification, and runtime
  preflight repeats it once per session without changing compiled schedules.
- `core/paths.py` owns Windows filesystem namespace adaptation. Image I/O uses
  extended-length paths while manifests and compiled contracts retain project-relative
  POSIX paths; containment checks and serialization normalize both filesystem forms.
- Runtime owns machine launch options, session transitions, declarative pre/post task
  sequencing and validation, participant flow, fixation scoring, trigger I/O
  coordination, and result assembly. Task clocks and compiled Arial/Open Sans font
  choices remain outside `RunSpec` and cannot change FPVS frame or trigger schedules.
- The PsychoPy engine prepares and synchronizes one condition cache at a time, checks
  production RAM/graphics-budget readiness before frame zero, rejects measured resource
  insufficiency, and preserves unavailable telemetry as an exported warning. It executes
  a precompiled hot loop, including preselected per-frame image contrast operations for
  sinusoidal mode, ends the last compiled frame with a neutral offset flip, and releases
  the cache before returning. Runtime scores fixation RT from same-clock hardware
  timestamps and owns the exported result contracts.
- The app-level experiment test-mode setting and selector remain outside persisted
  project contracts. Each test launch may compile all conditions (the default) or one
  selected condition; the resulting ordinary `SessionPlan` contains only the compiled
  entries, with no dedicated test-scope field. A selected condition still appears once
  per configured block with its ordinary task flow and execution behavior. Production
  launches always compile all conditions. Test mode explicitly selects null-trigger
  output and disables
  connected-display refresh and graphics-memory verification while preserving
  fullscreen playback, compiled schedules, asset checks, timing QC, task flow, and test
  exports.
- `ProjectFile` owns the per-participant `manual_removed_electrodes` authoring map saved
  from the launch dialog; it remains outside compiled and runtime playback contracts.
- Engines render compiled events and one neutral task step at a time; they do not own
  task sequencing, validation, compilation, session decisions, project persistence,
  or exports. Runtime image/word transforms and native geometry are compiled
  presentation properties and never create project assets.
- Full export mode writes detailed artifacts under `runs/`. Compact mode keeps
  project-level reporting under `logs/` without detailed run folders.
- GUI project-bundle import/export is implemented; its current workflow and contracts
  live in `docs/GUI_WORKFLOW.md` and `src/fpvs_studio/core/project_bundle.py`.

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
- `full`: optional full Ruff, mypy, and pytest with registered Qt tests explicitly
  enabled for an approved visible local environment.

Add `-List` to a scoped command to inspect its steps and use
`./scripts/verify.ps1 -CheckConfig` after harness edits. GUI-focused local verification
does not run Qt. Document a visible manual smoke path; run Qt locally only when the user
approves a safe visible environment, and do not set `QT_QPA_PLATFORM=offscreen`.

GitHub does not run a repository test or code-quality workflow; the independent
documentation build and publishing workflow remains automated. Legacy PowerShell
wrappers remain supported for developer workflows and packaging, but agent routing
should use the driver so environment selection and test safety remain consistent.

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
test commands again. Packaging entry points accept an optional safe `BuildLabel` to
isolate beta artifacts under matching ignored `build/` and `dist/` subdirectories.

## Module Decomposition

File length is evidence, not an architecture rule. Split a module only when it mixes
responsibilities, forces broad context reads, or prevents focused testing. Current
measured candidates and constraints live in
`docs/exec-plans/tech-debt-tracker.md`.
