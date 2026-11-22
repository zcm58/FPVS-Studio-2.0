# Participant Workbook Source Resolution

Status: Completed

## Workflow and Baseline Evidence

Studio gathers participant records from the active project when rebuilding
its results workbook. The baseline [record reader][records] resolved the same
project root again for each source. The separate workbook freshness scan already uses
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

## Implementation

Workbook source reads share one project resolver across captured records,
pending journals, legacy full results, historical question context and compact
CSV data. Retained-output maintenance and read-only visit lookup also create a
resolver for each invocation. Each lookup still resolves the target and checks
containment. A new operation resolves the current root. The workbook reporting
lock, record order and atomic workbook replacement use their existing paths.

## Output and performance verification

All six Windows fixtures exported identical XLSX bytes and 15 matching ZIP
members with workbook and ZIP clocks fixed. Current, legacy and mixed fixtures
kept the same worksheet source order. Every logical lookup still resolved its
target in the same order, and the reporting lock retained its own root and
target lookup.

| 200-visit fixture | Project-root resolutions before → after | Target resolutions | Median export before → after |
| --- | ---: | ---: | ---: |
| Current | 204 → 2 | 204 | 1.518 → 1.399 s |
| Legacy | 638 → 2 | 638 | 2.115 → 1.888 s |
| Mixed | 449 → 2 | 449 | 1.875 → 1.644 s |

The candidate was faster in all six pairs for each large fixture. In the three
four-visit fixtures, root resolutions fell from 8, 17 and 16 to two, and paired
median times fell by 1.35, 1.68 and 18.67 ms respectively. Small wall times varied
with the Windows host, including a higher unpaired median for the legacy case.
An additional 32 alternating pairs for the small legacy fixture lowered the
median from 65.59 to 63.41 ms, with a paired improvement of 2.41 ms and 24 faster
candidate runs. The paired median improved in both run orders.

Windows junction tests exercised a project-root redirect between workbook
rebuilds and an initially contained journal redirected outside the project.
The second project supplied the next workbook's answers. The escaping journal
raised the existing containment error and left the previous output intact.
Missing journals produced the existing blank answer sheet. Unreadable and
malformed journals and unsupported record versions preserved the previous
workbook. A 331-character source path exported matching XLSX bytes.

Runtime focused verification passed 1,175 tests with four Windows symlink-privilege
skips. Project I/O focused verification passed 921 tests with three skips for the
same reason.

The first safe repo precommit run saw a transient fourth file-replace attempt
in the existing Windows serialization retry test. All ten serialization tests
passed on focused rerun. A full precommit rerun passed the Windows and Darwin
type checks, repository audits and 6,615 unit tests with 41 platform or
permission skips.

[records]: ../../../src/fpvs_studio/runtime/participant_results.py
[paths]: ../../../src/fpvs_studio/core/paths.py
[tests]: ../../../tests/unit/test_participant_results.py
