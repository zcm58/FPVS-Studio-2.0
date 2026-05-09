# AGENTS.md

## Scope of this directory

`src/fpvs_studio/assets/` contains static application assets that must be available to
the installed GUI at runtime, such as the FPVS Studio window icon.

## Requirements

- Keep assets small and release-facing.
- Keep source branding assets and release-tooling icons documented in `docs/PACKAGING.md`.
- Do not place project data, user templates, generated stimuli, logs, or runtime outputs
  in this package.
- If replacing the app icon, keep the GUI asset synchronized with
  `packaging/assets/fpvs-studio.ico`.
