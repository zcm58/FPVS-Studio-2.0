# AGENTS.md

FPVS Studio authors versioned experiments, runs participant visits and hands
completed studies to Toolbox. Windows supports acquisition. macOS has experimental source support.

## Efficient Working Route

- Fast path before broad reads: check `git status --short --branch`. The
  [task index](docs/agent/agent-index.md) gives the scope, package guide, contract
  and focused verification. Use [architecture](ARCHITECTURE.md) for ownership.
- Preserve unrelated edits, untracked files, retained output, formats and workflows.
  Maintain an [execution plan](docs/PLANS.md) for feature-sized or cross-layer work.
- For implementation changes, apply the relevant [software quality checks](docs/agent/task-recipes.md#software-quality-checks).
  Verify material risks and fix verified deficiencies within scope. Fix regressions
  introduced by the change or obtain the user's explicit approval for the specific
  tradeoff before keeping, committing or pushing it. Preserve deterministic outputs
  bit for bit unless changing them is explicitly in scope. Choose the most efficient
  viable design that preserves scientific, timing and integrity contracts. Justify
  extra work against a concrete alternative. [Performance verification](docs/agent/agent-index.md#performance-and-output-parity)
- Use the [shared desktop guidance](docs/DESIGN.md#shared-openfpvs-desktop-experience)
  for independent release planning, audience and interaction decisions.

## Contract Boundaries

- Core compiles `ProjectFile` to `RunSpec` and `SessionPlan`. Preserve frame schedules,
  randomization and compiled fixation events. Runtime executes and scores. Engines
  render and alone import PsychoPy, lazily. Machine settings stay outside compiled plans.
- Core and preprocessing stay independent of Qt and hardware. GUI uses PySide6,
  `PySide6.QtGui.QAction`, worker signals and structured logging. Workers never
  access widgets. Retain explicit failures for trigger, display, dependency and
  runtime errors. Do not add CustomTkinter or fallback application modes.
- Project I/O uses the active project root. App templates live under
  `<FPVS Studio Root>/.fpvs-studio/templates/`. Editing `Main_App/Legacy_App/**`
  or `Tools/SourceLocalization/**` requires an explicit user request.

## GUI Acceptance

- Use the [GUI package guide](src/fpvs_studio/gui/AGENTS.md)
  for components, workflow contracts and registered Qt coverage.
- Check for clipping at minimum/default size with realistic content and document
  a visible smoke path. Local Qt execution requires approval for a safe visible
  environment. Never use offscreen Qt locally.

## Figure Generation

- Follow the [figure generation standard](docs/design-docs/figure-generation.md)
  for exported figures, agent-generated artwork and new figure tools.

## Verification and Plans

Use the [verification tiers](docs/agent/agent-index.md#verification-tiers).
Run precommit for shared behavior changes and `-CheckConfig` after harness edits.
Report external checks separately from local results. Physical display and EEG
timing require hardware evidence.

## Documentation Freshness

Update `ARCHITECTURE.md` when ownership changes, the task index when routing changes
and the owning contract when behavior changes. Archive completed plans and clean
task-generated artifacts.
