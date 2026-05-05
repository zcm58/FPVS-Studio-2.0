"""Window and fixation-stimulus helpers for the PsychoPy engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fpvs_studio.core.run_spec import RunSpec


def build_window_kwargs(runtime_options: Mapping[str, object]) -> dict[str, object]:
    """Build PsychoPy window keyword arguments from runtime options."""

    test_mode = bool(runtime_options.get("test_mode"))
    fullscreen = bool(runtime_options.get("fullscreen", True))
    display_index = runtime_options.get("display_index")
    window_kwargs: dict[str, object] = {
        "fullscr": fullscreen,
        "screen": display_index if isinstance(display_index, int) else 0,
        "allowGUI": not fullscreen,
        "waitBlanking": True,
        "color": "black",
        "units": "pix",
    }
    if test_mode and not fullscreen:
        window_kwargs["size"] = [1280, 720]
    return window_kwargs


def create_fixation_stim(*, visual: Any, window: Any, run_spec: RunSpec) -> Any:
    """Create the fixation cross stimulus for one run."""

    return visual.ShapeStim(
        window,
        vertices=(
            (0, -(run_spec.fixation.cross_size_px // 2)),
            (0, run_spec.fixation.cross_size_px // 2),
            (0, 0),
            (-(run_spec.fixation.cross_size_px // 2), 0),
            (run_spec.fixation.cross_size_px // 2, 0),
        ),
        closeShape=False,
        lineWidth=run_spec.fixation.line_width_px,
        lineColor=run_spec.fixation.default_color,
        fillColor=None,
        autoLog=False,
    )
