"""Neutral native visuals and compiled frame events for timed condition scenes."""

from __future__ import annotations

from math import isfinite
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from fpvs_studio.core.paths import validate_project_relative_path

RGBChannel = Annotated[float, Field(ge=-1, le=1, allow_inf_nan=False)]
RGB = tuple[RGBChannel, RGBChannel, RGBChannel]
SceneUnit = Literal["deg", "cm", "height", "pix"]
SceneId = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")]


class SceneVisual(BaseModel):
    """An immutable native visual definition, without renderer-specific objects.

    RGB values use signed channels and are retained as authored, without converting
    to eight-bit colors. Sizes and positions share the explicitly selected units.
    Circle size is its bounding-box diameter; edges preserve native polygon detail.
    """

    model_config = ConfigDict(extra="forbid", validate_default=True)

    kind: Literal["image", "text", "circle", "rectangle"]
    visual_id: SceneId
    image_path: str | None = None
    text: str | None = None
    units: SceneUnit = "height"
    position: tuple[float, float] = (0.0, 0.0)
    size: tuple[float, float] | None = None
    text_height: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    font: str = Field(default="Arial", min_length=1)
    rgb: RGB = (1.0, 1.0, 1.0)
    line_rgb: RGB | None = None
    line_width: float = Field(default=1.0, ge=0, allow_inf_nan=False)
    opacity: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)
    edges: int | None = Field(default=None, ge=3, strict=True)
    wrap_width: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    interpolate: bool = True

    @field_validator("image_path")
    @classmethod
    def validate_image_path(cls, value: str | None) -> str | None:
        return validate_project_relative_path(value) if value is not None else None

    @field_validator("font")
    @classmethod
    def validate_font(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Scene font names may not be blank.")
        return value

    @field_validator("position", "size")
    @classmethod
    def validate_geometry(cls, value: tuple[float, float] | None) -> tuple[float, float] | None:
        if value is not None and not all(isfinite(channel) for channel in value):
            raise ValueError("Scene positions and dimensions must be finite.")
        return value

    @model_validator(mode="after")
    def validate_payload(self) -> SceneVisual:
        if self.size is not None and any(value <= 0 for value in self.size):
            raise ValueError("Scene dimensions must be positive.")
        if self.kind == "text":
            if self.text is None or not self.text.strip() or self.image_path is not None:
                raise ValueError("Text visuals require nonblank text and no image path.")
            if self.text_height is None:
                raise ValueError("Text visuals require an exact text height.")
        elif self.kind == "image":
            if self.image_path is None or self.text is not None or self.size is None:
                raise ValueError("Image visuals require an image path and size, without text.")
        elif self.image_path is not None or self.text is not None or self.size is None:
            raise ValueError("Shape visuals require a size, without an image path or text.")
        return self


class SceneEvent(BaseModel):
    """A visual's inclusive onset and exclusive offset, in display frames."""

    model_config = ConfigDict(extra="forbid", validate_default=True)

    visual_id: SceneId
    start_frame: int = Field(ge=0, strict=True)
    duration_frames: int = Field(gt=0, strict=True)
    role: Literal["base", "target", "mask", "fixation", "decoration"] = "base"


class SceneStreamSpec(BaseModel):
    """Compiled scene; event order defines painter order when events overlap.

    The enclosing RunSpec owns total duration. Call validate_frame_bounds against
    that duration at compilation and preflight; gaps are intentional blank frames.
    """

    model_config = ConfigDict(extra="forbid", validate_default=True)

    visuals: list[SceneVisual]
    events: list[SceneEvent]
    background_rgb: RGB = (0.0, 0.0, 0.0)
    target_id: SceneId | None = None
    is_catch_trial: bool | None = None
    requested_soa_ms: float = Field(gt=0, allow_inf_nan=False)
    soa_frames: int = Field(gt=0, strict=True)

    @model_serializer(mode="wrap")
    def serialize_optional_catch(
        self, handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.is_catch_trial is None:
            payload.pop("is_catch_trial", None)
        return payload

    @model_validator(mode="after")
    def validate_references(self) -> SceneStreamSpec:
        visual_ids = [visual.visual_id for visual in self.visuals]
        if not visual_ids or len(visual_ids) != len(set(visual_ids)):
            raise ValueError("Scene visuals require unique, nonempty identities.")
        if not self.events:
            raise ValueError("A scene stream requires at least one timed event.")
        known = set(visual_ids)
        if any(event.visual_id not in known for event in self.events):
            raise ValueError("Scene events reference an unknown visual.")
        if self.target_id is not None and self.target_id not in known:
            raise ValueError("The scene target references an unknown visual.")
        if self.is_catch_trial and (
            self.target_id is not None or any(event.role == "target" for event in self.events)
        ):
            raise ValueError("Catch scenes must not identify or present a target.")
        return self

    def validate_frame_bounds(self, total_frames: int) -> None:
        if isinstance(total_frames, bool) or not isinstance(total_frames, int) or total_frames <= 0:
            raise ValueError("Scene playback requires a positive integer frame count.")
        if any(event.start_frame + event.duration_frames > total_frames for event in self.events):
            raise ValueError("Scene events extend beyond the compiled run duration.")
