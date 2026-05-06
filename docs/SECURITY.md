# Security

FPVS Studio is a local desktop application. Security work is mostly about safe local file
handling, dependency discipline, and avoiding accidental data exposure.

## Guardrails

- Keep project file I/O rooted in the active project root.
- Preserve existing project formats and avoid hidden fallback paths.
- Do not log participant-sensitive data unless a feature explicitly requires it and the
  behavior is documented.
- Do not commit secrets, tokens, local machine paths used as credentials, or generated
  private data.
- Use structured logging for diagnostics instead of `print`.

## Related Docs

- Environment notes: `ENVIRONMENT.md`
- Runtime/export flow: `RUNTIME_EXECUTION.md`
- Path-sensitive skill: `../.agents/skills/project-path-audit/SKILL.md`
