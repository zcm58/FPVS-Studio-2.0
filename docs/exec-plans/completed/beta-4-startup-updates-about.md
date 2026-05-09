# Beta 4 Startup Updates And About UI

Status: Completed

## Summary

Prepared FPVS Studio `0.9.1b4` by adding a silent startup update check, app-version
visibility in Settings, a `File > About` item, and a bounded Home description preview.

## Implementation

- Run one update check per app launch after root-folder setup succeeds and the Welcome
  window is visible.
- Stay silent when no update is available or the check fails; show the existing update
  dialog only when an update is available.
- Add `FPVS Studio version <version>` to Settings and `File > About` with developer and
  institution text.
- Keep project descriptions unrestricted, but render Home as a bounded two-line preview
  with the full description in a tooltip.
- Bump package metadata and packaging docs to `0.9.1b4`.

## Verification

- Added GUI coverage for startup update prompting, silent no-update/error behavior,
  About, Settings version display, and Home description clipping prevention.
- Built the beta 4 EXE and installer during implementation.
