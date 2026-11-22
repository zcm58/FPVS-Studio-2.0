# Participant Workbook Wrap Cache

Status: Planned

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

[layout]: ../../../src/fpvs_studio/runtime/workbook_layout.py
[exports]: ../../RUNTIME_EXECUTION.md#exports
[layout-tests]: ../../../tests/unit/test_workbook_layout.py
