# AGENTS.md

## Scope of this directory

`src/fpvs_studio/app/` contains application entry points and startup wiring.

## Requirements

- Keep startup thin; route real behavior into GUI, core, runtime, or preprocessing
  services.
- Do not import PsychoPy here.
- Avoid importing PySide6 in modules that are intended to remain backend-importable.
- Preserve the installed `fpvs-studio` entry point unless the packaging contract is
  explicitly changed.

## Verification

- Run `./scripts/verify.ps1 -Scope repo -Tier focused`. The configured
  route owns startup and import-boundary selection.
