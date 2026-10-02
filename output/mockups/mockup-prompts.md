# FPVS bundle import/export mockup prompts

All four mockups were generated with the built-in image-generation tool. The numerical
project metadata, paths, counts, file sizes, elapsed times, and ETAs are illustrative.

## Import review

Use case: `ui-mockup`

Create a high-fidelity, shippable PySide6 Windows desktop screen for FPVS Studio after
a user selects a `.fpvsbundle` and before files are copied. Preserve the current
light gray-blue visual system (`#f4f7fb` page, white elevated cards, `#1f2f44` text,
`#2563eb` primary, pale green success), native title/menu chrome, and practical Windows
sans-serif typography. Show `PROJECT IMPORT`, `Review project bundle`, the selected
`semanticcategories.fpvsbundle`, project/file metadata, an import destination, a
three-row explanation of what Studio will do, the no-overwrite/exclusions safety note,
and clear `Choose another file`, `Cancel`, and `Import Project` actions. Keep the layout
implementation-realistic, restrained, accessible, and free of web or decorative chrome.

## Import progress

Use case: `ui-mockup`

Create a high-fidelity, shippable PySide6 Windows desktop progress surface for a
long-running FPVS Studio project import. Preserve the existing palette but replace the
large spinner column with a centered professional card showing `PROJECT IMPORT`,
`Importing Semantic Categories`, source and destination paths, a determinate 52% bar,
`842 of 1,284 stimulus files`, a four-step tracker (`Verify bundle`, `Copy stimuli`,
`Create project`, `Confirm display`), current-file activity, elapsed time, ETA, and the
note `Keep FPVS Studio open until the import finishes.` Do not show cancellation because
the current workflow has no safe cancellation contract.

## Display matching

Use case: `ui-mockup`

Create a high-fidelity PySide6 modal titled `Match Project Display — FPVS Studio`.
Redesign the imported-display localization decision around an explicit side-by-side
comparison of imported and locally detected refresh rate, resolution, and physical
screen width. Preserve a separately editable viewing-distance control and explain that
the imported project targets a 5.0° image width. Include `Use detected values`, `Back`,
`Open with imported values`, and the primary `Apply & Open Project` action. Use the
FPVS Studio light palette, clear alignment, accessible desktop sizing, and no web or
decorative chrome.

## Export completion

Use case: `ui-mockup`

Create a persistent, high-fidelity PySide6 export-success page for FPVS Studio. Preserve
the current light palette and restrained scientific tone. Show `PROJECT EXPORT`,
`Project bundle ready`, a compact success badge, the exact bundle filename and saved
path, a concise bundle-contents checklist, the `Not included: cache, logs, and runs`
note, and useful `Copy Path`, `Open Folder`, and `Done` actions. Avoid confetti,
celebratory illustration, oversized status art, web chrome, gradients, and extra copy.
