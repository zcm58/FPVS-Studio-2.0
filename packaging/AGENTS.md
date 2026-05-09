# AGENTS.md

## Scope of this directory

`packaging/` contains developer build configuration for local Windows executable
artifacts. It is not application runtime code and must not own project data, user
settings, templates, or runtime/session contracts.

## Requirements

- Start packaging work from `docs/PACKAGING.md`, `ARCHITECTURE.md`, and
  `pyproject.toml`.
- Keep `scripts/build_exe.ps1` as the developer entry point for local executable builds.
- Keep `scripts/build_installer.ps1` as the developer entry point for local Inno Setup
  installer builds.
- Keep build outputs under ignored `build/` and `dist/` paths.
- Keep packaging dependencies in the `packaging` optional dependency group.
- Keep app-version changes centralized in `pyproject.toml`; `src/fpvs_studio/__init__.py`
  must read `__version__` from source-tree `pyproject.toml` when present and fall back
  to installed package metadata for bundled installs, and `tests/unit/test_package_metadata.py`
  guards this.
- If adding an app icon, prefer `packaging/assets/fpvs-studio.ico`, wire it through the
  PyInstaller spec and Inno Setup script, and update GUI application-window icon loading
  in the same change.

## Restrictions

- Do not write installer/build logic that deletes or rewrites QSettings, project roots,
  `.fpvs-studio/templates/`, `runs/`, or `logs/`.
- Do not vendor PyInstaller or third-party wheels into the repository.
- Do not vendor Inno Setup binaries into the repository.
- Do not turn packaging scripts into GitHub release automation without updating
  `docs/PACKAGING.md` and the architecture task recipe.
