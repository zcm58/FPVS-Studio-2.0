# Legacy Recovery Plan Inventory

Status: Planned

## Workflow and Evidence

The interrupted-condition view enables a rerun when the recorded occurrence
matches a frozen plan. When a dedicated recovery plan is missing,
[`_original_plan`][recovery] scans legacy `runs/*/session_plan.json` files for
each eligible record. A synthetic discovery probe with 24 plan paths and
eight unmatched requests called the bounded reader 192 times with plan
validation stubbed. Reading each unchanged candidate once would reduce that
count to 24 in this case. The probe measured read calls, with parsing and
elapsed time still to be measured.

## Implementation Boundary

Build the legacy candidate inventory lazily within one `query_condition_recovery`
call. Reuse each validated candidate's match data for later lookups while
preserving candidate order, first match and dedicated-plan precedence. Keep
the size limit and project containment checks. If a candidate changes or
redirects during discovery, use the existing lookup on that path. Limit
retained state to discovery and keep the authoritative plan recheck in
`build_recovery_session_plan`.

## Verification

- Compare reports, warning text and read-only behavior for dedicated plans,
  duplicate legacy matches, malformed or oversized plans, redirects and
  missing files. Check file replacement between discovery and rerun.
- With real plan parsing, measure read and validation calls, elapsed time
  and memory across early matches and many unmatched records. Cover ordinary
  projects that have dedicated plans and can skip the fallback.
- Check that a recovered occurrence preserves its exact compiled schedule.
  Use the [runtime recovery contract][contract], existing [condition recovery
  tests][tests], focused runtime verification and safe precommit checks.

[recovery]: ../../../src/fpvs_studio/runtime/condition_recovery.py
[contract]: ../../RUNTIME_EXECUTION.md#interrupted-condition-recovery
[tests]: ../../../tests/unit/test_condition_recovery.py
