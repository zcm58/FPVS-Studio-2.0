# Packaged Update Checker Regressions

Status: Completed

## Summary

Installed lab builds reported update-checker regressions that did not reproduce when the
app ran from `src/` on the dev PC. The beta 7 repair treats the failures as packaging and
installed-app smoke coverage gaps: the release build now fails on stale package metadata,
the packaged app exposes a bounded smoke mode for installed-update-dialog behavior, and
the update dialog owns its shared theme and button geometry directly.

## Success Criteria

- A freshly built and installed package reports the same app version as `pyproject.toml`
  and the installer filename/release tag used for that build. Completed for `0.9.0b7`.
- The update checker uses the same shared GUI theme/resources in packaged and source-tree
  runs. Completed by applying the shared Studio theme inside `UpdateDialog`.
- `Remind Me Later` closes or dismisses the startup update prompt without crashing the
  installed app. Completed by direct installed-app smoke verification.
- Update-checker action buttons do not clip text at 1080p with normal Windows display
  scaling. Completed with stable update-dialog minimum widths and smoke/test coverage.
- The packaging/update smoke path has a repeatable verification command or documented
  manual smoke checklist that exercises installed-app behavior, not only `src/` behavior.
  Completed with `scripts/smoke_packaged_app.ps1`.

## Assumptions

- Source-tree update behavior is currently functional on the dev PC.
- The non-dev PC failure is caused by PyInstaller/Inno packaging, installed metadata,
  bundled resources, or installed-app Qt runtime behavior rather than the update backend's
  release-selection logic.
- The repair should keep app version ownership centralized in `pyproject.toml`.
- This plan should not add fallback version constants or silent fallback behavior that
  could hide future packaging drift.

## Key Changes

- Bumped the package and installer target to `0.9.0b7`.
- Added build-time checks that compare `pyproject.toml`, `fpvs_studio.__version__`,
  installed package metadata, and bundled `fpvs_studio-*.dist-info` metadata before a
  release build can pass.
- Added `scripts/smoke_packaged_app.ps1`, backed by the packaged executable's hidden
  `--packaged-smoke-output` diagnostic mode, to verify installed metadata and
  update-dialog behavior from the bundle or installed app.
- Applied the shared Studio theme directly to `UpdateDialog`, including explicit
  update-dialog label/progress styling.
- Replaced the relabeled standard Close button with an explicit reject-role button and
  fixed action-button minimum widths so `Remind Me Later`, `Download Update`, and
  `Install and Restart` do not clip.

## Files Changed

- `pyproject.toml`
- `src/fpvs_studio/app/main.py`
- `src/fpvs_studio/app/packaged_smoke.py`
- `src/fpvs_studio/gui/update_dialog.py`
- `src/fpvs_studio/gui/components.py`
- `scripts/build_exe.ps1`
- `scripts/build_release.ps1`
- `scripts/smoke_packaged_app.ps1`
- `tests/unit/test_package_metadata.py`
- `tests/unit/test_app_main.py`
- `tests/gui/test_update_dialog.py`
- `ARCHITECTURE.md`
- `docs/PACKAGING.md`
- `docs/PLANS.md`

## Verification

- `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_app_main.py tests\unit\test_package_metadata.py`
  passed.
- `$env:QT_QPA_PLATFORM='offscreen'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; .\.venv3.10\Scripts\python -m pytest --disable-plugin-autoload -p pytestqt.plugin -p pytest_timeout -q tests\gui\test_update_dialog.py`
  passed.
- `.\.venv3.10\Scripts\python -m pytest -q tests\unit\test_harness_docs.py` passed.
- `.\.venv3.10\Scripts\python -m ruff check src tests` passed.
- `.\scripts\build_release.ps1 -SkipInstall` rebuilt `dist\FPVS Studio\FPVS Studio.exe`
  with bundled `fpvs_studio-0.9.0b7.dist-info`, ran the packaged-app smoke check, and
  produced
  `dist\installer\FPVS-Studio-Setup-0.9.0b7.exe`.
- Installed `dist\installer\FPVS-Studio-Setup-0.9.0b7.exe` into the per-user install
  location and manually ran
  `.\scripts\smoke_packaged_app.ps1 -ExePath "$env:LOCALAPPDATA\Programs\FPVS Studio\FPVS Studio.exe"`;
  the installed app reported `app_version=0.9.0b7`, `metadata_version=0.9.0b7`,
  `update_dialog_style_applied=true`, `remind_later_dismissed=true`, and
  `buttons_fit=true`.

## Notes

- The existing local `0.9.0b6` bundle contained correct `0.9.0b6` metadata, but the
  repaired build path now fails closed if stale installed metadata would be copied into a
  future bundle.
- The installed-app smoke command is the repeatable proxy for non-dev PC behavior. It
  exercises the packaged executable, not the source-tree Python path.
