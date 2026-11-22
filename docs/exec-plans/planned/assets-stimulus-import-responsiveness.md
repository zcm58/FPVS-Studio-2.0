# Responsive Assets stimulus folder import

Status: Planned

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
