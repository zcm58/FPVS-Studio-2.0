# Desktop interface polish

Status: Complete (source implementation and visible Windows verification at 100% scaling)

## Workflow and acceptance

Audit the desktop surfaces used to open a project, edit its setup, check readiness,
start a session, and manage the workspace or use a tool. The next action and any
blocking state should be easy to find. Remove headings, decoration, and copy that
repeat the surrounding controls. Keep experiment-specific guidance, failure recovery,
and warnings that affect timing, recording, or participant data.

Use existing PySide6 widgets and semantic theme roles. Keep project files, launch
routing, participant instructions, and experiment behavior within their existing
contracts. Budget edits for the documented minimum and default sizes, especially
the nine Setup steps at 1120 × 820. Use registered Qt cases for changed interactions
and geometry. Run focused GUI and docs verification plus repository precommit.

## Audit evidence

The source pass covered the shared components, Welcome, Home, all nine Setup steps,
Settings, Image Resizer, and the internal Run and Stimuli Manager views. Findings
are ranked by user impact. Existing app-specific actions, visible state text,
standard Qt input controls and semantic theme colors anchor the design.

| Priority | Finding | Change |
| --- | --- | --- |
| P1 | Image Resizer replaced a failed batch message with readiness and could retain stale output actions after folder changes. | Preserve the failure status until retry or a folder change. Clear previous output actions when a folder changes. |
| P1 | Setup could display the 60 Hz editing fallback as a saved refresh rate, and Neutral Gray recovery pointed to the wrong step. | Review reads the saved value. Conditions points to Display & Session when the required background is missing. |
| P2 | Home and Run contained obsolete Design guidance and repeated readiness boilerplate. | Point to Setup → Conditions. Use the first actual blocker on Home and one details pane on Run. |
| P2 | The main window and response-key picker allocated a graphics effect and animation for each button. Focus on a filled light-theme primary button could share its fill color. | Use theme hover, pressed and focus states. Primary button focus uses the foreground color against its fill. |
| P2 | Long Home descriptions and stimulus paths were shortened at fixed character counts. Workspace concealed the active root behind a tooltip. | Use width-based elision and preserve complete values through accessible text and tooltips. Show the active root in Workspace. |
| P2 | Image Resizer applied a one-time local palette. | Subscribe its local styles to the shared palette observer. |
| P3 | Welcome repeated the app name at hero scale. Setup and Image Resizer repeated their own titles, controls and status. | Use a Projects heading, direct Setup step names, and one Image Resizer status. |

The shared primary button focus edge has a calculated contrast ratio of 5.17:1
against the light fill and 7.45:1 against the dark fill. For the hovered or pressed
fill, the ratios are 8.72:1 and 5.15:1. The ratios describe theme tokens.

## Visible smoke

- At 760 × 520 and 1120 × 720, open Welcome and check Enter, then open ready and
  incomplete projects. Check action priority, an empty description, and a long
  description with its full text available.
- At 1120 × 820, walk Setup with the keyboard. Check image, word and native AB
  Conditions, the Neutral Gray prompt, a long project name, and Review with saved
  and unset refresh rates and accuracy tracking on and off.
- At 860 × 560 and 1000 × 680, check Settings navigation and the Workspace path.
  Verify the full path remains available when shortened. Inspect Advanced and
  Diagnostics with their restart and privacy guidance.
- At 960 × 640 and 1120 × 720, use Image Resizer with a valid source, then an empty
  source and a retry. Check action focus, persistent failure, output actions after
  success, and clearing them when a folder changes. Switch themes with the tool open.
- Use the registered Run and Stimuli Manager tests to expose the internal views.
  Check readiness, an empty session preview, preview results, and long paths.
  Exercise Light and Dark at the sizes above and check representative Windows scaling.

### Windows desktop results

On 2026-11-12, reviewed the native Qt 6.11.2 interface at 96 logical DPI in
Light and Dark. Captures used 760 × 520 for Welcome and Home, 1120 × 820 for
all nine Setup steps, 860 × 560 for all six Settings categories, and 960 × 640
for Image Resizer, Run, and Stimuli Manager. The projects and images were
synthetic, with playback and recording stubbed.

- Widened the Setup stepper to keep **Display & Session** readable in every
  step. Identified an unset refresh target as **60 Hz (default)** in the display
  editor, and made the first explicit selection of 60 Hz persist the target.
- Fixed singular Review counts, omitted an empty transform summary from Review
  and Image Size, and used one descriptive checkbox for consecutive change counts.
- Top-aligned Run display controls and gave the background note a full row.
  Image Resizer paths stay on one line with the full value available by tooltip
  and accessible name. Confirmed empty, failed, and successful batches in both themes.

## Verification

- GUI focused passed 180 non-Qt tests. Docs focused passed 13 tests.
- Repository precommit passed 6,237 non-Qt tests with 34 environment and platform
  skips. Ruff, Python compilation, Windows and macOS type checks, and repository
  audits passed. Targeted lint, compilation and type checks covered follow-up edits.
- Visible Windows verification passed 83 registered Qt cases in four serial
  batches and the two native-theme capture cases. Checks covered all nine Setup
  steps, keyboard navigation, long content, refresh selection, and tool recovery.
  Larger combined runs timed out during application-wide palette changes, so
  the final runs used fresh processes between batches. Physical timing and
  recording hardware were outside this UI pass.
