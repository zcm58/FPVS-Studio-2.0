# Desktop panel hierarchy

Status: Complete (source and visible Windows smoke at 100% scaling)

## Workflow and acceptance

Review how borders and surfaces group content in the desktop authoring workflow,
project and condition dialogs, Library, Run, and representative tools. Use headings,
alignment and dividers for section structure. Keep visible boundaries for interactive
lists, editors, preview canvases, and consequential notices where the boundary helps
people locate or interpret content.

Keep existing actions, keyboard behavior, theme roles, and data contracts. Reuse the
shared PySide6 layout and theme helpers. Check both themes at each affected surface's
minimum size with long paths, empty states, and populated content. Run registered
Qt smoke tests in serial batches on the approved Windows desktop and run the
repository's source checks.

## Audit and changes

| Surface | Finding and change |
| --- | --- |
| Home and Setup | Home readiness is inline. Setup keeps a frameless workspace, with headings and dividers for Review and flat condition and demographic editors. Separate source panes, project forms and previews retain their own boundaries. |
| Run and reports | Run uses a single workspace with headings and bounded read-only details. Accuracy reports give tables the available space and show status for loading, failures and exports. |
| Project and condition dialogs | Manage Projects places details beside the list. Bundle options, import review, display matching, modifier forms and presentation settings use flat sections within the dialog or tab. Section headings inherit the dialog's text colors. Interactive lists and the presentation canvas retain a boundary. |
| Bundle transfer | Each progress or result view uses one frame. At compact width, progress stages fit, and the result shows all its contents and actions. Long paths elide by width and retain the complete value in accessible text and tooltips. |
| Tools and Library | Condition Figure keeps boundaries around the five previews. Library, Image Resizer and Trigger Tester already group their controls in a single workspace. |

## Verification

The registered visible Qt cases covered Light and Dark in native Windows Qt at
100% scaling. Home fit at 760 × 520. All nine Setup steps fit at 1120 × 820,
including native attentional blink variants. Bundle progress and result fit in the
compact Home workspace and at default size. The modal import progress, project and
condition dialogs, Run, Condition Figure and reports were exercised at their own
minimum sizes. Test data included long paths, incomplete projects, populated
tables, partial recall and an Excel export failure with results still visible.

Repository precommit passed during the audit with 6,237 unit cases passing and 34
platform and environment skips. The final UI changes also passed focused GUI and
docs verification, type checking and the visible regression cases.
