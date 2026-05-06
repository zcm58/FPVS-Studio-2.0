# Execution Plans

Use this directory for feature-sized work that changes user workflows, public
contracts, or multiple layers of the application.

Before implementing a new feature or substantial GUI rework:

1. Draft future plans in `docs/exec-plans/planned/` when they are useful but not yet
   approved for implementation.
2. Move approved implementation work to `docs/exec-plans/active/`.
3. State the user workflow, implementation boundaries, tests, and assumptions.
4. Keep the plan current as decisions change.
5. Move completed plans to `docs/exec-plans/completed/` after the work lands.
6. Use `docs/exec-plans/tech-debt-tracker.md` for debt items that may become
   execution plans.

Small bug fixes and narrow refactors do not need an execution plan.

Run `.\scripts\check_docs_hygiene.ps1` during garbage-collection passes to review plan
status, root-doc clutter, and archived historical docs.
