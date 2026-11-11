# AGENTS.md

FPVS Studio is a PySide6 authoring application with Windows acquisition and experimental macOS source support.
PsychoPy presentation stays behind runtime and engine boundaries.

## Efficient Working Route

- Fast path before broad reads: check `git status --short --branch`. Use the
  [task index](docs/agent/agent-index.md) for one scope, its nested `AGENTS.md`
  and one contract section. Use `ARCHITECTURE.md` to resolve ownership.
- Run focused verification before expanding to implicated symbols, failures or
  cross-layer behavior. Find the relevant active plan in `docs/PLANS.md`.
- Preserve unrelated edits, persisted formats, processing order and workflows. Read
  generated output, environments or archives only as needed. Untracked files and
  retained output are user-owned.

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
  Setup's nine steps must fit `1120x820` without required scrolling or truncation.
  Intentional elision requires an accessible full value and coverage.
- Add/update registered pytest-qt coverage for changed GUI behavior. Do not run Qt
  locally by default. Use non-Qt checks and document a visible manual smoke path.
  Qt execution requires user approval for a safe visible environment; never use
  offscreen Qt locally.

## Figure Generation

- Follow the [figure generation standard](docs/design-docs/figure-generation.md)
  for exported figures, agent-generated artwork and new figure tools.
- Omit subtitles and redundant copy. Center a meaningful title when needed,
  and use the shared print typography, accessible labels and 600-DPI raster floor.

## Verification and Plans

Use the task index for skills and verification. Keep a current `docs/exec-plans/`
plan for feature-sized or cross-layer work and archive it when complete.

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

The driver selects `.venv3.10`, `.venv`, then compatible current Python. Run
`precommit` for shared behavior changes. Use `-List` to inspect steps and
`-CheckConfig` after harness edits. GitHub runs Windows precommit, macOS source
and cross-OS bundle checks, and docs publishing. Local verification and physical
display/EEG acceptance have separate evidence.

## Documentation Freshness

Update `ARCHITECTURE.md`, the task index and the nearest scoped document when
ownership, boundaries, workflows or verification routes change. Keep detailed
contracts in one canonical document. Done means requested behavior is complete,
focused checks pass, applicable precommit runs, skipped external/GUI checks are
reported and generated artifacts are cleaned without deleting user data.
