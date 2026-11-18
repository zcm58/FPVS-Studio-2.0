# Design

## Overview

Use this page as the design-document hub. FPVS Studio design decisions should support
fast returning-user launches, low-friction setup, and clear scientific/runtime status.

### Current design sources

- Core UX beliefs: `design-docs/core-beliefs.md`
- Agent design brief, research and review: [agent UI design guidance](design-docs/agent-ui-design.md)
- PySide6 GUI workflow and test guidance: `GUI_WORKFLOW.md`
- Public GUI component/theme surface: `../src/fpvs_studio/gui/components.py`
- GUI package guidance: `../src/fpvs_studio/gui/AGENTS.md`

## Shared OpenFPVS desktop experience

Maintainers can find the canonical desktop specification in the private OpenFPVS
checkout at `../OpenFPVS/DESKTOP_EXPERIENCE.md`, relative to the Studio repository root.
For release decisions, read [How to plan independent releases](https://github.com/zcm58/OpenFPVS-Website/blob/main/DESKTOP_EXPERIENCE.md#how-to-plan-independent-releases).
Use Studio for desktop layout, action order, focus and navigation. Use the
OpenFPVS and Toolbox Slate & Signal Teal palette for Studio surfaces.
Design for lab members doing routine work, with guidance beside unfamiliar choices
and advanced settings within reach for expert users.

For future changes, keep the path to the next participant quiet. Use inline or nonmodal notices
for optional account setup, updates and background status. Interrupt when the
current task requires a decision to proceed or continuing would put data or
scientific interpretation at risk. One dismissible reminder per Studio launch
is appropriate for an outstanding [Results upload](DATA_SHARING.md#operator-workflow).

## Colors

The Slate & Signal Teal theme applies to authoring controls. Scientific figures
and participant stimuli keep their authored colors. The [palette acceptance plan](exec-plans/active/slate-and-signal-teal-appearance.md) covers native visual review.
Implement desktop colors through [the theme definitions](../src/fpvs_studio/gui/design_system.py)
and keep semantic status labels legible in Light and Dark.

| Role | Light | Dark |
| --- | --- | --- |
| Workspace | `#F3F6F8` | `#202124` |
| Surface | `#FFFFFF` | `#24272D` |
| Elevated surface | `#FFFFFF` | `#30343B` |
| Primary text | `#1D2A34` | `#F3F6FB` |
| Muted text | `#4D626D` | `#AEB8C7` |
| Primary action | `#00646C` | `#25B8C4` |
| Focus | `#805C23` | `#78D5DD` |

## Typography

The desktop shell inherits the Qt application font family. Shared roles use
24 px for page titles, 18 px for dialog titles, 16 px for section titles,
13 px for body text and controls, and 12 px for metadata. Apply roles via
`mark_text_role` or the shared header components. Follow the
[text hierarchy](FRONTEND.md#shared-text-hierarchy) for standalone labels.

## Components

Use the [shared component module](../src/fpvs_studio/gui/components.py) for dialog
headers, titles, action styles and status. Style the next action with
`mark_primary_action` and supporting actions with `mark_secondary_action`.
`apply_dialog_theme` applies the dialog surface, field, button, selection and focus
styles for the current theme. Preserve focus visibility and essential status at
the documented minimum dialog size.

## Update Rules

- Put reusable design principles in `design-docs/`.
- Put concrete GUI behavior and smoke-test expectations in `GUI_WORKFLOW.md`.
- Put feature-sized redesign plans in `exec-plans/active/` before implementation.
- Keep page-local styles out of GUI modules unless the visual need is truly local.
