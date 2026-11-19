# Slate & Signal Teal desktop appearance

Status: Active

## Current baseline

Studio 3.1.0 ships the Slate & Signal Teal authoring palette with shared Light and
Dark tokens and native Qt theme selection. Welcome displays the version on the
workspace background after `0a0df50` removed the separate masthead fill. Theme
values are owned by [design_system.py](../../../src/fpvs_studio/gui/design_system.py)
and shared styles by [components.py](../../../src/fpvs_studio/gui/components.py).

The [interface polish](../completed/desktop-interface-polish.md) and
[panel hierarchy](../completed/desktop-panel-hierarchy.md) records cover Light
and Dark at 100% on Windows, including compact Home and all nine Setup steps at
1120 × 820. The [3.1.0 packaged smoke](../completed/release-3.1.0.md) also covered
all Settings categories at both sizes with Light and Dark verification palettes.
The [theme preference checks](../completed/settings-hierarchy-and-theme.md)
exercised native palette handling and simulated scheme notifications.

## Remaining acceptance

- [x] At native 125% scaling, check
  Welcome, Home, Settings, Run, Library, representative tools and dialogs, and
  all nine Setup steps at 1120 × 820. Use documented minimum/default sizes,
  long values, and synthetic projects with fake launch, recording and services.
  Confirm actions remain reachable and Setup needs no page-level scrolling.
- [ ] Repeat the full-window matrix at native 150% scaling on a display whose
  work area fits the 1120 × 820 Setup client area and its native frame.
- [x] Review shared theme states, including selected, disabled, busy,
  warning, error, keyboard focus, native menus and open dialogs. Check normal
  text at 4.5:1 and meaningful boundaries and focus at 3:1 against adjacent colors.
- [x] Change the actual Windows color scheme with Auto selected and dialogs open.
  Confirm that open surfaces update, explicit Light/Dark persist across restart
  and resist OS changes, and returning to Auto follows the current OS theme.
- [x] On a synthetic project, verify the authored data, compiled settings,
  participant-facing colors and figure exports across theme changes.

