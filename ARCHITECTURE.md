# Architecture

This is FPVS Studio's compact repository map. Detailed workflow and method contracts
belong in the focused documents routed by `docs/agent/agent-index.md`.

## Application Shape

FPVS Studio is a Windows-focused PySide6 authoring application with local
experiment test mode available in source and installed builds on Windows and Linux. The GUI edits
project models and compiles engine-neutral execution contracts. Runtime coordinates
sessions; presentation is isolated behind an engine interface, with PsychoPy loaded
lazily only inside the engine package.

## Package Map

- `src/fpvs_studio/app/`: thin application entry points and startup wiring.
- `src/fpvs_studio/library/`: GUI-neutral experiment catalog, device enrollment,
  native protected credential storage, and bounded verified bundle downloads.
  The Library dialog uses app-owned jobs and the existing reviewed project importer;
  `core/library_publish.py` prepares clean publishable whole-project copies with
  the current fixed COM3 serial-port policy.
  Private content and the independent Cloudflare service live in
  `zcm58/FPVS-Studio-Library`; that service checks live release-asset availability
  for each browse/download. See `docs/EXPERIMENT_LIBRARY.md`.
- `src/fpvs_studio/developer/`: bundled maintainer tools, enabled by a password-gated
  app preference in Settings > Advanced. `mode.py` snapshots activation at startup;
  enabling/disabling requires restart. `library_publisher.py` owns prepared copies;
  `catalog_publisher.py` owns GitHub credentials, owner/write authorization, immutable
  uploads and atomic catalog publication. The private CLI delegates to this module.
  GUI workers call it directly; no separate checkout or interpreter is needed.
- `src/fpvs_studio/support/`: GUI-neutral bug-report and feature-request contracts, queued
  application diagnostics, bounded OS-local drafts, and an opt-in HTTPS client.
  The native File > Report a Bug dialog uses app-owned background jobs; online
  submission defaults to the verified production endpoint and requires explicit user action.
  The independent Cloudflare backend is in private `zcm58/FPVS-Studio-Feedback`.
  See `docs/BUG_REPORTING.md` for the wire contract and activation.
- `src/fpvs_studio/assets/`: packaged release-facing static assets, including the
  licensed Open Sans face used by authored modular tasks.
- `src/fpvs_studio/gui/`: PySide6 windows, dialogs, controllers, document binding,
  Home/Setup workflows, and shared components/theme helpers. New-experiment Setup
  starts with manual creation or Library download. Manual creation asks for category,
  then project details; Library downloads reuse bundle import. Setup composes eight
  model-backed pages (Project, Conditions, Design, Timing & Session, Image Size, Fixation,
  Response, Review); shared dialog/form styling remains in `gui/components.py`.
  User-selected project reads use the app-owned job lifecycle; GUI documents/windows
  are constructed after completion on the GUI thread. Authoring save feedback and
  per-editor thumbnail reuse are specified in `docs/GUI_WORKFLOW.md`.
  Conditions confirms populated image/word switches before the document replaces only
  the selected condition's source associations. Its list and text editors expand
  vertically within the shared wizard surface; see `docs/GUI_WORKFLOW.md`.
  Design embeds a shared category-specific visual editor. Setup's Next action applies
  the draft through the existing navigation gate; the standalone host retains Apply.
  `core/experiment_design.py` owns oddball cycle descriptions and frame previews;
  Oddball Apply uses existing protocol settings. AB image pairs are retired, with
  guards in category validation, authoring, runtime preflight and direct engine launch.
  New AB bursts use `gui/attentional_blink_stream_designer.py`, shared native
  letter/digit pools, editable bursts per SOA and presentation rate, and onset-to-onset
  SOAs. `core/attentional_blink_stream.py` owns
  the exact character grid and seeded symbol sampling shared with the designer;
  `core/compiler_attentional_blink_stream.py` compiles the resulting stream.
  `core/attentional_blink_presets.py` assembles the three-condition burst study and
  two typed recall questions submitted with Enter/Next. New sessions shuffle all
  repeated bursts as one session block; every recall burst requires Space, and
  compiled answer keys refer to each entry's actual targets. Existing native studies
  retain their saved character pools and blockwise session behavior.
  Historical image-pair models remain decodable without an authoring or playback route.
  AB letter streams can hide the fixation cross through Setup > Fixation. The persisted
  `FixationTaskSettings.show_cross` flag compiles into `FixationStyleSpec`; engines
  skip cross preparation/drawing while preserving lead-in and stream frame timing.
  Manage Projects routes metadata-only renaming through `core/project_service.py`;
  the live document synchronizes the new name without saving other pending edits.
