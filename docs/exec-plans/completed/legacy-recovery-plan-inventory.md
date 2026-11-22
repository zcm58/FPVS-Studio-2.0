# Legacy Recovery Plan Inventory

Status: Completed

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

## Implementation and results

Discovery keeps a bounded cache of validated legacy match signatures for one
query. Each candidate still goes through the original path checks in the same
order. A cache hit requires an unchanged filesystem stamp, including native
change time on Windows. Invalid or unstampable files still go through the
reader. The rerun builder reads the selected plan afresh.

With 24 real legacy plan files of approximately 2.8 MB and eight unmatched
requests, bounded reads fell from 192 to 24 and median discovery time fell from
17.496 to 2.656 seconds across eight paired trials. Recovery reports and
warnings matched exactly. Single dedicated-plan and early legacy-match timings
were within measurement noise. Peak traced allocations rose from 143,791,889
to 143,839,584 bytes in the large case.

Regression cases cover dedicated and first legacy match precedence, malformed
files, Windows junction redirects, same-size replacement, and a plan changed
between discovery and the authoritative rerun. A Windows probe also confirmed
cache invalidation after an in-place rewrite that preserved file size and restored
mtime. Runtime focused verification passed 1,180 tests, including the existing
recovered-schedule assertions, with four Windows symlink-permission skips.

Repo precommit passed both platform type checks, repository audits, and 6,619
unit tests with 41 skips. The existing Windows serialization test recorded an
extra retry from the real file replacement, as in the previous workbook change.
All 10 serialization tests passed on immediate focused rerun. Docs focused
verification passed all 13 checks.

[recovery]: ../../../src/fpvs_studio/runtime/condition_recovery.py
[contract]: ../../RUNTIME_EXECUTION.md#interrupted-condition-recovery
[tests]: ../../../tests/unit/test_condition_recovery.py
