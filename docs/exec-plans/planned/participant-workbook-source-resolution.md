# Participant Workbook Source Resolution

Status: Planned

## Workflow and Evidence

Studio gathers participant records from the active project when rebuilding
its results workbook. The [record reader][records] resolves the same project
root again for each source. The separate workbook freshness scan already uses
one [`ProjectPathResolver`][paths] per operation. In a 200-visit export, a
prototype reduced total project-root resolutions from 204 to two, including
the lock's separate resolution. All 15 workbook ZIP members matched with
fixed timestamps. Median export time moved from 0.825 to 0.770 seconds in the
synthetic runs with substantial timing variation.

## Implementation Boundary

Reuse one resolver within `_records` and the readers it calls as appropriate.
Create a fresh resolver on each operation, retaining fresh target resolution
and containment checks on every lookup. Preserve the workbook lock, source
order, full and compact legacy records, pending-journal handling and explicit
errors. Keep the workbook's atomic replacement behavior on read or write
failure. Use the workbook entry point and check other callers of `_records`,
including retained-output maintenance and read-only result queries.

## Verification

- Compare workbook ZIP members with fixed timestamps across current, legacy
  and mixed projects. Verify missing optional journals are skipped as before
  and the previous workbook survives errors from unreadable journals, invalid
  records or escaping paths.
- Check redirects made between operations, target containment during lookup,
  Windows long paths, and source order. Measure root and target resolutions as
  well as elapsed time on small and large projects.
- Use the [participant results tests][tests], focused runtime and project I/O
  checks, and safe precommit verification.

[records]: ../../../src/fpvs_studio/runtime/participant_results.py
[paths]: ../../../src/fpvs_studio/core/paths.py
[tests]: ../../../tests/unit/test_participant_results.py
