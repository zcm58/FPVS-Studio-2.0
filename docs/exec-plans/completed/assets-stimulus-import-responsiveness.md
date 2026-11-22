# Responsive Assets stimulus folder import

Status: Completed

Date: 2026-11-22

## Workflow and evidence

In Assets, the researcher selects an image source and chooses **Import Source
Folder…**. The [Assets handler](../../../src/fpvs_studio/gui/assets_pages.py)
calls `import_condition_stimulus_folder` on the GUI thread. The
[document method](../../../src/fpvs_studio/gui/document_stimuli.py) copies,
inspects and hashes the images before attaching the set and writing its manifest.
The import backend took 0.702 seconds in one synthetic run with 128 PNGs totaling
96.2 MiB. GUI latency and repeated-run timings still need measurement.

## Scope and behavior to preserve

Move the existing fresh-source copy and inspection into a worker. Capture the
active project root, document, condition, role, current set identity and name on
the GUI thread. Follow the prepare/apply pattern in
[Conditions Setup](../../../src/fpvs_studio/gui/condition_setup_step.py) and
retain the Assets set name when invoking the shared importer. Apply the returned
set and inspection summary through the existing document method on the GUI
thread. Keep other callers of the synchronous document method working.

Make mutation and teardown follow the existing busy-job lifecycle. Keep the
GUI event loop available during intake, prevent conflicting mutation of the
active project, and guard completion against stale projects or bindings. Keep
file-picker cancellation free of side effects. Preserve fresh project-contained
set allocation, selected-role assignment, the imported bytes, accepted mixed
resolutions, manifest contents, and error handling for missing, unsupported or
unreadable inputs. Normalization stays in its existing workflow.

Keep the compatibility Assets view out of guided navigation. Reuse the
background job used by Conditions intake to keep the existing picker and
results without adding another dialog.

## Verification

- Extend the [registered Assets checks](../../../tests/gui/test_assets_run_launch.py)
  for asynchronous completion, continued event-loop dispatch, and the existing
  successful and mixed-resolution cases. Cover picker cancellation, failures,
  concurrent actions and project switching or closure during the job.
- Compare copied file hashes and persisted set/manifest state for equivalent
  projects with the same allocation state. Measure elapsed time and the longest
  GUI event-loop gap during the large import and a small import.
- Run GUI, project I/O and preprocessing focused checks and repo precommit.
  In an approved visible Windows session, import from Assets at minimum and
  default window sizes, check that the window remains responsive and unclipped,
  and verify that the selected source and its status refresh on completion.

## Implementation and results

The existing app-owned worker copies, inspects, and hashes the source folder.
The GUI attaches the set through the original document path once the captured
condition binding, stimulus set, and physical project root still match. A stale
completion leaves the copied folder detached and does not update the project or
manifest. The same Setup guard blocks project handoff through worker cleanup.

Safe GUI focused verification passed 184 tests. Preprocessing passed 112 tests.
Project I/O passed 921 tests with three Windows symlink-permission skips.
Repo precommit passed both platform type checks, repository audits, and 6,622
unit tests with 41 platform or permission skips. Docs focused verification
passed all 13 checks.

The [native Windows QA run](https://github.com/zcm58/FPVS-Studio-2.0/actions/runs/45045953152)
passed all ten registered cases, including layout at 960 × 640 and 1120 × 720,
background event dispatch, picker cancellation, errors, and handoff. Stubbed
inputs supplied the picker paths and the expected busy and error dialogs. The
runner's desktop was 1024 × 768 with 96 DPI. The native widget was resized after
showing it to check the default layout geometry.

The same runner compared real copies and saved state using one warm-up and six
timed imports per size and revision. All copied PNG hashes and canonicalized
project and manifest data matched. The comparison verified and normalized the
random fresh-set suffix and the generated and imported timestamps.

| Source fixture | Median completion before → after | Median longest event-loop gap before → after |
| --- | ---: | ---: |
| 3 PNGs, 28,140 bytes | 13.74 → 16.48 ms | 13.78 → 9.71 ms |
| 128 PNGs, 100,804,096 bytes | 449.29 → 449.09 ms | 449.36 → 10.26 ms |

The first hosted run showed an 11 ms increase in large-import completion time.
During application of an import, the page now keeps its first synchronous
refresh and skips the duplicate notification for the same project and
manifest. The subsequent large-import median was effectively flat. The
user explicitly approved the measured 2.74 ms median completion cost for the
three-image import in exchange for the shorter event-loop gaps.
