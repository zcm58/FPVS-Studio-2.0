"""Condition-local native scene preparation and precomputed frame draw calls."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from importlib import import_module
from pathlib import Path
from typing import Any

from fpvs_studio.core.paths import resolve_project_relative_path
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.scene_models import SceneStreamSpec, SceneVisual
from fpvs_studio.engines.graphics_readiness import (
    GraphicsMemoryEstimate,
    ImageMemoryRepresentation,
    ImageRenderMemorySpec,
    estimate_unique_image_memory,
)
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourcePreparationError,
    PreparedConditionResources,
    synchronize_gpu,
)


def prepare_scene_visual(
    visual: Any, window: Any, project_root: Path, definition: SceneVisual,
) -> Any:
    """Create one native drawable without rounding source geometry or RGB values."""
    common = {
        "units": definition.units,
        "pos": definition.position,
        "opacity": definition.opacity,
        "colorSpace": "rgb",
        "autoLog": False,
    }
    if definition.kind == "image":
        assert definition.image_path is not None
        return visual.ImageStim(
            window, image=str(resolve_project_relative_path(project_root, definition.image_path)),
            size=definition.size, color=definition.rgb,
            interpolate=definition.interpolate, **common,
        )
    if definition.kind == "circle":
        circle_kwargs = {
            "size": definition.size, "fillColor": definition.rgb,
            "lineColor": definition.line_rgb, "lineWidth": definition.line_width,
            "interpolate": definition.interpolate, **common,
        }
        if definition.edges is None:
            return visual.ShapeStim(window, vertices="circle", **circle_kwargs)
        return visual.Circle(window, radius=0.5, edges=definition.edges, **circle_kwargs)
    if definition.kind == "rectangle":
        assert definition.size is not None
        return visual.Rect(
            window, width=definition.size[0], height=definition.size[1],
            fillColor=definition.rgb, lineColor=definition.line_rgb,
            lineWidth=definition.line_width, interpolate=definition.interpolate, **common,
        )
    require_scene_font(definition.font)
    return visual.TextStim(
        window, text=definition.text, height=definition.text_height,
        font=definition.font, color=definition.rgb,
        wrapWidth=definition.wrap_width, **common,
    )


def require_scene_font(font: str) -> None:
    """Register bundled fonts and reject substitution of an unavailable source font."""
    from fpvs_studio.engines.psychopy_tasks import _register_bundled_task_font

    _register_bundled_task_font(font)
    if not import_module("pyglet.font").have_font(font):
        raise RuntimeError(f"Scene font '{font}' is unavailable; install it before playback.")


def prepare_scene_resources(
    *, visual: Any, window: Any, project_root: Path, run_spec: RunSpec,
    fixation_stimuli: Sequence[Any] = (), gpu_sync: Callable[[], None] | None = None,
) -> PreparedConditionResources:
    """Use the same preparation, GPU barrier, rollback and cleanup owner as FPVS."""
    scene = run_spec.scene_stream
    if scene is None:
        raise ValueError("Scene preparation requires a compiled scene stream.")
    scene.validate_frame_bounds(run_spec.display.total_frames)
    if not run_spec.fixation.show_cross and fixation_stimuli:
        raise ValueError("Hidden fixation crosses must not have prepared fixation stimuli.")
    if any(item.units in {"deg", "cm"} for item in scene.visuals):
        monitor = window.monitor
        monitor.setWidth(run_spec.display.screen_width_cm)
        monitor.setDistance(run_spec.display.viewing_distance_cm)
        monitor.setSizePix(tuple(int(value) for value in window.size))
    resolved_gpu_sync = gpu_sync or synchronize_gpu
    resources = PreparedConditionResources(
        gpu_sync=resolved_gpu_sync, fixation_stimuli=fixation_stimuli,
    )
    try:
        for definition in scene.visuals:
            stimulus = prepare_scene_visual(visual, window, project_root, definition)
            resources._stimuli[("scene", definition.visual_id)] = stimulus
            resources._prepared_sequence.append(stimulus)
        resources._prime_and_synchronize(window=window, gpu_sync=resolved_gpu_sync)
    except BaseException as error:
        cleanup = resources.release()
        if cleanup.failures and isinstance(error, Exception):
            raise ConditionResourcePreparationError(cleanup) from error
        raise
    return resources


def _draw_scene(draws: tuple[Callable[[], None], ...]) -> None:
    for draw in draws:
        draw()


def scene_frame_draws(
    scene: SceneStreamSpec, prepared_visuals: Sequence[Any], total_frames: int,
) -> list[Callable[[], None] | None]:
    """Resolve simultaneous events once, retaining their authored painter order."""
    scene.validate_frame_bounds(total_frames)
    if len(prepared_visuals) != len(scene.visuals):
        raise RuntimeError("Prepared scene visuals do not match the compiled scene.")
    draw_lookup = {
        definition.visual_id: stimulus.draw
        for definition, stimulus in zip(scene.visuals, prepared_visuals, strict=True)
    }
    frame_draws: list[list[Callable[[], None]]] = [[] for _ in range(total_frames)]
    for event in scene.events:
        draw = draw_lookup[event.visual_id]
        for frame in range(event.start_frame, event.start_frame + event.duration_frames):
            frame_draws[frame].append(draw)
    return [partial(_draw_scene, tuple(draws)) if draws else None for draws in frame_draws]


def estimate_scene_image_memory(
    scene: SceneStreamSpec, dimensions: Mapping[str, tuple[int, int]], modes: Mapping[str, str],
) -> GraphicsMemoryEstimate:
    """Budget every scene image using the actual decoded source representation."""
    variants = []
    for definition in scene.visuals:
        if definition.image_path is None:
            continue
        width, height = dimensions[definition.image_path]
        variants.append(ImageRenderMemorySpec(
            render_key=("scene", definition.visual_id), width_px=width, height_px=height,
            representation=(
                ImageMemoryRepresentation.ORDINARY_LUMINANCE_FLOAT
                if modes[definition.image_path] == "L"
                else ImageMemoryRepresentation.ORDINARY_RGBA8
            ),
        ))
    return estimate_unique_image_memory(variants)
