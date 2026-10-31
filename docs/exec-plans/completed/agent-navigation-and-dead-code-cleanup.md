# Agent Navigation And Dead Code Cleanup

Status: Completed

## Scope and success criteria

The user requested removal of proven dead code and outdated instructions, with a
smaller, current navigation route for agents. Preserve behavior, schemas, public
compatibility surfaces, protected legacy boundaries and user-owned untracked files.
Do not remove a callable with active callers or a persisted/public interface.

The entry route is root `AGENTS.md`, one scope in `docs/agent/agent-index.md`, the
governing package guide, and one relevant contract section. `ARCHITECTURE.md` remains
the package/dependency map. Detailed recipes are optional, searchable context.
Target maximums are 800 words for root guidance, 1,000 for architecture and 1,200
for the index, reducing their combined baseline of 10,319 words substantially.

## Work and verification

1. Audit source references and current documentation before deleting code or rules.
   Keep unresolved candidates and external acceptance honest.
2. Compact entry documents, fix stale ownership/phase instructions and route detailed
   workflows to their existing canonical documents.
3. Remove only independently verified unused internal code. Check direct, dynamic,
   GUI, packaging and compatibility uses as applicable.
4. Run affected focused scopes, documentation/harness checks and repo precommit.
   No Qt execution is planned; use an approved visible environment only if needed.
   Report any remaining check limits.

## Progress

- Initial repo/harness baseline: 65 tests pass.
- Documentation baseline: root 988 words, architecture 4,427, agent index 4,904;
  the separate planning map contains 1,332 words, mostly completed-history entries.
- Audit found implemented migration, engine and exporter services described as
  future scaffolding, plus obsolete separate-project-only update guidance.
- Removed 173 lines of unreachable production code: obsolete text-height helpers,
  unused participant/session models and path helper, two unused GUI methods, the
  superseded output-label allocator, an old fixation-color helper, unused outbox
  deletion and three orphan constants. Removed only allocator-specific tests and
  obsolete fixture wiring; current behavior tests remain.
- Reference checks covered imports, Qt bindings, dynamic names, registries, packaging,
  active docs/tests and user-owned scratch/example files. The final non-GUI sweep
  covered 173 modules. Explicit compatibility APIs, registry introspection, retained
  standalone editors, active legacy label parsing and atomic visit reservations stay.
- Entry words: root 595, architecture 869, task index 590 (2,054 combined, down
  80.1%); the inherited source guide is 127 words. Topic recipes are optional.
- Scoped guides now describe implemented owners instead of future scaffolding;
  PLANS lists active work and remaining gates without a completion changelog.
  The old v1 spec is archived, with its old path retained as a short current-contract
  pointer. Skills no longer force full legacy-spec or workflow reads.
- Added harness checks for entry word budgets, verification-scope routing and local
  navigation links. All 41 entry/recipe section anchors also resolve.
- Affected non-Qt tests: 371 pass, one Windows symlink-privilege skip. Docs focused:
  13 pass. Repo focused: 68 pass.
- Clean QA precommit: 4,392 pass, 13 Windows symlink-privilege skips and 24 subtests
  pass. Changed-file Ruff/compilation, mypy across 261 source files, import boundaries
  and repository/doc audits pass. Log: `build/agent-cleanup-precommit.log`.
- The previously identified 1,500-session retirement stress test was explicitly
  deselected; it was not claimed as verified. No Qt or hardware execution was needed.
  User-owned untracked files were preserved. Other active plans retain their real
  external/manual acceptance gates.
