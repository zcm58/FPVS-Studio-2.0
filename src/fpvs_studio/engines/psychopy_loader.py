"""Lazy PsychoPy dependency loading for engine implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PsychoPyModules:
    psychopy: Any
    visual: Any
    core: Any
    keyboard: Any


def load_psychopy_modules() -> PsychoPyModules:
    """Import PsychoPy modules lazily for the PsychoPy engine."""

    try:
        import psychopy  # type: ignore[import-untyped]
        from psychopy import core, visual
        from psychopy.hardware import keyboard  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - exercised by import-boundary tests
        raise RuntimeError(
            "PsychoPy is not installed. Install the optional 'engine' "
            "dependencies to use this engine."
        ) from exc

    return PsychoPyModules(
        psychopy=psychopy,
        visual=visual,
        core=core,
        keyboard=keyboard,
    )
