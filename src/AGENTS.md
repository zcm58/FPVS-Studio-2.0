# Source Tree Guidance

Root `AGENTS.md` supplies global boundaries. Before editing production code, read
only the governing package guide and the relevant contract section selected by
`docs/agent/agent-index.md`. Use `ARCHITECTURE.md` for ownership, not broad source scans.

- Preserve existing JSON, compiled contracts, exports and public imports unless the
  user explicitly requests a contract change. Audit dynamic/GUI/packaging callers
  before removing apparently unused code.
- Project category is immutable and categories cannot mix. Category defaults,
  supported presentation modes and retired AB image-pair behavior are canonical in
  `docs/EXPERIMENT_CATEGORIES.md`; use current models rather than old phase guidance.
- Generated assets and task media stay project-contained; app-level templates/presets
  stay under the configured root's `.fpvs-studio/templates/`.
- Preserve backend ownership and existing document/controller bindings for user-facing
  changes. Ambiguous behavior requires evidence, not a hidden fallback.
