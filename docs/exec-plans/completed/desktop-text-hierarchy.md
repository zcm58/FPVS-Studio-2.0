# Desktop text hierarchy

Status: Completed

## Current baseline

Studio 3.1.0 shows the build version above Welcome's project actions, puts the
active Home launch blocker beside the project identity, and aligns the Run title
with its workspace. The [shared text hierarchy](../../FRONTEND.md#shared-text-hierarchy)
defines the title, section, body, supporting and metadata roles.

The [interface polish](desktop-interface-polish.md) and
[panel hierarchy](desktop-panel-hierarchy.md) records cover visible
Light and Dark work at 100% Windows scaling, including all nine Setup steps,
compact Home and representative dialogs. The
[3.1.0 release](release-3.1.0.md) adds packaged layout coverage for
all seven Settings pages at 860 × 560 and 1000 × 680. All 28 Light/Dark cases
passed, along with two scroll cases that kept navigation and Close reachable.

## Windows acceptance (November 19, 2026)

- Visible registered cases passed for the Welcome build label and busy import
  copy, and for the long Home project name and launch blocker at 760 × 520 and
  1120 × 720 in both themes. The blocker exposes its full text through the
  tooltip and accessible label. The tests use isolated projects and fake launch
  and import states.
- Visible cases passed for the populated Setup Review at 1120 × 820, the Run
  readiness and details at 960 × 640 and 1120 × 720, Condition Modifiers at
  1100 × 720 and 1120 × 760, and Presentation Settings at 900 × 600. The
  registered reminder cases checked the generic BioSemi and BrainVision prompts.
- Four expanded Settings cases passed for Light and Dark at 860 × 560 and
  1000 × 680. They toggle **Reduce motion** during active feedback, confirm
  the ticker and progress state remain visible, reopen to verify persistence,
  and use keyboard navigation to reach the theme selector and Diagnostics in
  both motion modes. The Diagnostics callback is a local stand-in.

Higher scaling and complete native frame fit remain under the separate
[appearance plan](../active/slate-and-signal-teal-appearance.md).

## Source audit

| Finding | Implementation |
| --- | --- |
| Welcome's generic heading supplied no build identity. | Show the running package version once and place transient import status next to the action group. |
| Home's launch blocker sat between project actions and metrics. | Move the blocker below the project name and description, with the complete text available on hover and to assistive technology. |
| Run's centered title and full-width readiness badge competed with its workspace and launch action. | Align the title with the bounded workspace and use the same inline readiness treatment as Home. |
| Setup Review and page/dialog headings expressed common purposes through local selectors. | Apply shared roles for titles, section labels, body text, supporting text and metadata. |
| Condition Modifiers and Presentation Settings mixed interpretation and routine guidance into loose text. | Group recorded data under its own heading and retain the presentation inheritance rule. |
| Settings used a shared category title with inconsistent grouping inside each page. | Use shared page, section and subsection roles. Place Account last and present reporting as a single Diagnostics checkbox. |

The shared foreground and inline status tokens were checked against the page and
surface backgrounds in source. The lowest calculated ratio was 6.64:1 in Light
and 8.92:1 in Dark.

## Verification

The original text-hierarchy pass cleared focused GUI and docs checks, targeted
type checking and repository precommit with 6,237 unit cases passing and 34
platform and environment skips. Its registered Qt cases were deferred at that
point. Later visible work is linked in the baseline above.
