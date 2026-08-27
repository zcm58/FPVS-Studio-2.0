"""Neutral graphics-memory readiness helpers for condition-local preparation.

The helpers in this module deliberately avoid importing PsychoPy or OpenGL.  A live
engine may pass its already-loaded OpenGL module to :func:`probe_renderer_from_gl`,
and Windows-specific DXGI access is supplied through an injected observer.  This
keeps import boundaries lazy while making unsupported or failed diagnostics explicit.
"""

from __future__ import annotations

import sys
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from math import ceil, isfinite
from typing import Any, Protocol

from fpvs_studio.core.enums import ImageGeometryMode, StimulusModality, StimulusTransform
from fpvs_studio.core.run_spec import RunSpec, StimulusEvent

MEBIBYTE = 1024 * 1024
_MIPMAP_NUMERATOR = 4
_MIPMAP_DENOMINATOR = 3
_RGBA8_BYTES_PER_PIXEL = 4


class RendererClassification(str, Enum):
    """Timing-relevant classification of the active OpenGL renderer."""

    HARDWARE = "hardware"
    SOFTWARE = "software"
    UNKNOWN = "unknown"


class ImageMemoryRepresentation(str, Enum):
    """Decoded representation used by PsychoPy for one prepared image variant."""

    ORDINARY_RGBA8 = "ordinary_rgba8"
    COVER_RGBA8 = "cover_rgba8"
    ORDINARY_LUMINANCE_FLOAT = "ordinary_luminance_float"


class AdapterMemoryKind(str, Enum):
    """Physical-memory layout exposed by an adapter budget observer."""

    DISCRETE = "discrete"
    UMA = "uma"
    UNKNOWN = "unknown"


class BudgetObservationStatus(str, Enum):
    """Whether Windows graphics-memory budget telemetry is usable."""

    VERIFIED = "verified"
    UNSUPPORTED = "unsupported"
    QUERY_FAILED = "query_failed"


class BudgetEvaluationPhase(str, Enum):
    """Whether condition allocations are projected or already represented in usage."""

    BEFORE_UPLOAD = "before_upload"
    AFTER_UPLOAD = "after_upload"


