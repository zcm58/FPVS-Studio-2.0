# AGENTS.md

FPVS Studio is a Windows-focused PySide6 authoring application for FPVS experiments.
PsychoPy presentation stays behind runtime and engine boundaries.

## Efficient Working Route

- Fast path before broad reads: check `git status --short --branch`, then use
  [the task index](docs/agent/agent-index.md) to select one scope, its package guide
  and one relevant contract section. `ARCHITECTURE.md` is the package/dependency map.
- Read nested `AGENTS.md` files governing edited paths. For non-trivial work, use
  `docs/PLANS.md` to find the relevant active plan; completed plans are history.
- Run the selected focused verification before broad inspection. Expand context
  only for implicated symbols, failures or cross-layer behavior.
- Preserve unrelated changes, persisted formats, processing order and workflows.
  Do not read output, environments, caches, builds or archives without task need.
  Untracked files and retained output are user-owned.

## Contract Boundaries

- Core compiles editable `ProjectFile` state to single-condition `RunSpec` and
  multi-condition `SessionPlan`. Runtime and engines consume compiled contracts,
  not editable projects. Use existing owners in `ARCHITECTURE.md`.
- Runtime owns ordered sessions, participant flow, scoring and core-owned execution
  results. Exporters serialize them; engines render screens and one run at a time.
- Keep machine/launch settings outside compiled contracts. Compiled timing uses
  frames; fixation tasks must not alter base/oddball scheduling. Preserve session
  randomization and compile-time fixation realization unless explicitly changed.
- Only engines may import PsychoPy, lazily. Core and preprocessing remain independent
  of PySide6, PsychoPy and hardware. GUI uses PySide6; import `QAction` from `PySide6.QtGui`.
  Do not add CustomTkinter or fallback non-GUI application modes.
- Keep work off the UI thread through workers/signals; workers never touch widgets.
  Use structured logging, not production `print` calls.
- Project I/O uses the active project root and preserves portable formats. App
  templates belong in `<FPVS Studio Root>/.fpvs-studio/templates/`.
- Do not add silent trigger, display, dependency or runtime fallbacks. Protected
  `Main_App/Legacy_App/**` and `Tools/SourceLocalization/**`, if present, require an
  explicit user request before edits.

## GUI Acceptance

- For substantial UI work, define the task, primary action, affected states and
  observable success criteria. Follow current `docs/FRONTEND.md` contracts and
  [UI design guidance](docs/design-docs/agent-ui-design.md); routine decisions need
  no extra approval checkpoint. Preserve the quiet scientific-tool character.
- Reuse `gui/components.py`. No clipping is the default: verify each changed surface
  at its minimum/default size with realistic longest content and relevant states.
  Setup's eight steps must fit `1120x820` without required scrolling or truncation.
  Intentional elision requires an accessible full value and coverage.
- Add/update registered pytest-qt coverage for changed GUI behavior. Do not run Qt
  locally by default. Use non-Qt checks and document a visible manual smoke path.
  Qt execution requires user approval for a safe visible environment; never use
  offscreen Qt locally.

## Verification and Plans

Use the task index for skills and verification routes. Global web/mobile skills do
not establish desktop architecture. Feature-sized or cross-layer work uses a current
`docs/exec-plans/` plan; keep its status/location accurate and archive completed work.

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

The driver selects `.venv3.10`, then `.venv`, then compatible current Python.
`focused` runs scope checks plus changed-file Ruff/compilation; `precommit` adds
audits, mypy and safe non-Qt tests. Run precommit for shared behavior changes.
`full` includes Qt and requires the visible-environment approval above. Use `-List`
to inspect steps and `-CheckConfig` after harness changes. GitHub runs documentation
publishing, not the repository's local tests or code-quality checks.

## Documentation Freshness

Update `ARCHITECTURE.md`, the task index and the nearest scoped document when
ownership, boundaries, workflows or verification routes change. Keep detailed
contracts in one canonical document. Done means requested behavior is complete,
focused checks pass, applicable precommit runs, skipped external/GUI checks are
reported and generated artifacts are cleaned without deleting user data.
