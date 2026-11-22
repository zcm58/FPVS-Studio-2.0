# Studio backend efficiency audit

Status: Completed

## Scope

Measure local Studio workflows that delay authoring, experiment preparation or
results export. Check the existing compile, asset scan, workbook and study
handoff entry points with synthetic project data. Keep persisted formats, errors,
validation, output order and deterministic bytes intact. Preserve acquisition
and rendering boundaries.

## Session compilation

Canonical project-relative POSIX paths avoid constructing two `pathlib` objects.
Alternate spellings and invalid paths still go through the existing parser, and
the active project root and resolved containment checks are preserved. A comparison
of 21,772 generated or typed inputs returned the same strings or errors.

Using on-disk assets and fixed seeds, 18 alternating benchmark pairs reduced
median `compile_session_plan` time from 251 ms to 196 ms for 3,600 image events,
and from 703 ms to 585 ms for 8,640 image events. Word compilation was effectively
flat. Serialized session plans matched byte for byte, including the schedules,
randomization and fixation events. Compiler focused verification passed 815 tests.
Project I/O focused verification passed 913 tests with three Windows privilege skips.

## Image readiness scan

Setup scans still decode each image and apply EXIF orientation. Pillow now applies
orientation in place, which avoids copying the full pixel buffer for unchanged
orientations. Six alternating Windows runs per build used the same synthetic
source files and a warm filesystem cache.

| Fixture | Baseline median | Updated median | Full pixel copies |
| --- | ---: | ---: | ---: |
| 400 JPEGs at 512 × 512 | 1.428 s | 1.300 s | 400 to 0 |
| 90 JPEGs at 2,048 × 2,048 | 4.202 s | 3.818 s | 90 to 0 |
| 26 BMPs at 2,048 × 2,048 | 0.564 s | 0.455 s | 26 to 0 |

Scan results matched on all fixtures. JPEG and PNG EXIF orientations 1–8 produced
the same scan results and normalized PNG hashes. A truncated JPEG raised the same
error. TIFF checks covered 56 mode/orientation combinations and Windows file release.
Preprocessing focused verification passed 94 tests.

## Participant Results workbook

Workbook generation reuses identical openpyxl styles, applies numeric formats
only in columns that use them, and caches individual glyph widths. Glyph widths
are still added in their original order. A comparison spanning the Unicode code
point range returned identical floating-point width bits.

| Fixture and operation | Baseline median | Updated median | Measurement pairs |
| --- | ---: | ---: | ---: |
| First write, 1 visit with 4 conditions | 0.261 s | 0.199 s | 12 |
| Regeneration, 60 visits with 4 conditions each | 12.650 s | 9.138 s | 5 |
| Regeneration with long-text disclosure, 2 visits | 0.622 s | 0.440 s | 3 |

The Windows `write_participant_summary` benchmark included reading the same
retained research and history, saving and replacing the workbook. Every XLSX
member matched byte for byte with creation and modification times held fixed.
Fixtures included multiline and formula-like text, combining marks, wide Unicode,
number formats, row and column sizing, and long-answer links. The timing series
overlapped the runtime focused suite and alternated baseline and updated order.

## Whole-study Toolbox handoff

The export now indexes participant, visit number and session identity once while
combining retained acquisition evidence and historical rows. It preserves the
same treatment of numbered repeats, unnumbered historical records, test/pilot
visits and conflicts with retained acquisition evidence.

Exact `.fpvsconfig` bytes and roster order matched on the first export and four
repeat exports per build. The 750-visit numbered-history fixture fell from 234 ms
to 33 ms on first use and from 231 ms to 33 ms on repeat median. Visit identity
constructions fell from 563,250 to 1,500. With 1,500 numbered visits, repeat medians
fell from 1,539 ms to 133 ms and identity constructions from 2,251,500 to 3,000.
On the mixed 750-visit fixture with 375 retained private records, repeat medians
fell from 990 ms to 519 ms. The large and mixed timings varied under concurrent
local test load.

## Remaining candidates

A Windows `os.scandir` prototype reduced median inventory time for 5,000 ordinary
local files from 1,334 ms to 46 ms. The fixture retained ordering and Finder metadata
filtering. Windows reparse points, permission errors and changes during enumeration
still need parity tests.

Profile Manage Projects on a root with many studies. Its background inventory reads
study identity and saved-version count through separate database opens for each
project. A single read would need to preserve the handling of legacy tables and
damaged databases. Setup-save validation deliberately rereads project and manifest
state across the review step to detect intervening edits.

## Verification

Runtime focused verification passed 1,168 tests with four Windows permission
skips. The three direct whole-study handoff tests passed. The four-worker repo
precommit run passed lint, compilation, Windows and Darwin type checks, repository
audits and 6,580 non-Qt tests, with 41 platform or permission skips. The
1,500-session reporting archive test passed in 212 seconds. The benchmark covers
backend commands and functions. Visible desktop latency and physical display and
EEG timing were outside this pass.