Close when the GUI maintainer records the build, OS, scale, window size and
results for these checks against the [frontend](../../FRONTEND.md) and
[appearance](../../GUI_WORKFLOW.md#settings-appearance-and-layout) contracts.

## Unattended verification (November 19, 2026)

On the office Windows PC at 100% scaling with a 1920 × 1032 work area, the
registered visible desktop selection passed all palette cases. It included
Light and Dark contrast and focus boundaries, keyboard interaction, native
menu fit, all nine Setup pages in both palettes, Auto scheme handling, and
equality of compiled experiment settings and rendered figure pixels. The
full-window native 150% matrix on a taller display remains open.

## Initial office PC verification (November 19, 2026)

Windows Light/Dark changes reached the open Welcome window and Settings dialog
with Auto selected. Both explicit Studio schemes loaded in separate process
restarts while Windows used the opposite scheme. Returning to Auto applied
the current Windows scheme. Settings used an isolated test profile.

The Dark enabled field and button outline measured 1.99:1 against the field
fill. The feature branch now uses an outline with a 3.37:1 minimum across
the tested Dark surfaces. Hover and press outlines measure 4.85:1 in Light
and 4.97:1 in Dark against their active fill. The registered test verifies the
shared stylesheet selectors and both themes' neutral and primary focus rings.

The office panel's logical work area was 1536 × 816 at 125% and
1280 × 672 at 150%. Both are shorter than the Setup window before accounting
for native chrome. The broader 125% Qt run timed out, and an isolated rerun
passed the composited Setup theme and shared contrast cases at that scale.
At 150%, all four compact Welcome cases, the composited
Setup theme test, and the Settings keyboard/motion and control-contrast checks
passed. Windows clamped the four default Welcome cases to 1120 × 700
instead of the requested 1120 × 720. These runs used the standard visible
taskbar.

## Follow-up verification (November 19, 2026)

The office PC ran the 3.1.0 source on `codex/verify-studio-desktop-plans`
from `ba631d9` plus the appearance changes. At native 100%, 86 baseline
layout cases passed for Welcome, Home, Run, Settings, Library, menus,
representative dialogs and tools, and all nine Setup steps. Launch,
serial hardware, external services and file pickers used isolated fixtures
or stubs where applicable.

The updated shared styles improve text and dropdown selection, disabled
labels, and keyboard focus on lists and tables. The weakest measured
shared disabled label is 4.60:1, control boundary 3.37:1 and neutral
focus indicator 5.06:1. The Attentional Blink selected SOA row is at least
5.30:1 against adjacent rows, and the standalone Designer's primary label
is at least 8.68:1 on hover.

All 16 follow-up cases at native 100% passed, including native Qt menu
geometry and selection at 760 × 520 and 1120 × 720 in both themes. A visible
test opened a synthetic authored project, selected each theme in Settings,
and exported a Condition Figure through the normal tool with the output
picker stubbed. Both themes matched the saved project and stimulus bytes,
seeded SessionPlan, compiled participant colors and all pixels and DPI
metadata in the 600-DPI PNG.

At native 125%, temporarily auto-hiding the taskbar gave Windows a
1536 × 864 logical work area. All 50 registered cases passed, including the
nine common Setup steps in Light and Dark at 1120 × 820 with no page-level
scrolling. The entire 1120 × 850 native frame fit inside that work area in
both appearances.

At native 150%, all 24 compact-window cases passed on the 1080p panel.
They covered Welcome, Home, Run, Settings, Library, menu popups and
representative tools. The work area was 1280 × 720 with the taskbar
auto-hidden, below the required 820-pixel Setup client height before
native chrome. The full-window 150% run remains open. The office PC was
returned to 100% scaling with its original visible taskbar.

The focused GUI and documentation suites passed 183 and 13 cases.
Repository precommit passed 6,524 tests and reported two failures in
reporting tests. The workflow-reporting Windows file-replacement case
passed in isolation. A worker exited during the data-sharing volume test.

## Original approved palette

| Role | Value |
| --- | --- |
| Studio-owned masthead | `#222F3B` |
| Light workspace background | `#F3F6F8` |
| Light panel | `#FFFFFF` |
| Light primary text | `#1D2A34` |
| Light muted text | `#4D626D` |
| Light primary action | `#00646C` |
| Light selection | `#DDEEF0` |
| Light divider | `#CBD9DE` |
| Light control boundary | `#6A7C87` |
| Focus on light surfaces | `#805C23` |
| Signal accent on dark surfaces | `#25B8C4` |

The original palette included a masthead fill. Current Light and Dark values
reside in the design system. Dividers group sections, with a stronger boundary
where it conveys interactivity. The light focus color has 5.57:1 contrast on the
workspace and 1.14:1 on the primary action fill. The interface polish record
documents the separately contrasting indicator used on filled primary controls.

Keep the existing success, warning, error, information, pending and destructive
roles with their text or symbols. Preserve scientific colors for Base and
Oddball roles, stimulus and fixation previews, plots and exports. The desktop
palette stays outside the experiment's authored appearance and participant
presentation, timing, recording and result contracts.

## Original implementation phases

1. **Map shared roles and establish a baseline.** Use
   [design_system.py](../../../src/fpvs_studio/gui/design_system.py) for theme
   values and [components.py](../../../src/fpvs_studio/gui/components.py) for
   shared styles. Identify the Studio-owned masthead and preserve native window
   captions and dialogs. Capture representative current Light and Dark windows
   with synthetic projects for comparison.
2. **Apply and review Light.** Start with Welcome, Home and Settings, then extend
   through all nine Setup steps, Run, Library, and representative tools and
   dialogs. Reuse shared components so the same field, action, selection and
   status roles read consistently. Verify the existing size and action hierarchy
   after each group of changes.
3. **Complete Dark and verify Auto.** Derive readable Dark surfaces, text and
   control states around the selected dark accent. Check Light and Dark on open
   windows, persisted explicit modes across restart, and Auto's live response
   to OS scheme changes. Keep the existing fallback to Auto for missing or
   invalid preferences and the current feedback when saving fails.
4. **Review and hand off.** Run focused GUI and docs checks, registered Qt
   coverage and repo precommit. Record the source results and visible acceptance
   separately. Update the canonical GUI and frontend contracts after the work
   lands. Release packaging and publication are separate work.
