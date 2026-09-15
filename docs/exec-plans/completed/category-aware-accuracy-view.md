# Category-aware accuracy view

Status: Completed

## User workflow

View offers **T1 and T2 Accuracy** for Attentional Blink and **Fixation Task
Accuracy** for other categories. Reuse the existing AB report, showing T1/T2
correct/answered counts and percentages for each SOA with its recorded condition
trigger codes. The default rows are 100/300/500 ms with codes 1/3/5.

## Boundaries

- Main window selects the report from the locked project category.
- Runtime owns SOA summaries and actual recorded trigger-code lists; GUI and Excel
  consume the same summaries. Preserve scoring, partial answers and test inclusion.
- Replace the old Tools AB entry with the category-aware View action. Preserve the
  fixation report, worker lifecycle, project handoff guards and recorded data.

## Verification

- Registered Qt checks cover category routing and compact table content/layout at
  920x600 and 1080x680. Native Qt remains a documented visible smoke check.
- Non-Qt tests cover actual/custom trigger codes, accuracy and matching workbook
  summaries. Run GUI focused checks and repo precommit, then hash-verify delivery.

## Results

- One View action selects the label and report from the locked project category.
  AB uses T1 and T2 Accuracy; FPVS / Oddball use the existing fixation report.
- The seven-column AB summary shows actual trigger codes alongside SOA, burst
  count, and independent T1/T2 correct/answered counts and accuracy percentages.
  Both Excel SOA summaries include the same recorded codes. Data formats and
  scoring are unchanged, including test sessions and partial responses.
- GUI focused checks passed. Repo precommit passed with 1,581 tests and seven
  Windows symlink skips; Ruff, compilation, mypy and repository audits passed.
- Registered Qt tests cover AB/non-AB routing, compact table headers and full
  access to long trigger-code lists. Visible Qt checks were not run.
- A read-only query of MSMS's saved bursts left all 56 study files unchanged.
  Delivery updates the verified source files only; no installer was rebuilt.
