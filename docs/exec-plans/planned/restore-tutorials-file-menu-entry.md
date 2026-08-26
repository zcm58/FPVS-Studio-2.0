# Restore Tutorials File Menu Entry

Status: Planned

## Objective

Restore the existing `File > Tutorials` entry after the public tutorial section is
complete and ready for users. The underlying QAction, URL, and browser-opening callback
remain implemented while the entry is hidden.

## Scope

- Complete and verify the public tutorial content at the existing tutorials URL.
- Make the existing `tutorials_action` visible in the File menu again.
- Update the GUI workflow documentation to describe the restored entry.
- Update registered pytest-qt coverage to require the visible action and confirm that it
  opens the existing URL.

## Boundaries

- Do not replace the tutorials URL or create a second QAction unless requirements change.
- Do not alter the participant fixation-tutorial setting, runtime tutorial state machine,
  or tutorial data contracts; those are separate functionality.
- Preserve the current File-menu grouping and the existing browser-opening callback.

## Acceptance

- `Tutorials` is visible exactly once in the File menu.
- Activating it opens the completed public tutorial site through the existing callback.
- Registered GUI coverage passes in CI, and the safe GUI/docs verification scopes pass
  locally.
