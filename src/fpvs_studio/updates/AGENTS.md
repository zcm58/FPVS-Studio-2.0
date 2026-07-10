# AGENTS.md

## Scope of this directory

`src/fpvs_studio/updates/` contains backend-only update-checking, installer download,
and installer-launch helpers for the end-user application update flow.

## Requirements

- Do not import PySide6 in this package; GUI presentation belongs in
  `src/fpvs_studio/gui/`.
- Do not import PsychoPy or runtime engine modules.
- Treat GitHub Releases as release metadata, not as arbitrary executable input.
- Keep update downloads in user-writable cache or temp folders, never in the install
  directory or project folders.
- Use HTTPS release and asset URLs only.
- Keep installer launch explicit; callers must get final user confirmation before
  executing a downloaded installer.

## Verification

- Run `./scripts/verify.ps1 -Scope updates -Tier focused`. The configured
  route owns update behavior and import-boundary checks.
