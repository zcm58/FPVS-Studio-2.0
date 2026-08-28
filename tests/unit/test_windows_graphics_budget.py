from __future__ import annotations

from dataclasses import dataclass

import pytest

from fpvs_studio.engines.graphics_readiness import (
    AdapterMemoryKind,
    BudgetObservationStatus,
)
from fpvs_studio.engines.windows_graphics_budget import (
    CtypesWindowsGraphicsBudgetProbe,
    WindowsAdapterMemorySnapshot,
    WindowsGraphicsBudgetObserver,
    WindowsGraphicsBudgetQueryError,
    WindowsGraphicsBudgetUnsupported,
    WindowsSystemMemorySnapshot,
    _AdapterDescription,
    _VideoMemoryInfo,
    activate_renderer_candidates_conservatively,
)


def _adapter(
    adapter_id: str,
    description: str,
    *,
    dedicated_video_memory_bytes: int = 8_000,
    dedicated_system_memory_bytes: int = 0,
    shared_system_memory_bytes: int = 16_000,
    local_budget_bytes: int = 7_000,
    local_usage_bytes: int = 2_000,
    non_local_budget_bytes: int = 12_000,
    non_local_usage_bytes: int = 1_000,
    is_software: bool = False,
) -> WindowsAdapterMemorySnapshot:
    return WindowsAdapterMemorySnapshot(
        adapter_id=adapter_id,
        description=description,
        dedicated_video_memory_bytes=dedicated_video_memory_bytes,
        dedicated_system_memory_bytes=dedicated_system_memory_bytes,
        shared_system_memory_bytes=shared_system_memory_bytes,
        local_budget_bytes=local_budget_bytes,
        local_usage_bytes=local_usage_bytes,
        non_local_budget_bytes=non_local_budget_bytes,
        non_local_usage_bytes=non_local_usage_bytes,
        is_software=is_software,
    )


@dataclass
class _FakeProbe:
    adapters: tuple[WindowsAdapterMemorySnapshot, ...]
    system_memory: WindowsSystemMemorySnapshot = WindowsSystemMemorySnapshot(
        total_bytes=32_000,
        available_bytes=20_000,
    )
    adapter_calls: int = 0
    system_calls: int = 0

    def query_adapters(self) -> tuple[WindowsAdapterMemorySnapshot, ...]:
        self.adapter_calls += 1
        return self.adapters

    def query_system_memory(self) -> WindowsSystemMemorySnapshot:
        self.system_calls += 1
        return self.system_memory


def test_non_windows_observation_is_unsupported_without_calling_probe() -> None:
    probe = _FakeProbe((_adapter("gpu-0", "NVIDIA GeForce RTX 4080"),))

    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="linux",
    ).observe()

    assert observation.status == BudgetObservationStatus.UNSUPPORTED
    assert probe.adapter_calls == 0
    assert probe.system_calls == 0


