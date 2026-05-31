"""Lazy PsychoPy dependency loading for engine implementations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class PsychoPyModules:
    psychopy: Any
    visual: Any
    core: Any
    keyboard: Any
    logging: Any


def load_psychopy_modules() -> PsychoPyModules:
    """Import PsychoPy modules lazily for the PsychoPy engine."""

    try:
        psychopy = import_module("psychopy")
        visual = import_module("psychopy.visual")
        core = import_module("psychopy.core")
        keyboard = import_module("psychopy.hardware.keyboard")
        logging = import_module("psychopy.logging")
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
        logging=logging,
    )
