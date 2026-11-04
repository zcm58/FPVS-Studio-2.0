# Results workbook automatic sizing

Status: Completed

## Outcome

Fit column widths and wrapped row heights whenever the combined participant workbook
is generated or refreshed, including appended visits. Keep centered text, typed values,
existing research records and the project-relative `logs/participant_summary.xlsx` path.
Apply the same sizing to the 13 existing result workbooks without changing their data.

## Boundaries

- Runtime owns content-based sizing across all six standard sheets. Size formatted
  values, headers, explicit line breaks, long identifiers and Unicode text.
- Expand columns when needed to keep rows within Excel's display limits. Preserve
  exceptionally long cell values and provide readable chunks in a conditional Full Text
  sheet; ordinary workbooks retain the six standard tabs.
- One results XLSX is generated automatically per project. Raw acquisition/recovery
  records remain separate, and explicit manual exports may produce additional XLSX files.
- Do not change scoring, session ordering, presentation, canonical research files or
  workbook cell values. Back up existing workbooks before the formatting-only update.

## Verification

- Exercise growing appended content, all sheets, centered defaults, numeric formats,
  multiline/Unicode text, long seed lists and Excel-limit text preservation.
- Run runtime focused checks and applicable safe repository checks.
- Compare existing workbook values before/after sizing and inspect rendered sheets,
  including the longest seed list. Record results and archive this plan on completion.
- Native Excel and Qt execution are not part of ordinary local verification.

## Completed evidence

- Runtime focused: 1,027 passed, four Windows symlink-capability skips. Repository
  precommit: 5,227 passed, 32 environment/platform skips; Ruff and Windows/Darwin
  mypy passed. Verification configuration passed for all 15 scopes.
- All 13 existing combined workbooks were backed up and resized. Cell values, types,
  numeric formats, centering and other formatting were verified unchanged; no existing
  value required a Full Text disclosure. The longest current seed list has 2,130
  characters and is fully visible after sizing.
- Rendered all six standard sheet types and the longest seed cell for visual review.
  Native Excel and Qt were not executed. The linked Full Text behavior for very long
  Unicode/multiline values is covered by saved-workbook tests.
- Formatting verification and backup are retained beneath the configured Studio Root's
  `.fpvs-studio/results-consolidation/`, with verification metadata named
  `autofit-verification-20261104T143832Z.json`.
