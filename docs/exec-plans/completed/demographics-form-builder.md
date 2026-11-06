# Demographics form builder

Status: Completed

## Workflow

Use a Forms-style editor in Setup > Demographics. A question outline controls the
selected inline card. The researcher can edit the prompt and type, add choice rows,
mark a question required, duplicate or remove it, and change the order. Restore
defaults recovers the original Studio questionnaire. Preview renders the participant
controls and checks required answers before the researcher saves Setup.

The selected scope is short answer, paragraph, multiple choice, checkboxes, dropdown,
linear scale, rating, date, and time. Keep Age and Yes or No available. The `1120x820`
Setup workspace fits the authoring actions and selected card, with scrolling inside
the outline or option list when needed. Check empty, invalid, restored, and long
question states. Use the registered `600x360` participant dialog smoke path for preview
and launch, including both required and optional answers.

## Contracts and verification

Extend the existing project questionnaire and participant snapshots. Default required
flags and omitted new options keep earlier definitions readable. An unanswered optional
question keeps its wording and position, with a blank result cell. Checkboxes retain
their selected labels as a list and display one selection per line in the existing
participant workbook. Scale and rating answers are numeric. Date and time use ISO text.

Verify project and config round trips, all response types, invalid input, workbook
regeneration from full and compact output, and the safe repo precommit suite. Register
Qt smoke coverage and document visible acceptance separately.

Project I/O and runtime focused checks passed. Registered Qt coverage exercises the
card editor, invalid drafts and participant preview. See the
[manual smoke path](../../GUI_WORKFLOW.md#demographics-setup) for visible acceptance.
