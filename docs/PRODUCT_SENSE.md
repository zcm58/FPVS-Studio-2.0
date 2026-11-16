# Product Sense

FPVS Studio helps researchers prepare stimuli, author reproducible image and word
FPVS experiments, and run repeated participant sessions without rebuilding their
experiment for each participant. The [current product specification](product-specs/studio.md)
defines the mission and routes to the implemented contracts.

The primary workflows are:

1. Optionally prepare images using Image Resizer and Image Equalizer, or use stimuli
   already prepared externally. Preparation creates separate copies and is not a
   mandatory Setup step. Native word lists do not need image preparation.
2. Create an FPVS project once by selecting conditions, stimuli, display settings,
   session design, and fixation behavior.
3. Reopen that project many times over weeks or months and launch the experiment quickly
   for participant sessions.

The GUI should optimize repeated sessions while keeping preparation and authoring
accessible. Ready projects
should open to Home. New or incomplete projects should guide users through setup.

## Product Sources

- Current category/protocol scope: `EXPERIMENT_CATEGORIES.md` and `RUNSPEC.md`
- GUI workflow behavior: `GUI_WORKFLOW.md`
- Product specs area: `product-specs/index.md`

## Product Guardrails

- Keep launch readiness honest and computed from existing validation.
- Prefer defaults for technical FPVS timing choices, then expose advanced controls only
  where power users need them.
- Keep optional image utilities independent of project state, preserve source files,
  and distinguish digital image matching from external monitor calibration.
- Support image and word studies explicitly; document current limitations rather than
  implying support for every published FPVS method.
- Do not add persisted approval states or schema changes without an execution plan.
