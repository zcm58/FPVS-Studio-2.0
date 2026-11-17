# Slate & Signal Teal desktop appearance

Status: Planned

## Decision and scope

The user selected Slate & Signal Teal for a future FPVS Studio desktop appearance
update. Preserve Studio's icons, typography, layouts and workflows. This plan
records the design decision. Move it to `active/` when the user selects the
desktop implementation as the next task.

Studio already offers **Settings > Appearance > Light / Dark / Auto**. Keep the
existing immediate application, per-computer `appearance/theme_mode` preference
and native Qt scheme selection. Auto follows the OS and refreshes open windows
when it changes. Reuse the existing theme roles and palette observers. See
[Frontend](../../FRONTEND.md) and
[Settings appearance and layout](../../GUI_WORKFLOW.md#settings-appearance-and-layout).

## Approved palette

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

The selected palette defines Light and the dark masthead accent. Resolve the
remaining Dark roles in native Studio captures during implementation. Keep
dividers for grouping and use the stronger control boundary where it conveys
interactivity. The light focus color has 5.57:1 contrast on the workspace and
1.14:1 on the primary action fill. Retain a separately contrasting focus
indicator on filled controls, including hover and pressed states.

Keep the existing success, warning, error, information, pending and destructive
roles with their text or symbols. Preserve scientific colors for Base and
Oddball roles, stimulus and fixation previews, plots and exports. The desktop
palette stays outside the experiment's authored appearance and participant
presentation, timing, recording and result contracts.

## Implementation phases

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

## Acceptance

- Check text at 4.5:1 and meaningful control boundaries and focus at 3:1 against
  adjacent colors. Review selected, disabled, busy, warning and error states
  along with keyboard focus, native menus and already-open dialogs.
- In an approved visible Windows session, review 100%, 125% and 150% scaling
  at documented minimum and default sizes. All nine Setup steps must fit at
  `1120x820` without required scrolling or clipping. Use realistic long values
  and synthetic data with fake launch, recording and service dependencies.
- Test native OS-follow behavior separately from simulated palette events.
  Check that changing appearance leaves project files, compiled settings,
  participant-facing colors and exported figures unchanged.
