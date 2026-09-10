# Retire Attentional-Blink Image Pairs

Status: Complete

## Approved scope

Remove image-pair designs from the Attentional-Blink product. Only the native
10 Hz digit/letter study remains available. Rename the disabled base-only category
to Standard FPVS and the oddball category to FPVS Oddball Paradigm, retaining
persisted enum values and existing project IDs.

Old image-pair records remain readable for identification and historical records;
do not convert their stimuli/timing or delete user assets. Reject retired layouts
at authoring, template application, compilation and runtime preflight. Remove them
from built-in and custom template choices. Existing oddball behavior and the previous
frameless Setup changes must remain intact.

## Verification

Cover the category labels, disabled placeholder, one supported AB template, rejection
of custom image-pair templates and old projects/runs, preservation of files, and
successful native AB creation/compilation. Update obsolete image-pair acceptance tests
to retirement coverage. Use core/GUI/runtime focused checks and repo precommit;
visible Qt checks are already authorized, with no real PsychoPy or hardware launch.

## Completed result

- Removed the built-in image-pair template and excluded saved custom copies from
  all template pickers and the manager. Direct application/upsert is rejected.
- AB condition creation, duplication/control creation and image-design application
  cannot create retired layouts. Design shows a retirement explanation for old files.
- Removed the compound-slot compiler. Saving, configuration/bundle validation and
  compilation reject retired projects. Runtime preflight and direct engine launch
  reject old RunSpecs before playback; model decoding and source files are retained.
- Display names are Standard FPVS (disabled Coming soon), FPVS Oddball Paradigm,
  and Attentional-Blink. Enum values, existing project IDs and folders are unchanged.
- Native 10 Hz letter streams retain the 100/300/500 ms default SOAs, randomized
  digits, target colors, questionnaires and optional fixation cross.

## Verification results

- Precommit checks: Ruff, compilation, mypy (150 source files), repository and docs
  audits passed; unit suite 1244 passed, five Windows symlink privilege skips.
- The stock driver includes deleted files in its lint list. Ran the same driver
  in process with nonexistent changed paths excluded; no harness file was edited.
- GUI/core/runtime focused routes passed using that same deleted-path exclusion:
  core 329 passed/one symlink skip; runtime 224 passed; GUI static checks passed.
- Visible Qt: updated category and Design modules 26 passed; native stream tests
  plus locked Project template selection 18 passed/four unrelated all-step cases
  deselected. Oddball designer and fixation checks also passed. Category cards were
  checked at 760x500 in both themes; native Design at the documented wizard sizes.
- No real experiment or hardware-trigger run. Earlier frameless Setup edits remain
  in the working tree. No commit or push was requested for this change.

Visible smoke path: restart Studio, choose New Experiment, inspect the three category
names, choose Attentional-Blink, confirm only Digits & letter targets is offered,
then inspect the three default SOAs in Design. An archived image-pair project should
show the unsupported-design explanation and refuse saving/running without rewriting it.
