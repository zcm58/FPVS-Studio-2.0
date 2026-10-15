# Agent UI design guidance

Use this guidance for substantive interface work in FPVS Studio. It supplements
the [frontend contract](../FRONTEND.md) and [GUI workflow](../GUI_WORKFLOW.md).
Small text or alignment fixes need only the relevant rules.

## Research and applicability

Reviewed 2026-10-15 for the user's GPT-6 Astra design-guidance request. These are
the most useful transferable practices for this repository, based on the sources
below and Studio's existing constraints. They are not a measured ranking or evidence
of a design-quality improvement in this repo. Instructions remain useful to other
agents; they do not change the configured model or reasoning effort.

| Source | Supported guidance | Application here |
| --- | --- | --- |
| [OpenAI: GPT-6 Astra prompting](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices) | Specify completion, resolve conflicting instructions, calibrate verification to the task | Finish the interaction and relevant checks; respect established execution boundaries; stop broadening tests once the required checks pass without unresolved concerns |
| [OpenAI: Rethinking skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra) | Keep instructions lean, route to relevant context, avoid unnecessary approval stops | Put common rules in root AGENTS.md and local details in owning packages; make routine authorized design decisions |
| [OpenAI: Frontend prompt instructions](https://developers.openai.com/api/docs/guides/frontend-prompt) | Match the audience and established design, build usable controls and states, maintain hierarchy and fit | Use a restrained experiment-authoring interface and existing PySide6 components |
| [OpenAI: Designing delightful frontends](https://developers.openai.com/blog/designing-delightful-frontends-with-gpt-5-4) | Concrete visual references, real content, consistent design tokens and rendered inspection improve direction | Compare relevant screen details, use realistic experiment names and paths, inspect actual Qt output when authorized |
| [Microsoft: Command bar](https://learn.microsoft.com/en-us/windows/apps/develop/ui/controls/command-bar) | Rank commands by importance/frequency and keep secondary commands in menus | Keep the main task prominent and occasional tools in existing menus; preserve command locations |
| [Qt: Accessibility](https://doc.qt.io/qt-6/accessible.html) | Adaptive layouts, keyboard access, contrast and non-color status cues | Use standard controls, useful accessible names, visible focus and meaningful status text |
| [Qt: High DPI](https://doc.qt.io/qt-6/highdpi.html) | Widget geometry uses device-independent coordinates; assets must support scaling | Verify text and icons at relevant Windows scaling without mixing logical and physical pixels |

The frontend prompt page targets GPT-5.5; the design article targets GPT-5.4.
Their visual practices are adapted here, not presented as Astra-specific benchmarks.
Web frameworks, marketing heroes, image-generation requirements and browser-only
verification are not Studio architecture guidance. The older article's reasoning-effort
advice does not establish an optimal Astra setting for this application.

## Brief before substantial work

Capture these facts in the existing plan or task notes; do not create an approval
gate or separate design document for every edit:

- Who is using this surface, what are they trying to do, and what is the next action?
- Which existing screen/component or supplied reference anchors the change? Name
  the useful attribute: field alignment, density, command placement or feedback.
- What real content and states must fit at the documented minimum/default size?
- What observable result will demonstrate improvement: fewer steps to a command,
  visible validation, readable names, stable selection, or a clear primary action?

Inspect available screenshots before inferring visual defects from code. If no
rendered evidence is available, use the existing components and state that visual
verification is pending. Research references when the design question needs them;
do not repeat broad online research for routine fixes. Adapt a reference's useful
interaction pattern without copying its branding or importing its implementation stack.

## Native design and review

Use the GUI package's design-quality rules during implementation. The existing
Home/Setup navigation, semantic components, text hierarchy and acceptance sizes
remain authoritative. Treat each added control, container and sentence as something
that must help the current task. Optional help must remain accessible without
displacing essential experiment content.

Review the changed surface against these concrete questions:

| Area | Acceptance question |
| --- | --- |
| Task hierarchy | Is the next action easy to locate, with occasional tools in predictable menus? |
| Layout | Do grouping and alignment support scanning, with no clipped controls, overlaps or state-driven layout jumps? |
| Content | Are labels precise, units clear, and long names/paths available in full through the documented access path? |
| Interaction | Do keyboard use, selection, pending edits, disabled actions and cancel/recovery behave correctly? |
| State | Are actual loading, error and save states distinguishable, with an appropriate next action? |
| Consistency | Does the surface reuse the established tokens, icons and controls across both themes? |

During an approved visible session, inspect real before/after captures with synthetic
experiment data at the documented sizes and relevant Windows scale factors. Exercise
the affected states, fix observed defects and recheck those states. Keep captures
identified by surface, size, theme and scale; distinguish mockups from running GUI
screenshots. Deliver requested screenshots as image attachments/embeds rather than
assuming a local Windows Markdown image path will render in chat.

Run the focused verification route and maintain registered GUI coverage required by
the repository. Visual review does not substitute for behavior checks, and passing
non-Qt checks does not prove visual quality. Existing approval requirements for
visible Qt execution remain in force; never use offscreen Qt to bypass them.
Report precisely what was observed and what remains unverified.
