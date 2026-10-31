# FPVS Studio Documentation

This directory is the structured documentation entry point for future FPVS Studio
development. Keep stable source-of-truth docs here, and keep the compact repo map in
`../ARCHITECTURE.md`.

These are internal developer and agent-facing docs, not the public user guide. The
public quickstart site lives in `../docs-site/` and is built with MkDocs.

## Choose A Task

- Agent and architecture context: `../AGENTS.md` and `../ARCHITECTURE.md`
- Task scopes, skills, and verification routes: `agent/agent-index.md`

Agents should choose one scope and one relevant contract section there. The topics
below are a catalog, not a required reading list.

## Product And Workflows

- Product direction: `PRODUCT_SENSE.md` and `product-specs/index.md`
- Design and GUI workflow: `DESIGN.md`, `FRONTEND.md`, and `GUI_WORKFLOW.md`
- Experiment categories and legacy separation: `EXPERIMENT_CATEGORIES.md`
- Cognitive Load FPVS and reusable backward counting: `COGNITIVE_LOAD_FPVS.md`
- Condition modifiers, memory workflows, and local presets: `CONDITION_MODIFIERS.md`
- Simple questions and readable response CSV: `POST_CONDITION_QUESTIONS.md`
- Packaging developer builds: `PACKAGING.md`
- Execution planning: `PLANS.md`, `exec-plans/README.md`, and
  `exec-plans/plan-review-workflow.md`
- Quality, reliability, and security: `QUALITY_SCORE.md`, `RELIABILITY.md`, and
  `SECURITY.md`
- Bug/feature reports and automatic crash diagnostics: `BUG_REPORTING.md`
- Private whole-experiment library and publishing: `EXPERIMENT_LIBRARY.md`
- Signed Library bundle evidence and immutable releases: `LIBRARY_ARTIFACT_PROVENANCE.md`
- Experiment contribution preferences and comparisons: `DATA_SHARING.md` and
  [active acceptance plan](exec-plans/active/remote-experiment-results-reporting.md)
- Completed Studio/Toolbox handoffs and shared-study integration:
  [active integration plan](exec-plans/active/studio-toolbox-integration.md)

## Runtime Contracts

- Engine boundary: `ENGINE_INTERFACE.md`
- Run contract: `RUNSPEC.md`
- Session contract: `SESSION_PLAN.md`
- Runtime/export flow: `RUNTIME_EXECUTION.md`

## Supporting Areas

- Design docs: `design-docs/index.md`
- Generated references: `generated/README.md`
- External/reference material and archived setup/audit docs: `references/index.md`
- Technical debt: `exec-plans/tech-debt-tracker.md` (`TECH_DEBT.md` is a compatibility
  pointer)
- Completed execution plans: `exec-plans/completed/`
