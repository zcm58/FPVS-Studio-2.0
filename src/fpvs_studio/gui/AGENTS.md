# AGENTS.md

## Scope of this directory

`src/fpvs_studio/gui/` will hold the PySide6 user interface.

The GUI is not the primary focus of the current phase. The goal right now is just to create a sane package boundary and minimal placeholders if needed.

## Requirements

- The GUI should depend on core services/models, not on raw dicts.
- The GUI should never import PsychoPy directly.
- Any future run/test action should hand off to runtime through neutral data contracts.

## Current phase guidance

- It is fine to create placeholder modules/classes.
- Do not spend most of this pass building widgets.
- Prefer thin GUI shells over premature complex architecture.