def test_single_hardware_adapter_is_selected_and_software_adapter_is_marked() -> None:
    probe = _FakeProbe(
        (
            _adapter("gpu-0", "NVIDIA GeForce RTX 4080"),
            _adapter(
                "warp",
                "Microsoft Basic Render Driver",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    assert observation.status == BudgetObservationStatus.VERIFIED
    assert observation.total_system_memory_bytes == 32_000
    assert observation.available_system_memory_bytes == 20_000
    adapter_states = [
        (item.adapter_id, item.is_active, item.is_software)
        for item in observation.adapters
    ]
    assert adapter_states == [
        ("gpu-0", True, False),
        ("warp", False, True),
    ]
    assert observation.adapters[0].memory_kind == AdapterMemoryKind.DISCRETE


def test_renderer_hint_uniquely_selects_matching_adapter_after_normalization() -> None:
    probe = _FakeProbe(
        (
            _adapter("intel", "Intel(R) Arc(TM) A370M Graphics"),
            _adapter("nvidia", "NVIDIA GeForce RTX 4080"),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        renderer_hint=(
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Direct3D11 vs_5_0 ps_5_0)"
        ),
        probe=probe,
        platform_name="win32",
    ).observe()

    assert [item.adapter_id for item in observation.adapters if item.is_active] == ["nvidia"]
    assert "matched the OpenGL renderer" in observation.detail


def test_integrated_adapter_is_reported_as_uma() -> None:
    probe = _FakeProbe(
        (
            _adapter(
                "integrated",
                "Intel UHD Graphics",
                dedicated_video_memory_bytes=0,
                dedicated_system_memory_bytes=0,
                shared_system_memory_bytes=16_000,
            ),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    assert observation.adapters[0].memory_kind == AdapterMemoryKind.UMA
    assert observation.adapters[0].is_active is True


def test_ambiguous_renderer_match_leaves_every_adapter_inactive() -> None:
    probe = _FakeProbe(
        (
            _adapter("gpu-0", "NVIDIA GeForce RTX 4080"),
            _adapter("gpu-1", "NVIDIA GeForce RTX 4080"),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        renderer_hint="NVIDIA GeForce RTX 4080",
        probe=probe,
        platform_name="win32",
    ).observe()

    assert observation.status == BudgetObservationStatus.VERIFIED
    assert not any(item.is_active for item in observation.adapters)
    assert "multiple adapters" in observation.detail
    assert "no active adapter was guessed" in observation.detail


def test_ambiguous_renderer_candidates_can_all_be_activated_for_headroom_checks() -> None:
    renderer = "NVIDIA GeForce RTX 4080/PCIe/SSE2"
    probe = _FakeProbe(
        (
            _adapter("gpu-0", "NVIDIA GeForce RTX 4080"),
            _adapter("gpu-1", "NVIDIA GeForce RTX 4080"),
            _adapter("intel", "Intel Arc A370M"),
            _adapter(
                "software",
                "NVIDIA GeForce RTX 4080",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
        )
    )
    observation = WindowsGraphicsBudgetObserver(
        renderer_hint=renderer,
        probe=probe,
        platform_name="win32",
    ).observe()

    activated = activate_renderer_candidates_conservatively(
        observation,
        renderer_hint=renderer,
    )

    assert [item.adapter_id for item in activated.adapters if item.is_active] == [
        "gpu-0",
        "gpu-1",
    ]
    assert observation.detail in activated.detail
    assert "All 2 compatible non-software renderer candidates" in activated.detail
    assert "no single active adapter was guessed" in activated.detail


@pytest.mark.parametrize("renderer_hint", [None, "", "Unmatched Virtual Renderer"])
def test_candidate_activation_requires_a_matching_renderer_hint(
    renderer_hint: str | None,
) -> None:
    probe = _FakeProbe(
        (
            _adapter("gpu-0", "NVIDIA GeForce RTX 4080"),
            _adapter("gpu-1", "AMD Radeon RX 7900 XTX"),
        )
    )
    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    activated = activate_renderer_candidates_conservatively(
        observation,
        renderer_hint=renderer_hint,
    )

    assert activated is observation


def test_candidate_activation_does_not_replace_an_existing_selection() -> None:
    probe = _FakeProbe((_adapter("gpu-0", "NVIDIA GeForce RTX 4080"),))
    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    activated = activate_renderer_candidates_conservatively(
        observation,
        renderer_hint="NVIDIA GeForce RTX 4080",
    )

    assert activated is observation


def test_candidate_activation_does_not_promote_software_only_match() -> None:
    probe = _FakeProbe(
        (
            _adapter(
                "software-0",
                "Microsoft Basic Render Driver",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
            _adapter(
                "software-1",
                "Microsoft Basic Render Driver",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
        )
    )
    observation = WindowsGraphicsBudgetObserver(
        renderer_hint="Microsoft Basic Render Driver",
        probe=probe,
        platform_name="win32",
    ).observe()

    activated = activate_renderer_candidates_conservatively(
        observation,
        renderer_hint="Microsoft Basic Render Driver",
    )

    assert activated is observation
    assert not any(item.is_active for item in activated.adapters)


def test_unmatched_hint_does_not_guess_between_hardware_and_software() -> None:
    probe = _FakeProbe(
        (
            _adapter("gpu-0", "NVIDIA GeForce RTX 4080"),
            _adapter(
                "warp",
                "Microsoft Basic Render Driver",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        renderer_hint="Unknown virtual renderer",
        probe=probe,
        platform_name="win32",
    ).observe()

    assert not any(item.is_active for item in observation.adapters)
    assert "did not identify one adapter" in observation.detail


def test_only_software_adapter_is_active_so_policy_can_reject_it() -> None:
    probe = _FakeProbe(
        (
            _adapter(
                "warp",
                "Microsoft Basic Render Driver",
                dedicated_video_memory_bytes=0,
                is_software=True,
            ),
        )
    )

    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    assert observation.adapters[0].is_active is True
    assert observation.adapters[0].is_software is True


class _FailingProbe:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def query_adapters(self) -> tuple[WindowsAdapterMemorySnapshot, ...]:
        raise self._error

    def query_system_memory(self) -> WindowsSystemMemorySnapshot:
        raise AssertionError("system-memory query should not run")


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (
            WindowsGraphicsBudgetUnsupported("IDXGIAdapter3 unavailable"),
            BudgetObservationStatus.UNSUPPORTED,
        ),
        (
            WindowsGraphicsBudgetQueryError("budget call failed"),
            BudgetObservationStatus.QUERY_FAILED,
        ),
        (OSError("unexpected native failure"), BudgetObservationStatus.QUERY_FAILED),
    ],
)
def test_native_failures_become_explicit_observation_statuses(
    error: Exception,
    expected_status: BudgetObservationStatus,
) -> None:
    observation = WindowsGraphicsBudgetObserver(
        probe=_FailingProbe(error),
        platform_name="win32",
    ).observe()

    assert observation.status == expected_status
    assert str(error) in observation.detail


def test_invalid_native_values_become_query_failure() -> None:
    probe = _FakeProbe((_adapter("gpu-0", "GPU", local_usage_bytes=-1),))

    observation = WindowsGraphicsBudgetObserver(
        probe=probe,
        platform_name="win32",
    ).observe()

    assert observation.status == BudgetObservationStatus.QUERY_FAILED
    assert "negative memory value" in observation.detail


class _FakeInterop:
    def __init__(self, *, fail_operation: str | None = None) -> None:
        self.fail_operation = fail_operation
        self.released: list[object] = []

    def create_factory(self) -> object:
        return "factory"

    def enum_adapter(self, factory: object, index: int) -> object | None:
        assert factory == "factory"
        return "adapter" if index == 0 else None

    def get_adapter_description(self, adapter: object) -> _AdapterDescription:
        assert adapter == "adapter"
        if self.fail_operation == "description":
            raise WindowsGraphicsBudgetQueryError("description failed")
        return _AdapterDescription(
            adapter_id="00000001:00000002",
            description="NVIDIA GeForce RTX 4080",
            dedicated_video_memory_bytes=8_000,
            dedicated_system_memory_bytes=0,
            shared_system_memory_bytes=16_000,
            is_software=False,
        )

    def query_adapter3(self, adapter: object) -> object:
        assert adapter == "adapter"
        if self.fail_operation == "query_interface":
            raise WindowsGraphicsBudgetUnsupported("IDXGIAdapter3 unavailable")
        return "adapter3"

    def query_video_memory(self, adapter3: object, *, segment_group: int) -> _VideoMemoryInfo:
        assert adapter3 == "adapter3"
        if self.fail_operation == "non_local" and segment_group == 1:
            raise WindowsGraphicsBudgetQueryError("non-local query failed")
        return _VideoMemoryInfo(budget_bytes=7_000, usage_bytes=2_000)

    def release(self, interface: object) -> None:
        self.released.append(interface)


def test_ctypes_probe_releases_all_com_interfaces_after_success() -> None:
    interop = _FakeInterop()
    probe = CtypesWindowsGraphicsBudgetProbe(
        interop_factory=lambda: interop,
        system_memory_query=lambda: WindowsSystemMemorySnapshot(32_000, 20_000),
    )

    snapshots = probe.query_adapters()

    assert snapshots[0].adapter_id == "00000001:00000002"
    assert interop.released == ["adapter3", "adapter", "factory"]


@pytest.mark.parametrize(
    ("operation", "expected_releases"),
    [
        ("description", ["adapter", "factory"]),
        ("query_interface", ["adapter", "factory"]),
        ("non_local", ["adapter3", "adapter", "factory"]),
    ],
)
def test_ctypes_probe_releases_acquired_com_interfaces_after_failure(
    operation: str,
    expected_releases: list[object],
) -> None:
    interop = _FakeInterop(fail_operation=operation)
    probe = CtypesWindowsGraphicsBudgetProbe(interop_factory=lambda: interop)

    with pytest.raises((WindowsGraphicsBudgetQueryError, WindowsGraphicsBudgetUnsupported)):
        probe.query_adapters()

    assert interop.released == expected_releases


def test_ctypes_probe_uses_injected_system_memory_query() -> None:
    expected = WindowsSystemMemorySnapshot(total_bytes=64_000, available_bytes=48_000)
    probe = CtypesWindowsGraphicsBudgetProbe(
        interop_factory=_FakeInterop,
        system_memory_query=lambda: expected,
    )

    assert probe.query_system_memory() == expected