class GraphicsReadinessStatus(str, Enum):
    """Outcome of the conservative production-readiness policy."""

    READY = "ready"
    REJECTED = "rejected"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class GraphicsMemoryPolicy:
    """Conservative, configurable headroom and estimation policy."""

    estimate_safety_factor: float = 1.5
    per_variant_driver_overhead_bytes: int = 256 * 1024
    local_headroom_fraction: float = 0.20
    minimum_local_headroom_bytes: int = 256 * MEBIBYTE
    system_headroom_fraction: float = 0.20
    minimum_system_headroom_bytes: int = 1024 * MEBIBYTE

    def __post_init__(self) -> None:
        if not isfinite(self.estimate_safety_factor) or self.estimate_safety_factor < 1.0:
            raise ValueError("Graphics-memory estimate safety factor must be at least 1.0.")
        for field_name in ("local_headroom_fraction", "system_headroom_fraction"):
            value = getattr(self, field_name)
            if not isfinite(value) or value < 0.0 or value >= 1.0:
                raise ValueError(f"{field_name} must be finite and in the range [0, 1).")
        for field_name in (
            "per_variant_driver_overhead_bytes",
            "minimum_local_headroom_bytes",
            "minimum_system_headroom_bytes",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer byte count.")


DEFAULT_GRAPHICS_MEMORY_POLICY = GraphicsMemoryPolicy()


@dataclass(frozen=True)
class RendererInfo:
    """Neutral OpenGL renderer strings and their timing classification."""

    vendor: str | None
    renderer: str | None
    version: str | None
    classification: RendererClassification
    reason: str


@dataclass(frozen=True)
class ImageRenderMemorySpec:
    """Decoded dimensions and representation for one immutable render identity."""

    render_key: Hashable
    width_px: int
    height_px: int
    representation: ImageMemoryRepresentation

    def __post_init__(self) -> None:
        try:
            hash(self.render_key)
        except TypeError as exc:
            raise ValueError("Image render keys must be hashable.") from exc
        for field_name in ("width_px", "height_px"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer.")


@dataclass(frozen=True)
class GraphicsMemoryEstimate:
    """Conservative memory estimate for all unique image render variants."""

    complete: bool
    unique_image_variant_count: int
    ordinary_variant_count: int
    cover_variant_count: int
    texture_bytes: int
    upload_buffer_bytes: int
    driver_overhead_bytes: int
    retained_cpu_bytes: int
    peak_transient_cpu_bytes: int
    estimated_gpu_bytes: int
    conservative_gpu_bytes: int
    estimated_peak_cpu_bytes: int
    conservative_peak_cpu_bytes: int
    issues: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdapterGraphicsBudget:
    """Current-process budget values for one active or candidate DXGI adapter."""

    adapter_id: str
    description: str
    memory_kind: AdapterMemoryKind
    local_budget_bytes: int
    local_usage_bytes: int
    non_local_budget_bytes: int = 0
    non_local_usage_bytes: int = 0
    is_active: bool = True
    is_software: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "local_budget_bytes",
            "local_usage_bytes",
            "non_local_budget_bytes",
            "non_local_usage_bytes",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer byte count.")


@dataclass(frozen=True)
class GraphicsBudgetObservation:
    """Neutral result returned by an injected Windows/DXGI budget observer."""

    status: BudgetObservationStatus
    adapters: tuple[AdapterGraphicsBudget, ...] = ()
    total_system_memory_bytes: int | None = None
    available_system_memory_bytes: int | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        for field_name in ("total_system_memory_bytes", "available_system_memory_bytes"):
            value = getattr(self, field_name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int) or value < 0
            ):
                raise ValueError(f"{field_name} must be None or a non-negative byte count.")
        if (
            self.total_system_memory_bytes is not None
            and self.available_system_memory_bytes is not None
            and self.available_system_memory_bytes > self.total_system_memory_bytes
        ):
            raise ValueError("Available system memory cannot exceed total system memory.")


class WindowsDxgiBudgetObserver(Protocol):
    """Injectable boundary for platform-specific DXGI and system-memory queries."""

    def observe(self) -> GraphicsBudgetObservation:
        """Return the current process's adapter budgets and physical-memory state."""


@dataclass(frozen=True)
class AdapterHeadroomAssessment:
    """Conservative local-memory projection for one active adapter."""

    adapter_id: str
    description: str
    memory_kind: AdapterMemoryKind
    budget_bytes: int
    current_usage_bytes: int
    projected_usage_bytes: int
    required_headroom_bytes: int
    projected_headroom_bytes: int
    sufficient: bool


@dataclass(frozen=True)
class SystemMemoryHeadroomAssessment:
    """Conservative physical-memory projection for condition preparation."""

    total_bytes: int
    available_bytes: int
    projected_available_bytes: int
    required_headroom_bytes: int
    sufficient: bool


@dataclass(frozen=True)
class GraphicsReadinessResult:
    """Production-readiness decision with no implicit pass state."""

    status: GraphicsReadinessStatus
    reasons: tuple[str, ...]
    renderer: RendererInfo
    estimate: GraphicsMemoryEstimate
    budget_status: BudgetObservationStatus
    adapter_assessments: tuple[AdapterHeadroomAssessment, ...] = ()
    system_memory_assessment: SystemMemoryHeadroomAssessment | None = None

    @property
    def ready(self) -> bool:
        """Return whether timing-valid playback may proceed."""

        return self.status == GraphicsReadinessStatus.READY


_SOFTWARE_RENDERER_MARKERS = (
    "gdi generic",
    "microsoft basic render driver",
    "llvmpipe",
    "softpipe",
    "swiftshader",
    "software rasterizer",
    "software renderer",
    "warp",
)


def classify_renderer(
    *,
    vendor: str | None,
    renderer: str | None,
    version: str | None = None,
    adapter_is_software: bool | None = None,
) -> RendererInfo:
    """Classify renderer strings without assuming that missing data means hardware."""

    normalized_vendor = _clean_optional_string(vendor)
    normalized_renderer = _clean_optional_string(renderer)
    normalized_version = _clean_optional_string(version)
    if adapter_is_software is True:
        return RendererInfo(
            vendor=normalized_vendor,
            renderer=normalized_renderer,
            version=normalized_version,
            classification=RendererClassification.SOFTWARE,
            reason="The active DXGI adapter is flagged as a software adapter.",
        )

    combined = " ".join(
        value.casefold() for value in (normalized_vendor, normalized_renderer) if value
    )
    marker = next((item for item in _SOFTWARE_RENDERER_MARKERS if item in combined), None)
    if marker is not None:
        return RendererInfo(
            vendor=normalized_vendor,
            renderer=normalized_renderer,
            version=normalized_version,
            classification=RendererClassification.SOFTWARE,
            reason=f"The OpenGL renderer identifies a software path ('{marker}').",
        )
    if normalized_renderer is None:
        return RendererInfo(
            vendor=normalized_vendor,
            renderer=None,
            version=normalized_version,
            classification=RendererClassification.UNKNOWN,
            reason="The active OpenGL renderer string is unavailable.",
        )
    return RendererInfo(
        vendor=normalized_vendor,
        renderer=normalized_renderer,
        version=normalized_version,
        classification=RendererClassification.HARDWARE,
        reason="The OpenGL renderer string does not identify a known software renderer.",
    )


def probe_renderer_from_gl(
    gl_module: Any,
    *,
    adapter_is_software: bool | None = None,
) -> RendererInfo:
    """Read renderer strings from an already-loaded OpenGL module.

    The caller owns the current context and the lazy OpenGL/PsychoPy import.  Query
    failures return an explicit ``unknown`` classification.
    """

    try:
        gl_get_string = gl_module.glGetString
        if not callable(gl_get_string):
            raise TypeError("glGetString is not callable")
        vendor = _decode_gl_string(gl_get_string(gl_module.GL_VENDOR))
        renderer = _decode_gl_string(gl_get_string(gl_module.GL_RENDERER))
        version = _decode_gl_string(gl_get_string(gl_module.GL_VERSION))
    except Exception as exc:
        return RendererInfo(
            vendor=None,
            renderer=None,
            version=None,
            classification=RendererClassification.UNKNOWN,
            reason=f"OpenGL renderer query failed ({type(exc).__name__}).",
        )
    return classify_renderer(
        vendor=vendor,
        renderer=renderer,
        version=version,
        adapter_is_software=adapter_is_software,
    )


def image_render_key_for_event(event: StimulusEvent, *, run_spec: RunSpec) -> tuple[object, ...]:
    """Return the immutable image identity used for unique preparation and estimates."""

    if event.stimulus_modality != StimulusModality.IMAGE:
        raise ValueError("Only image events have an image render key.")
    role_spec = (
        getattr(run_spec.presentation, event.role) if run_spec.presentation is not None else None
    )
    geometry = role_spec.image_geometry if role_spec is not None else None
    transform = role_spec.transform if role_spec is not None else StimulusTransform.NONE
    return (
        "image",
        event.image_path,
        transform.value,
        geometry.mode.value if geometry is not None else "legacy_natural_aspect",
        geometry.width_degrees if geometry is not None else run_spec.display.stimulus_width_degrees,
        geometry.height_degrees if geometry is not None else None,
        geometry.source_resolution.width_px if geometry is not None else None,
        geometry.source_resolution.height_px if geometry is not None else None,
    )


def estimate_unique_image_memory(
    variants: Iterable[ImageRenderMemorySpec],
    *,
    policy: GraphicsMemoryPolicy = DEFAULT_GRAPHICS_MEMORY_POLICY,
) -> GraphicsMemoryEstimate:
    """Estimate unique decoded/uploaded image variants conservatively.

    Color sources are budgeted as RGBA8. PsychoPy expands Pillow mode-L sources to a
    three-channel float32 upload/PBO and an RGB16F or RGB32F texture; luminance variants
    therefore use the vendor-independent RGB32F worst case. Cover crops additionally
    retain their decoded Pillow image. Every representation includes a full mip chain,
    upload buffer, driver allowance, and sequential-preparation CPU scratch space.
    """

    unique: dict[Hashable, ImageRenderMemorySpec] = {}
    for variant in variants:
        existing = unique.get(variant.render_key)
        if existing is not None and existing != variant:
            raise ValueError("One render key cannot describe conflicting memory variants.")
        unique[variant.render_key] = variant

    ordinary_count = 0
    cover_count = 0
    texture_bytes = 0
    upload_buffer_bytes = 0
    retained_cpu_bytes = 0
    peak_transient_cpu_bytes = 0
    for variant in unique.values():
        pixel_count = variant.width_px * variant.height_px
        is_cover = variant.representation in {
            ImageMemoryRepresentation.COVER_RGBA8,
        }
        is_luminance_float = variant.representation in {
            ImageMemoryRepresentation.ORDINARY_LUMINANCE_FLOAT,
        }
        if is_cover:
            cover_count += 1
        else:
            ordinary_count += 1

        if is_luminance_float:
            texture_base_bytes = pixel_count * 12
            upload_bytes = pixel_count * 12
            if is_cover:
                retained_cpu_bytes += pixel_count
                transient_bytes = pixel_count * 16
            else:
                transient_bytes = pixel_count * 17
        else:
            base_bytes = pixel_count * _RGBA8_BYTES_PER_PIXEL
            texture_base_bytes = base_bytes
            upload_bytes = base_bytes
            if is_cover:
                retained_cpu_bytes += base_bytes
            transient_bytes = base_bytes * 2
        texture_bytes += _mipmapped_bytes(texture_base_bytes)
        upload_buffer_bytes += upload_bytes
        peak_transient_cpu_bytes = max(peak_transient_cpu_bytes, transient_bytes)

    driver_overhead_bytes = len(unique) * policy.per_variant_driver_overhead_bytes
    estimated_gpu_bytes = texture_bytes + upload_buffer_bytes + driver_overhead_bytes
    estimated_peak_cpu_bytes = retained_cpu_bytes + peak_transient_cpu_bytes
    return GraphicsMemoryEstimate(
        complete=True,
        unique_image_variant_count=len(unique),
        ordinary_variant_count=ordinary_count,
        cover_variant_count=cover_count,
        texture_bytes=texture_bytes,
        upload_buffer_bytes=upload_buffer_bytes,
        driver_overhead_bytes=driver_overhead_bytes,
        retained_cpu_bytes=retained_cpu_bytes,
        peak_transient_cpu_bytes=peak_transient_cpu_bytes,
        estimated_gpu_bytes=estimated_gpu_bytes,
        conservative_gpu_bytes=ceil(estimated_gpu_bytes * policy.estimate_safety_factor),
        estimated_peak_cpu_bytes=estimated_peak_cpu_bytes,
        conservative_peak_cpu_bytes=ceil(estimated_peak_cpu_bytes * policy.estimate_safety_factor),
    )


def estimate_run_spec_image_memory(
    run_spec: RunSpec,
    *,
    decoded_dimensions: Mapping[str, tuple[int, int]] | None = None,
    decoded_modes: Mapping[str, str] | None = None,
    policy: GraphicsMemoryPolicy = DEFAULT_GRAPHICS_MEMORY_POLICY,
) -> GraphicsMemoryEstimate:
    """Estimate all unique image render variants scheduled by one ``RunSpec``.

    Compiled source dimensions are used when no decoded-dimension mapping is supplied.
    Supplying mappings lets condition preparation use dimensions and Pillow modes read
    from the actual assets. Missing or mismatched decoded dimensions make the estimate
    explicitly incomplete; they never fall back silently to compiled values. If modes
    are not supplied, the estimator uses PsychoPy's larger mode-L float path as the safe
    unknown-source default.
    """

    variants: list[ImageRenderMemorySpec] = []
    issues: list[str] = []
    for event in run_spec.stimulus_sequence:
        if event.stimulus_modality != StimulusModality.IMAGE:
            continue
        if event.image_path is None:
            issues.append(f"Image event '{event.stimulus_id}' has no image path.")
            continue
        role_spec = (
            getattr(run_spec.presentation, event.role)
            if run_spec.presentation is not None
            else None
        )
        geometry = role_spec.image_geometry if role_spec is not None else None
        if geometry is None and decoded_dimensions is None:
            issues.append(
                f"Image event '{event.stimulus_id}' has no compiled or decoded dimensions."
            )
            continue

        compiled_size = geometry.source_resolution.as_tuple() if geometry is not None else None
        if decoded_dimensions is None:
            assert compiled_size is not None
            source_size = compiled_size
        else:
            source_size = decoded_dimensions.get(event.image_path)
            if source_size is None:
                issues.append(f"Image '{event.image_path}' has no decoded-dimension record.")
                continue
            if not _valid_dimensions(source_size):
                issues.append(f"Image '{event.image_path}' has invalid decoded dimensions.")
                continue
            if compiled_size is not None and source_size != compiled_size:
                issues.append(
                    f"Image '{event.image_path}' decoded as {source_size[0]}x{source_size[1]}, "
                    f"not compiled {compiled_size[0]}x{compiled_size[1]}."
                )

        decoded_mode = decoded_modes.get(event.image_path) if decoded_modes is not None else None
        if decoded_modes is not None and decoded_mode is None:
            issues.append(f"Image '{event.image_path}' has no decoded-mode record.")
            continue
        is_luminance = decoded_mode is None or decoded_mode == "L"
        is_cover = geometry is not None and geometry.mode == ImageGeometryMode.COVER
        if is_cover:
            representation = ImageMemoryRepresentation.COVER_RGBA8
        elif is_luminance:
            representation = ImageMemoryRepresentation.ORDINARY_LUMINANCE_FLOAT
        else:
            representation = ImageMemoryRepresentation.ORDINARY_RGBA8
        variants.append(
            ImageRenderMemorySpec(
                render_key=image_render_key_for_event(event, run_spec=run_spec),
                width_px=source_size[0],
                height_px=source_size[1],
                representation=representation,
            )
        )

    estimate = estimate_unique_image_memory(variants, policy=policy)
    unique_issues = tuple(dict.fromkeys(issues))
    return replace(estimate, complete=not unique_issues, issues=unique_issues)


def observe_windows_graphics_budget(
    observer: WindowsDxgiBudgetObserver | None,
    *,
    platform_name: str | None = None,
) -> GraphicsBudgetObservation:
    """Call an injected DXGI observer without converting absence or failure to success."""

    active_platform = sys.platform if platform_name is None else platform_name
    if active_platform != "win32":
        return GraphicsBudgetObservation(
            status=BudgetObservationStatus.UNSUPPORTED,
            detail=f"DXGI graphics-memory budgets are unsupported on '{active_platform}'.",
        )
    if observer is None:
        return GraphicsBudgetObservation(
            status=BudgetObservationStatus.UNSUPPORTED,
            detail="No Windows DXGI graphics-memory budget observer is configured.",
        )
    try:
        observation = observer.observe()
    except Exception as exc:
        return GraphicsBudgetObservation(
            status=BudgetObservationStatus.QUERY_FAILED,
            detail=f"Windows graphics-memory budget query failed ({type(exc).__name__}).",
        )
    if not isinstance(observation, GraphicsBudgetObservation):
        return GraphicsBudgetObservation(
            status=BudgetObservationStatus.QUERY_FAILED,
            detail="Windows graphics-memory observer returned an invalid result.",
        )
    return observation


def evaluate_graphics_readiness(
    *,
    renderer: RendererInfo,
    estimate: GraphicsMemoryEstimate,
    observation: GraphicsBudgetObservation,
    phase: BudgetEvaluationPhase,
    policy: GraphicsMemoryPolicy = DEFAULT_GRAPHICS_MEMORY_POLICY,
) -> GraphicsReadinessResult:
    """Apply renderer, DXGI, and physical-memory policy with no silent pass."""

    rejection_reasons: list[str] = []
    unverified_reasons: list[str] = []
    adapter_assessments: list[AdapterHeadroomAssessment] = []
    system_assessment: SystemMemoryHeadroomAssessment | None = None

    if renderer.classification == RendererClassification.SOFTWARE:
        rejection_reasons.append(renderer.reason)
    elif renderer.classification == RendererClassification.UNKNOWN:
        unverified_reasons.append(renderer.reason)

    if not estimate.complete:
        unverified_reasons.extend(estimate.issues or ("The image-memory estimate is incomplete.",))

    active_adapters: tuple[AdapterGraphicsBudget, ...] = ()
    if observation.status != BudgetObservationStatus.VERIFIED:
        unverified_reasons.append(
            observation.detail or "Graphics-memory budget telemetry is unavailable."
        )
    else:
        active_adapters = tuple(adapter for adapter in observation.adapters if adapter.is_active)
        if not active_adapters:
            unverified_reasons.append("No active DXGI adapter budget was identified.")

    projected_condition_gpu_bytes = (
        estimate.conservative_gpu_bytes if phase == BudgetEvaluationPhase.BEFORE_UPLOAD else 0
    )
    for adapter in active_adapters:
        if adapter.is_software:
            rejection_reasons.append(
                f"Active adapter '{adapter.description}' is flagged as software-rendered."
            )
        if adapter.memory_kind == AdapterMemoryKind.UNKNOWN:
            unverified_reasons.append(
                f"Active adapter '{adapter.description}' has an unknown memory architecture."
            )
        if adapter.local_budget_bytes <= 0:
            unverified_reasons.append(
                f"Active adapter '{adapter.description}' reported no usable local budget."
            )
            continue

        required_headroom = max(
            policy.minimum_local_headroom_bytes,
            ceil(adapter.local_budget_bytes * policy.local_headroom_fraction),
        )
        projected_usage = adapter.local_usage_bytes + projected_condition_gpu_bytes
        projected_headroom = adapter.local_budget_bytes - projected_usage
        sufficient = projected_headroom >= required_headroom
        adapter_assessments.append(
            AdapterHeadroomAssessment(
                adapter_id=adapter.adapter_id,
                description=adapter.description,
                memory_kind=adapter.memory_kind,
                budget_bytes=adapter.local_budget_bytes,
                current_usage_bytes=adapter.local_usage_bytes,
                projected_usage_bytes=projected_usage,
                required_headroom_bytes=required_headroom,
                projected_headroom_bytes=projected_headroom,
                sufficient=sufficient,
            )
        )
        if not sufficient:
            rejection_reasons.append(
                f"Active adapter '{adapter.description}' would leave "
                f"{max(projected_headroom, 0)} bytes of local headroom; "
                f"{required_headroom} bytes are required."
            )

    total_system = observation.total_system_memory_bytes
    available_system = observation.available_system_memory_bytes
    if observation.status == BudgetObservationStatus.VERIFIED:
        if total_system is None or available_system is None or total_system <= 0:
            unverified_reasons.append("Physical-memory availability was not reported.")
        else:
            required_system_headroom = max(
                policy.minimum_system_headroom_bytes,
                ceil(total_system * policy.system_headroom_fraction),
            )
            projected_system_cost = 0
            if phase == BudgetEvaluationPhase.BEFORE_UPLOAD:
                projected_system_cost = estimate.conservative_peak_cpu_bytes
                if any(adapter.memory_kind == AdapterMemoryKind.UMA for adapter in active_adapters):
                    projected_system_cost += estimate.conservative_gpu_bytes
            projected_available = available_system - projected_system_cost
            sufficient = projected_available >= required_system_headroom
            system_assessment = SystemMemoryHeadroomAssessment(
                total_bytes=total_system,
                available_bytes=available_system,
                projected_available_bytes=projected_available,
                required_headroom_bytes=required_system_headroom,
                sufficient=sufficient,
            )
            if not sufficient:
                rejection_reasons.append(
                    "Condition preparation would leave "
                    f"{max(projected_available, 0)} bytes of physical-memory headroom; "
                    f"{required_system_headroom} bytes are required."
                )

    if rejection_reasons:
        status = GraphicsReadinessStatus.REJECTED
        reasons = tuple(dict.fromkeys((*rejection_reasons, *unverified_reasons)))
    elif unverified_reasons:
        status = GraphicsReadinessStatus.UNVERIFIED
        reasons = tuple(dict.fromkeys(unverified_reasons))
    else:
        status = GraphicsReadinessStatus.READY
        reasons = ("Hardware renderer and memory budgets meet the conservative headroom policy.",)
    return GraphicsReadinessResult(
        status=status,
        reasons=reasons,
        renderer=renderer,
        estimate=estimate,
        budget_status=observation.status,
        adapter_assessments=tuple(adapter_assessments),
        system_memory_assessment=system_assessment,
    )


def _mipmapped_bytes(base_bytes: int) -> int:
    return (base_bytes * _MIPMAP_NUMERATOR + _MIPMAP_DENOMINATOR - 1) // (_MIPMAP_DENOMINATOR)


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _decode_gl_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return _clean_optional_string(value.decode("utf-8", errors="replace"))
    return _clean_optional_string(str(value))


def _valid_dimensions(value: tuple[int, int]) -> bool:
    return len(value) == 2 and all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in value
    )
