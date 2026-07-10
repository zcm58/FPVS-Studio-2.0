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
- Keep `scripts/build_release.ps1` and `scripts/build_release.cmd` as thin convenience
  wrappers over the executable and installer scripts; do not duplicate stage logic there.
- Keep build outputs under ignored `build/` and `dist/` paths.
- Keep packaging dependencies in the `packaging` optional dependency group.
- Keep app-version changes centralized in `pyproject.toml`; `src/fpvs_studio/__init__.py`
  must read `__version__` from source-tree `pyproject.toml` when present and fall back
  to installed package metadata for bundled installs, and `tests/unit/test_package_metadata.py`
  guards this.
- If replacing branding, update the canonical high-resolution PNG at
  `packaging/assets/fpvs-studio-icon-1024.png`, run
  `scripts/sync_branding_assets.ps1`, and keep PyInstaller, Inno Setup, and GUI
  application-window icon loading pointed at the generated packaged icon.

## Restrictions

- Do not write installer/build logic that deletes or rewrites QSettings, project roots,
  `.fpvs-studio/templates/`, `runs/`, or `logs/`.
- Do not vendor PyInstaller or third-party wheels into the repository.
- Do not vendor Inno Setup binaries into the repository.
- Do not turn packaging scripts into GitHub release automation without updating
  `docs/PACKAGING.md` and the architecture task recipe.

## Verification

- Run `./scripts/verify.ps1 -Scope packaging -Tier focused` before a
  release build. Build or installer execution remains an explicit packaging task.
