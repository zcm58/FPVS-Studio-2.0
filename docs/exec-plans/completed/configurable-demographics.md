# Configurable demographics

Status: Completed

## Workflow and acceptance

Place **Demographics** between Project and Conditions in Setup. The researcher
can add, edit, remove and reorder questions or restore the four Studio defaults.
Keep the ordered list, row actions and Setup navigation usable at `1120x820`,
including an empty questionnaire and long question wording. Apply edits through
the project document and persist them with the normal Setup save action.

Use the saved order in Participant Information for normal and AB Pilot launches.
Keep participant number and electrode review separate. Support single-line text,
age, multiple choice and yes/no. Each configured question requires an answer.

## Implementation and verification

Persist definitions in the project and snapshot each prompt and typed answer at
launch. Keep earlier visits independent of edits, preserve the fixed demographics
for unchanged Studio questions, and retain custom answers in the same project
participant workbook. Keep custom responses out of remote reporting.

Verify project and answer round trips, earlier project and visit compatibility,
workbook regeneration and launch wiring. Register minimum-size Setup and dialog
smoke coverage. Run focused checks and safe precommit. Visible Qt execution needs
approval for a safe visible environment.

Project and config round trips, launch snapshots, and workbook regression tests
passed. Registered Qt coverage was added for Setup and Participant Information.
Visible acceptance remains available through the documented
[manual smoke path](../../GUI_WORKFLOW.md#demographics-setup).
