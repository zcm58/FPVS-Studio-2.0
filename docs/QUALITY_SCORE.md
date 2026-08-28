# Local Quality Checks

FPVS Studio uses locally executable evidence instead of a manually maintained numeric
score or a GitHub code-quality gate. The scope-aware driver is the agent entry point;
its configuration owns the underlying test, audit, lint, type, and compilation commands.

## Standard Route

```powershell
./scripts/verify.ps1 -Scope <scope> -Tier focused
./scripts/verify.ps1 -Scope repo -Tier precommit
```

- `focused` runs the selected scope plus changed-file Ruff and compilation.
- `precommit` adds mechanical/docs audits, mypy, and the safe non-Qt pytest suite.
- `full` optionally runs full Ruff, mypy, and pytest with registered Qt tests explicitly
  enabled in a user-approved safe visible environment.

Use `docs/agent/agent-index.md` to choose among `repo`, `docs`, `gui`, `core`,
`compiler`, `project-io`, `preprocessing`, `runtime`, `engine`, `triggers`, `updates`,
and `packaging`. Add `-List` to a scoped command to inspect resolved steps and use
`./scripts/verify.ps1 -CheckConfig` after harness changes.

## Safety and Garbage Collection

The configured audits enforce repository invariants such as:

- production diagnostics use structured logging rather than `print`
- PySide6, PsychoPy, and hardware imports remain behind their package boundaries
- shared GUI styling stays in the component surface
- machine-local paths stay out of committed source, tests, and scripts
- plan state matches its planned/active/completed directory
- historical setup and audit docs remain outside the active docs root
- registered Qt tests cannot enter the default local suite before import

GUI-focused local verification does not run Qt. It reports the required visible/manual
smoke path, while registered pytest-qt coverage runs only through the optional `full`
tier. Any skipped or failing check must be reported with its command, reason, and
residual risk.

PowerShell wrappers remain available for developer-specific workflows and release
builds. Do not duplicate their individual commands in agent guidance; route ordinary
work through the driver. GitHub does not repeat these repository checks; its independent
documentation build and publishing workflow remains automated.