- `src/fpvs_studio/core/`: editable models, validation, compilation, `RunSpec`,
  `SessionPlan`, reusable condition-task definitions, execution results, persistence,
  `.fpvsconfig` interchange, portable `.fpvsbundle` services, and other engine-neutral
  domain logic. `compiler_inputs.py` and `compiler_tasks.py` prepare shared inputs only
  for one compilation invocation; compiled run/task outputs stay independent.
  `serialization.py` owns atomic UTF-8 persistence; bundle hashes describe the exact
  streamed archive bytes. See `docs/SESSION_PLAN.md` and `docs/GUI_WORKFLOW.md`.
- `src/fpvs_studio/preprocessing/`: image intake, inspection, normalization, derived
  variants, and manifest provenance; independent of GUI, runtime, and PsychoPy.
  Fresh source pools are staged and validated before document adoption.
- `src/fpvs_studio/tools/`: reserved for Studio-native utilities. Current Image Resizer
  UI remains under the GUI package and delegates to preprocessing.
- `src/fpvs_studio/runtime/`: launch settings, preflight, session orchestration,
  participant history and atomic visit reservation, fixation reporting and explicit-path Excel export, fixation
  scoring, trigger coordination, and execution exports.
  Attentional-blink runs add phase onset records and event CSVs in full and compact
  exports; `runtime/attentional_blink_report.py` owns incremental burst records,
  independent T1/T2 scoring summaries and dedicated Excel export. View selects
  T1 and T2 Accuracy for AB, or Fixation Task Accuracy for other categories. The AB
  dialog shows SOA summaries with recorded trigger codes and chronological bursts
  through that read-only service, including identified test sessions and their accuracy.
  Timing ownership and clock origins are defined in `docs/RUNSPEC.md` and
  `docs/RUNTIME_EXECUTION.md`.
- `src/fpvs_studio/engines/`: presentation interface, lazy PsychoPy implementation,
  condition-local GPU-ready resource ownership, and Windows graphics-budget probing.
- `src/fpvs_studio/triggers/`: optional hardware adapters used by runtime. Normal event
  codes are `1`-`255`; `0` is manual reset only. The `oddball_onset` code remains `55`
  unless the user explicitly enables and records
  `allow_nonstandard_oddball_trigger_code`.
- `src/fpvs_studio/updates/`: GUI-neutral GitHub Releases checking, bounded updater
  cache ownership/locking, checksum-verified downloads, and independent updater
  coordination. Studio's GUI calls `helper_client.py` over bounded private subprocess
  pipes; `helper_service.py` owns check/download and the accepted installation handoff,
  while `helper_runtime.py` owns registration, staging, process identity, installation
  locking, and restart. `patches.py` selects authenticated patch candidates without
  scanning installed payload files. Inno owns final baseline verification, replacement,
  recovery, and target verification. The retained full Python verifier uses scoped
  directory pins and reusable Windows bindings. Typed phase events keep progress and
  installation commitment separate from GUI presentation.
- `src/fpvs_studio/updater_main.py`: independent entry for backend pipe operations,
  the managed install-progress window, and standalone Update & Repair. Its GUI reuses
  `gui/update_dialog.py`, `gui/updater_window.py`, and the existing worker lifecycle;
  its minimal one-file bundle excludes Studio's authoring/runtime/engine dependencies.
- `tests/`: unit, integration, and registered pytest-qt coverage.
- `packaging/`: PyInstaller/Inno configuration, published legacy ownership inventory,
  and release assets for Windows builds. The ordinary installer bundles the independent
  updater under `Updater/` and supplies a Start Menu Update & Repair entry. The updater
  runs from guarded user-local staging so setup can replace its installed executable.
  Patch payloads are generated from authenticated
  baseline inventories and the complete target bundle. Installer-owned file reconciliation remains
  here, separate from project data and the runtime updater cache.

Every source package has a nested `AGENTS.md`; read the one governing files you edit.

## Contract Flow

