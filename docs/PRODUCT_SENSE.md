# Product Sense

FPVS Studio is primarily for two workflows:

1. Create an FPVS project once by selecting conditions, stimuli, display settings,
   session design, and fixation behavior.
2. Reopen that project many times over weeks or months and launch the experiment quickly
   for participant sessions.

The GUI should optimize the second workflow without hiding the first. Ready projects
should open to Home. New or incomplete projects should guide users through setup.

## Product Sources

- Current product/protocol scope: `FPVS_Studio_v1_Architecture_Spec.md`
- GUI workflow behavior: `GUI_WORKFLOW.md`
- Product specs area: `product-specs/index.md`

## Product Guardrails

- Keep launch readiness honest and computed from existing validation.
- Prefer defaults for technical FPVS timing choices, then expose advanced controls only
  where power users need them.
- Do not add persisted approval states or schema changes without an execution plan.
