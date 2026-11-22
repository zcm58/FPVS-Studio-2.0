# Participant Workbook Wrap Cache

Status: Completed

## Workflow and Evidence

Studio regenerates the participant workbook after research commits or when a
user opens results that need refresh. Its [layout code][layout] measures
identical text at identical available widths across cells and fitting passes.
A synthetic export with 24 visits and four conditions made 119,563 wrap
calculations on the baseline and had 862 cache misses with the prototype.
Across four paired runs through `write_participant_summary`, median elapsed
time went from 4.128 to 3.935 seconds. All 16 workbook ZIP members matched
byte for byte with timestamps held fixed.

## Implementation Boundary

Use a bounded cache for the existing `_wrapped_lines` calculation, keyed by
the exact rendered text and exact available width. Share it within one
workbook fit, including any generated disclosure sheets, then discard it so
participant text is released with the export. Keep the existing width
arithmetic, formatting and fitting decisions. Preserve the [export
contract][exports], including original values, sheet layout, disclosure
parts and hyperlinks.

## Verification

- Compare all workbook ZIP members through `write_participant_summary` with
  fixed timestamps. Include mixed fonts and widths, wide Unicode, explicit
  line breaks and long text that needs disclosure.
- Measure elapsed time, wrap calculations and peak memory for repeated text
  and mostly distinct text in small and large exports. Check that consecutive
  exports release the cache and isolate participant data.
- Use the existing [workbook layout tests][layout-tests], the focused runtime
  check and safe precommit verification.

## Implementation

A workbook fit shares one least-recently-used cache across its sheets and any
generated disclosure. Standalone worksheet fits create their own cache. Each
cache holds up to 1,024 entries and admits lines of up to 512 characters. The
key uses the exact rendered line and available width. Each fit releases its
cache on return.

Focused coverage checks rendered number formats, exact widths, sharing across
sheets and disclosures, separate fit lifetimes, eviction and long-line bypass.
An independent workbook comparison with fixed timestamps matched every ZIP
member for workbook fit, workbook refit and standalone worksheet fit. Its
synthetic cells included mixed font sizes, bold text, formatted numbers, wide
and combining characters, mixed line endings and a linked disclosure.

## Export measurements

These paired runs used `write_participant_summary` on Windows. Small fixtures
had three visits and two conditions, with 48 answers. Large fixtures had 24
visits and four conditions, with 1,536 answers and 1,344 fixation responses.
Every emitted XLSX matched byte for byte with workbook and ZIP timestamps fixed,
including all 16 archive members and the linked full-text disclosure.

| Fixture | Median export before | Median export after | Wrap evaluations before → after |
| --- | ---: | ---: | ---: |
| Small, repeated | 119 ms | 111 ms | 5,556 → 626 |
| Small, mostly distinct | 225 ms | 195 ms | 5,591 → 840 |
| Large, repeated | 5.540 s | 4.963 s | 154,284 → 963 |
| Large, mostly distinct | 5.506 s | 5.187 s | 155,435 → 10,395 |

The cache was faster in all six measured pairs for each large case and in nine
of ten pairs for each small case.

Peak traced Python allocation rose by 3 KiB and 37 KiB for the small cases,
and by 208 KiB and 218 KiB for the large cases. The largest absolute increase
was 218 KiB, or 0.55% of that export's peak. Consecutive exports released the
cache after each fit and reproduced the same wrap evaluation count and XLSX bytes.

The focused runtime route passed 1,172 tests with four Windows symlink-privilege
skips. It includes the workbook layout and participant result tests.
Safe repo precommit passed Windows and Darwin type checks, repository audits,
and 6,612 tests with 41 platform or permission skips.

[layout]: ../../../src/fpvs_studio/runtime/workbook_layout.py
[exports]: ../../RUNTIME_EXECUTION.md#exports
[layout-tests]: ../../../tests/unit/test_workbook_layout.py