Masking modifiers own native image/text/shape source pools and independent within-item
target/mask windows. Core compiles them to `RunSpec.scene_stream`; engines prepare
native draw calls, while pre/post screens remain `SessionEntry` tasks. Variant groups
use authored task flow. See [Masking](docs/MASKING.md) for schemas and exactness limits.

```text
ProjectFile
  -> compiler -> RunSpec (one condition)
  -> session compiler -> SessionPlan (ordered RunSpec entries + pre/post task specs)
  -> runtime -> task flow + engine playback + core execution results
  -> exporters -> project logs and optional detailed run artifacts
```

Letter streams use `ProjectFile` schema `1.5.0` and `.fpvsconfig`/`RunSpec` schema
`1.3.0`. Legacy projects/configs/runs retain `1.4.0`/`1.2.0`/`1.1.0`. `SessionPlan`
and execution-result contracts remain `1.2.0`. New native-stream onset exports use
`attentional_blink_stream_events_v1.csv`; legacy image exports retain their headers.
Template-library `1.2.0` carries explicit layout identity in profile defaults.
Project loaders migrate schemas `1.0.0` through `1.3.0` in memory;
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

Condition modifiers use project schema `1.6.0` and config schema `1.4.0`, retaining
the existing `RunSpec` and bundle envelope. `core/condition_modifiers.py` owns
workflow grouping, factories, and draft assignment changes that preserve unaffected
condition bindings; `core/modifier_presets.py` owns independent local
presets and staged project media intake. Existing condition bindings remain the
task execution order. Compilation resolves selected session baselines and linked
memory targets outside FPVS timing; runtime scores the existing response contracts.
See [Condition modifiers](docs/CONDITION_MODIFIERS.md) for authoring and compatibility.

`ProjectFile.experiment_category` is immutable after creation. `core/experiment_categories.py`
owns category labels and conflict checks; `core/project_separation.py` preserves legacy
mixed designs in separate experiments after an explicit user action. Category inference,
template compatibility and no-mixing boundaries are defined in
[`EXPERIMENT_CATEGORIES.md`](docs/EXPERIMENT_CATEGORIES.md).

Cognitive Load FPVS uses ordinary image RunSpecs with three matched load/no-load
pairs. `core/cognitive_load_presets.py` owns scaffolding; `core/backward_counting.py`
and task contracts own reusable baseline/start/endpoint modules. Compilation realizes
seeded starting numbers and a session-first baseline outside FPVS frames; runtime
owns endpoint estimates and task-response checkpoints. Details and acceptance are in
[`COGNITIVE_LOAD_FPVS.md`](docs/COGNITIVE_LOAD_FPVS.md).

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
  from the launch dialog as the latest prefill. Each new execution snapshots the
  reviewed list in participant metadata so repeat visits preserve their own setup.
- `ProjectSettings.allow_repeated_participant_sessions` enables repeat visits in the
  GUI. Runtime owns collision-safe `participant_session_number` reservation and
  reporting identity across full/compact exports, independent of compiled sessions.
  See [Runtime execution](docs/RUNTIME_EXECUTION.md#repeat-participant-sessions) for
  compatibility rules.
- Engines render compiled events and one neutral task step at a time; they do not own
  task sequencing, validation, compilation, session decisions, project persistence,
  or exports. Runtime image/word transforms and native geometry are compiled
  presentation properties and never create project assets.
  The trigger backend contract declares physical-output capability; playback rejects
  log-only backends outside explicit test/pilot launches and empty trigger schedules.
- Full export mode writes each numbered visit under `runs/P<PID>_session<NN>/`.
  Compact mode keeps reporting and visit reservations under `logs/` without detailed
  run folders. Historical outputs remain in place.
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
- The independent updater imports no runtime or experiment engine. Studio saves through
  its existing GUI callback before accepting a handoff; the helper never edits projects.
  Installer/download trust, private IPC, and recovery rules live in `docs/PACKAGING.md`.
- `tests/unit/test_import_boundaries.py` checks documented internal restrictions,
  including relative imports and aliased authoring-model use, without importing modules.
  It preserves the explicit core/preprocessing contract relationship.

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


AB-only Pilot Study Mode is an app preference owned by the GUI document/controller.
It retains standard demographics and visit rules while selecting local testing hardware
options. Runtime checkpoints pilot identity and demographics alongside each burst;
the accuracy GUI and Excel expose them. See `docs/RUNTIME_EXECUTION.md`.
