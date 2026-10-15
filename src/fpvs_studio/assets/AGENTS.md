# AGENTS.md

## Scope of this directory

`src/fpvs_studio/assets/` contains static application assets that must be available to
the installed GUI at runtime, such as the FPVS Studio window icon.

## Requirements

- Keep assets small and release-facing.
- Reuse the established icon and branding language. Add imagery only when it helps
  identify an action, explain experiment content, or communicate state.
- For changed GUI assets, inspect legibility at actual displayed sizes in light/dark
  themes and relevant Windows scaling during approved visible acceptance. Use Qt's
  high-DPI asset handling; do not assume widget coordinates are physical pixels.
- Keep source branding assets and release-tooling icons documented in `docs/PACKAGING.md`.
- Do not place project data, user templates, generated stimuli, logs, or runtime outputs
  in this package.
- The packaged `.ico` used by the GUI, PyInstaller, and Inno Setup is generated from
  `packaging/assets/fpvs-studio-icon-1024.png` by `scripts/sync_branding_assets.ps1`.
  Do not keep extra copied PNG sources in this package.
