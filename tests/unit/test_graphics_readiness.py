"""Focused unit coverage for neutral graphics-memory readiness policy."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.engines.graphics_readiness import (
    AdapterGraphicsBudget,
    AdapterMemoryKind,
    BudgetEvaluationPhase,
    BudgetObservationStatus,
    GraphicsBudgetObservation,
    GraphicsMemoryPolicy,
    GraphicsReadinessStatus,
    ImageMemoryRepresentation,
    ImageRenderMemorySpec,
    RendererClassification,
    classify_renderer,
    estimate_run_spec_image_memory,
    estimate_unique_image_memory,
    evaluate_graphics_readiness,
    image_render_key_for_event,
    observe_windows_graphics_budget,
    probe_renderer_from_gl,
)

MEBIBYTE = 1024 * 1024
GIBIBYTE = 1024 * MEBIBYTE


def _exact_policy() -> GraphicsMemoryPolicy:
    return GraphicsMemoryPolicy(
        estimate_safety_factor=1.0,
        per_variant_driver_overhead_bytes=0,
        local_headroom_fraction=0.20,
        minimum_local_headroom_bytes=0,
        system_headroom_fraction=0.20,
        minimum_system_headroom_bytes=0,
    )


def _small_estimate():
    return estimate_unique_image_memory(
        [
            ImageRenderMemorySpec(
                render_key="base",
                width_px=64,
                height_px=64,
                representation=ImageMemoryRepresentation.ORDINARY_RGBA8,
            )
        ]
    )


def _hardware_renderer():
    return classify_renderer(
        vendor="NVIDIA Corporation",
        renderer="NVIDIA RTX 4000",
        version="4.6",
    )


def _healthy_observation(
    *,
    memory_kind: AdapterMemoryKind = AdapterMemoryKind.DISCRETE,
) -> GraphicsBudgetObservation:
    return GraphicsBudgetObservation(
        status=BudgetObservationStatus.VERIFIED,
        adapters=(
            AdapterGraphicsBudget(
                adapter_id="gpu-0",
                description="Lab GPU",
                memory_kind=memory_kind,
                local_budget_bytes=8 * GIBIBYTE,
                local_usage_bytes=2 * GIBIBYTE,
            ),
        ),
        total_system_memory_bytes=32 * GIBIBYTE,
        available_system_memory_bytes=20 * GIBIBYTE,
    )


@pytest.mark.parametrize(
    ("vendor", "renderer"),
    [
        ("Mesa", "llvmpipe (LLVM 18.1)"),
        ("Microsoft Corporation", "GDI Generic"),
        ("Google", "SwiftShader Device"),
        ("Microsoft", "Microsoft Basic Render Driver"),
    ],
)
def test_classify_renderer_rejects_known_software_paths(vendor: str, renderer: str) -> None:
    result = classify_renderer(vendor=vendor, renderer=renderer)

    assert result.classification == RendererClassification.SOFTWARE


def test_classify_renderer_distinguishes_hardware_unknown_and_dxgi_software() -> None:
    hardware = _hardware_renderer()
    unknown = classify_renderer(vendor="NVIDIA Corporation", renderer=None)
    flagged = classify_renderer(
        vendor="Vendor",
        renderer="Renderer",
        adapter_is_software=True,
    )

    assert hardware.classification == RendererClassification.HARDWARE
    assert unknown.classification == RendererClassification.UNKNOWN
    assert flagged.classification == RendererClassification.SOFTWARE


def test_probe_renderer_uses_injected_gl_module_and_decodes_strings() -> None:
    values = {
        1: b"Intel",
        2: b"Intel(R) Iris(R) Xe Graphics",
        3: b"4.6",
    }
    gl_module = SimpleNamespace(
        GL_VENDOR=1,
        GL_RENDERER=2,
        GL_VERSION=3,
        glGetString=values.get,
    )

    result = probe_renderer_from_gl(gl_module)

    assert result.classification == RendererClassification.HARDWARE
    assert result.vendor == "Intel"
    assert result.renderer == "Intel(R) Iris(R) Xe Graphics"
    assert result.version == "4.6"


def test_probe_renderer_returns_unknown_when_gl_query_fails() -> None:
    result = probe_renderer_from_gl(SimpleNamespace())

    assert result.classification == RendererClassification.UNKNOWN
    assert "query failed" in result.reason


def test_ordinary_memory_estimate_deduplicates_exact_render_keys() -> None:
    variant = ImageRenderMemorySpec(
        render_key=("image", "apple.png"),
        width_px=100,
        height_px=50,
        representation=ImageMemoryRepresentation.ORDINARY_RGBA8,
    )

    estimate = estimate_unique_image_memory([variant, variant], policy=_exact_policy())

    base_bytes = 100 * 50 * 4
    assert estimate.complete is True
    assert estimate.unique_image_variant_count == 1
    assert estimate.ordinary_variant_count == 1
    assert estimate.cover_variant_count == 0
    assert estimate.texture_bytes == (base_bytes * 4 + 2) // 3
    assert estimate.upload_buffer_bytes == base_bytes
    assert estimate.retained_cpu_bytes == 0
    assert estimate.peak_transient_cpu_bytes == base_bytes * 2
    assert estimate.conservative_gpu_bytes == estimate.estimated_gpu_bytes


def test_cover_estimate_uses_rgba8_mipmaps_and_retained_pillow_image() -> None:
    estimate = estimate_unique_image_memory(
        [
            ImageRenderMemorySpec(
                render_key="cover",
                width_px=100,
                height_px=50,
                representation=ImageMemoryRepresentation.COVER_RGBA8,
            )
        ],
        policy=_exact_policy(),
    )

    base_bytes = 100 * 50 * 4
    assert estimate.cover_variant_count == 1
    assert estimate.texture_bytes == (base_bytes * 4 + 2) // 3
    assert estimate.upload_buffer_bytes == base_bytes
    assert estimate.retained_cpu_bytes == base_bytes
    assert estimate.peak_transient_cpu_bytes == base_bytes * 2
    assert estimate.estimated_peak_cpu_bytes == base_bytes * 3


def test_luminance_estimate_covers_psychopy_float_texture_and_pbo(
) -> None:
    estimate = estimate_unique_image_memory(
        [
            ImageRenderMemorySpec(
                render_key="grayscale",
                width_px=100,
                height_px=50,
                representation=ImageMemoryRepresentation.ORDINARY_LUMINANCE_FLOAT,
            )
        ],
        policy=_exact_policy(),
    )

    float_rgb_bytes = 100 * 50 * 12
    assert estimate.texture_bytes == (float_rgb_bytes * 4 + 2) // 3
    assert estimate.upload_buffer_bytes == float_rgb_bytes
    assert estimate.retained_cpu_bytes == 0
    assert estimate.peak_transient_cpu_bytes == 100 * 50 * 17
    assert estimate.estimated_peak_cpu_bytes == 100 * 50 * 17


def test_run_spec_estimate_uses_decoded_luminance_mode(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="luminance-estimate",
    )
    dimensions = {}
    for event in run_spec.stimulus_sequence:
        if event.image_path is None:
            continue
        role = getattr(run_spec.presentation, event.role)
        dimensions[event.image_path] = role.image_geometry.source_resolution.as_tuple()
    modes = {image_path: "L" for image_path in dimensions}

    estimate = estimate_run_spec_image_memory(
        run_spec,
        decoded_dimensions=dimensions,
        decoded_modes=modes,
        policy=_exact_policy(),
    )

    assert estimate.complete is True
    unique_variants = {
        image_render_key_for_event(event, run_spec=run_spec): event
        for event in run_spec.stimulus_sequence
        if event.image_path is not None
    }
    expected_upload_bytes = sum(
        dimensions[event.image_path][0]
        * dimensions[event.image_path][1]
        * (
            4
            if getattr(run_spec.presentation, event.role).image_geometry.mode.value == "cover"
            else 12
        )
        for event in unique_variants.values()
        if event.image_path is not None
    )
    assert estimate.upload_buffer_bytes == expected_upload_bytes


def test_estimate_rejects_conflicting_specs_for_one_render_key() -> None:
    first = ImageRenderMemorySpec(
        render_key="same",
        width_px=100,
        height_px=100,
        representation=ImageMemoryRepresentation.ORDINARY_RGBA8,
    )
    conflicting = ImageRenderMemorySpec(
        render_key="same",
        width_px=200,
        height_px=100,
        representation=ImageMemoryRepresentation.ORDINARY_RGBA8,
    )

    with pytest.raises(ValueError, match="conflicting"):
        estimate_unique_image_memory([first, conflicting])


def test_run_spec_estimate_matches_unique_scheduled_render_identities(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="graphics-estimate",
    )

    estimate = estimate_run_spec_image_memory(run_spec, policy=_exact_policy())
    unique_keys = {
        image_render_key_for_event(event, run_spec=run_spec) for event in run_spec.stimulus_sequence
    }

    assert estimate.complete is True
    assert estimate.unique_image_variant_count == len(unique_keys)
    assert estimate.unique_image_variant_count < len(run_spec.stimulus_sequence)


def test_run_spec_estimate_marks_missing_or_mismatched_decoded_dimensions_unverified(
    sample_project,
    sample_project_root,
) -> None:
    run_spec = compile_run_spec(
        sample_project,
        refresh_hz=60.0,
        project_root=sample_project_root,
        run_id="decoded-dimensions",
    )
    first_path = run_spec.stimulus_sequence[0].image_path
    assert first_path is not None

    missing = estimate_run_spec_image_memory(run_spec, decoded_dimensions={})
    mismatched = estimate_run_spec_image_memory(
        run_spec,
        decoded_dimensions={
            event.image_path: (512, 256)
            for event in run_spec.stimulus_sequence
            if event.image_path is not None
        },
    )

    assert missing.complete is False
    assert "no decoded-dimension record" in missing.issues[0]
    assert mismatched.complete is False
    assert any("not compiled" in issue for issue in mismatched.issues)


def test_windows_budget_observer_reports_unsupported_and_query_failure_explicitly() -> None:
    class _FailingObserver:
        def observe(self) -> GraphicsBudgetObservation:
            raise OSError("DXGI unavailable")

    unsupported = observe_windows_graphics_budget(None, platform_name="linux")
    unconfigured = observe_windows_graphics_budget(None, platform_name="win32")
    failed = observe_windows_graphics_budget(_FailingObserver(), platform_name="win32")

    assert unsupported.status == BudgetObservationStatus.UNSUPPORTED
    assert unconfigured.status == BudgetObservationStatus.UNSUPPORTED
    assert failed.status == BudgetObservationStatus.QUERY_FAILED


def test_windows_budget_observer_accepts_injected_verified_snapshot() -> None:
    expected = _healthy_observation()

    class _Observer:
        def observe(self) -> GraphicsBudgetObservation:
            return expected

    observed = observe_windows_graphics_budget(_Observer(), platform_name="win32")

    assert observed is expected


def test_readiness_passes_only_verified_hardware_with_conservative_headroom() -> None:
    result = evaluate_graphics_readiness(
        renderer=_hardware_renderer(),
        estimate=_small_estimate(),
        observation=_healthy_observation(),
        phase=BudgetEvaluationPhase.BEFORE_UPLOAD,
    )

    assert result.status == GraphicsReadinessStatus.READY
    assert result.ready is True
    assert result.adapter_assessments[0].sufficient is True
    assert result.system_memory_assessment is not None
    assert result.system_memory_assessment.sufficient is True


def test_readiness_never_silently_passes_missing_budget_or_renderer_data() -> None:
    missing_budget = evaluate_graphics_readiness(
        renderer=_hardware_renderer(),
        estimate=_small_estimate(),
        observation=GraphicsBudgetObservation(
            status=BudgetObservationStatus.QUERY_FAILED,
            detail="DXGI query failed.",
        ),
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )
    unknown_renderer = evaluate_graphics_readiness(
        renderer=classify_renderer(vendor=None, renderer=None),
        estimate=_small_estimate(),
        observation=_healthy_observation(),
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert missing_budget.status == GraphicsReadinessStatus.UNVERIFIED
    assert missing_budget.ready is False
    assert unknown_renderer.status == GraphicsReadinessStatus.UNVERIFIED
    assert unknown_renderer.ready is False


def test_readiness_rejects_software_renderer_even_when_memory_is_plentiful() -> None:
    result = evaluate_graphics_readiness(
        renderer=classify_renderer(vendor="Mesa", renderer="llvmpipe"),
        estimate=_small_estimate(),
        observation=_healthy_observation(),
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert result.status == GraphicsReadinessStatus.REJECTED
    assert result.ready is False


def test_readiness_rejects_insufficient_discrete_local_headroom() -> None:
    observation = GraphicsBudgetObservation(
        status=BudgetObservationStatus.VERIFIED,
        adapters=(
            AdapterGraphicsBudget(
                adapter_id="gpu-0",
                description="Small discrete GPU",
                memory_kind=AdapterMemoryKind.DISCRETE,
                local_budget_bytes=GIBIBYTE,
                local_usage_bytes=900 * MEBIBYTE,
            ),
        ),
        total_system_memory_bytes=16 * GIBIBYTE,
        available_system_memory_bytes=8 * GIBIBYTE,
    )

    result = evaluate_graphics_readiness(
        renderer=_hardware_renderer(),
        estimate=_small_estimate(),
        observation=observation,
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert result.status == GraphicsReadinessStatus.REJECTED
    assert result.adapter_assessments[0].sufficient is False


def test_readiness_rejects_uma_when_shared_system_memory_reserve_is_too_low() -> None:
    observation = GraphicsBudgetObservation(
        status=BudgetObservationStatus.VERIFIED,
        adapters=(
            AdapterGraphicsBudget(
                adapter_id="gpu-0",
                description="Integrated GPU",
                memory_kind=AdapterMemoryKind.UMA,
                local_budget_bytes=4 * GIBIBYTE,
                local_usage_bytes=GIBIBYTE,
            ),
        ),
        total_system_memory_bytes=8 * GIBIBYTE,
        available_system_memory_bytes=GIBIBYTE,
    )

    result = evaluate_graphics_readiness(
        renderer=classify_renderer(vendor="Intel", renderer="Intel Iris Xe"),
        estimate=_small_estimate(),
        observation=observation,
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert result.status == GraphicsReadinessStatus.REJECTED
    assert result.system_memory_assessment is not None
    assert result.system_memory_assessment.sufficient is False


def test_before_upload_projection_counts_uma_gpu_bytes_against_system_memory() -> None:
    estimate = _small_estimate()
    observation = _healthy_observation(memory_kind=AdapterMemoryKind.UMA)

    before = evaluate_graphics_readiness(
        renderer=classify_renderer(vendor="AMD", renderer="AMD Radeon Graphics"),
        estimate=estimate,
        observation=observation,
        phase=BudgetEvaluationPhase.BEFORE_UPLOAD,
    )
    after = evaluate_graphics_readiness(
        renderer=classify_renderer(vendor="AMD", renderer="AMD Radeon Graphics"),
        estimate=estimate,
        observation=observation,
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert before.adapter_assessments[0].projected_usage_bytes == (
        after.adapter_assessments[0].projected_usage_bytes + estimate.conservative_gpu_bytes
    )
    assert before.system_memory_assessment is not None
    assert after.system_memory_assessment is not None
    assert before.system_memory_assessment.projected_available_bytes == (
        after.system_memory_assessment.projected_available_bytes
        - estimate.conservative_gpu_bytes
        - estimate.conservative_peak_cpu_bytes
    )


def test_unknown_adapter_architecture_is_unverified_not_ready() -> None:
    result = evaluate_graphics_readiness(
        renderer=_hardware_renderer(),
        estimate=_small_estimate(),
        observation=_healthy_observation(memory_kind=AdapterMemoryKind.UNKNOWN),
        phase=BudgetEvaluationPhase.AFTER_UPLOAD,
    )

    assert result.status == GraphicsReadinessStatus.UNVERIFIED
    assert result.ready is False
