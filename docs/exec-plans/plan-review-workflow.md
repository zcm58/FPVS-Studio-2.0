# Execution Plan Review Workflow

Use this workflow during harness garbage-collection passes or before starting
feature-sized work.

## Steps

1. Check the workspace state:
   - `git status --short`
2. Review the plan inventory:
   - `.\scripts\check_docs_hygiene.ps1`
3. Read the current planning map:
   - `docs/PLANS.md`
   - `docs/exec-plans/README.md`
4. Review active plans in `docs/exec-plans/active/`:
   - confirm each plan has a `Status:` line
   - confirm the plan still describes unfinished work
   - move completed plans to `docs/exec-plans/completed/`
5. Review planned plans in `docs/exec-plans/planned/`:
   - keep only concrete future work
   - move approved work to `active/`
   - delete or archive vague ideas that no longer match product direction
6. Review root `docs/*.md`:
   - keep hub docs and current contract docs at the root
   - move old prompts, scaffold notes, and historical audits to `docs/references/archive/`
   - update `docs/index.md` after any move
7. Run verification:
   - `python -m pytest -q tests\unit\test_harness_docs.py`
   - `.\scripts\check_gc.ps1`

## Active Plan Status Rules

- `Status: Active` means implementation or review is still in progress.
- `Status: Planned` belongs in `planned/`, not `active/`.
- `Status: Completed` belongs in `completed/`.
- `Status: Archived` belongs in `docs/references/archive/` only when the plan is
  historical context rather than future work.
