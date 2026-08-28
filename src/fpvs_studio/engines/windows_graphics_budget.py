"""Read-only Windows DXGI graphics-budget observation.

The public observer in this module converts native Windows telemetry into the
engine-neutral contracts in :mod:`fpvs_studio.engines.graphics_readiness`.
Windows DLLs and COM entry points are loaded only when ``observe()`` actually
runs on Windows.  Adapter selection is intentionally conservative: a renderer
hint must identify exactly one adapter, or the machine must expose exactly one
hardware adapter with no contradictory hint.
"""

from __future__ import annotations

import ctypes
import re
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any, Protocol

from fpvs_studio.engines.graphics_readiness import (
    AdapterGraphicsBudget,
    AdapterMemoryKind,
    BudgetObservationStatus,
    GraphicsBudgetObservation,
)

_S_OK = 0
_E_NOINTERFACE = 0x80004002
_DXGI_ERROR_NOT_FOUND = 0x887A0002
_DXGI_ADAPTER_FLAG_SOFTWARE = 0x2
_DXGI_MEMORY_SEGMENT_GROUP_LOCAL = 0
_DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL = 1

_IID_IDXGI_FACTORY1 = "770aae78-f26f-4dba-a829-253c83d1b387"
_IID_IDXGI_ADAPTER3 = "645967a4-1392-4310-a798-8053ce3e93fd"

_FACTORY_ENUM_ADAPTERS1_VTABLE_INDEX = 12
_ADAPTER_GET_DESC1_VTABLE_INDEX = 10
_ADAPTER_QUERY_VIDEO_MEMORY_INFO_VTABLE_INDEX = 14
_IUnknown_QUERY_INTERFACE_VTABLE_INDEX = 0
_IUnknown_RELEASE_VTABLE_INDEX = 2

_RENDERER_NOISE_TOKENS = frozenset(
    {
        "adapter",
        "angle",
        "corporation",
        "corp",
        "d3d11",
        "direct3d",
        "driver",
        "gpu",
        "inc",
        "incorporated",
        "ltd",
        "opengl",
        "pci",
        "pcie",
        "r",
        "renderer",
        "sse2",
        "tm",
        "vulkan",
    }
)


class WindowsGraphicsBudgetUnsupported(RuntimeError):
    """Signal that the required Windows or DXGI 1.4 API is unavailable."""


class WindowsGraphicsBudgetQueryError(RuntimeError):
    """Signal that an available Windows graphics-memory query failed."""


@dataclass(frozen=True)
class WindowsAdapterMemorySnapshot:
    """Native adapter description and per-process DXGI budget values."""

    adapter_id: str
    description: str
    dedicated_video_memory_bytes: int
    dedicated_system_memory_bytes: int
    shared_system_memory_bytes: int
    local_budget_bytes: int
    local_usage_bytes: int
    non_local_budget_bytes: int
    non_local_usage_bytes: int
    is_software: bool


@dataclass(frozen=True)
class WindowsSystemMemorySnapshot:
    """Physical-memory values returned by ``GlobalMemoryStatusEx``."""

    total_bytes: int
    available_bytes: int


class WindowsGraphicsBudgetProbe(Protocol):
    """Injectable native-query seam used by :class:`WindowsGraphicsBudgetObserver`."""

    def query_adapters(self) -> tuple[WindowsAdapterMemorySnapshot, ...]:
        """Return every adapter exposed by ``IDXGIFactory1``."""

    def query_system_memory(self) -> WindowsSystemMemorySnapshot:
        """Return current physical-memory totals."""


class WindowsGraphicsBudgetObserver:
    """Observe DXGI budgets and identify the active adapter conservatively."""

    def __init__(
        self,
        renderer_hint: str | None = None,
        *,
        probe: WindowsGraphicsBudgetProbe | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._renderer_hint = renderer_hint
        self._probe = probe
        self._platform_name = sys.platform if platform_name is None else platform_name

    def observe(self) -> GraphicsBudgetObservation:
        """Return neutral budget telemetry without treating uncertainty as success."""

        if self._platform_name != "win32":
            return GraphicsBudgetObservation(
                status=BudgetObservationStatus.UNSUPPORTED,
                detail=(
                    "DXGI graphics-memory budgets are available only on Windows; "
                    f"current platform is '{self._platform_name}'."
                ),
            )

        probe = self._probe or CtypesWindowsGraphicsBudgetProbe()
        try:
            native_adapters = probe.query_adapters()
            system_memory = probe.query_system_memory()
            if not native_adapters:
                raise WindowsGraphicsBudgetQueryError("DXGI reported no adapters.")
            _validate_native_snapshots(native_adapters, system_memory)
        except WindowsGraphicsBudgetUnsupported as exc:
            return GraphicsBudgetObservation(
                status=BudgetObservationStatus.UNSUPPORTED,
                detail=str(exc) or "DXGI 1.4 graphics-memory budgets are unavailable.",
            )
        except Exception as exc:
            return GraphicsBudgetObservation(
                status=BudgetObservationStatus.QUERY_FAILED,
                detail=f"Windows graphics-memory budget query failed: {exc}",
            )

        active_adapter_id, selection_detail = _select_active_adapter(
            native_adapters,
            renderer_hint=self._renderer_hint,
        )
        adapters = tuple(
            AdapterGraphicsBudget(
                adapter_id=adapter.adapter_id,
                description=adapter.description,
                memory_kind=_memory_kind(adapter),
                local_budget_bytes=adapter.local_budget_bytes,
                local_usage_bytes=adapter.local_usage_bytes,
                non_local_budget_bytes=adapter.non_local_budget_bytes,
                non_local_usage_bytes=adapter.non_local_usage_bytes,
                is_active=adapter.adapter_id == active_adapter_id,
                is_software=adapter.is_software,
            )
            for adapter in native_adapters
        )
        return GraphicsBudgetObservation(
            status=BudgetObservationStatus.VERIFIED,
            adapters=adapters,
            total_system_memory_bytes=system_memory.total_bytes,
            available_system_memory_bytes=system_memory.available_bytes,
            detail=selection_detail,
        )


def activate_renderer_candidates_conservatively(
    observation: GraphicsBudgetObservation,
    *,
    renderer_hint: str | None,
) -> GraphicsBudgetObservation:
    """Evaluate every plausible hardware adapter when one cannot be identified.

    DXGI can expose duplicate logical adapter entries with the same renderer
    description.  Selecting one would be a guess, while leaving all entries inactive
    makes otherwise usable telemetry unverifiable.  This helper instead marks every
    non-software description compatible with the OpenGL renderer as active.  The
    neutral evaluator will then require *all* candidates to meet its headroom policy.

    Missing renderer information, failed telemetry, an already-selected adapter, and
    a renderer with no hardware candidates leave the observation unchanged.
    """

    if observation.status != BudgetObservationStatus.VERIFIED:
        return observation
    if any(adapter.is_active for adapter in observation.adapters):
        return observation

    normalized_hint = _normalize_renderer_identity(renderer_hint)
    if not normalized_hint:
        return observation
    candidate_ids = frozenset(
        adapter.adapter_id
        for adapter in observation.adapters
        if not adapter.is_software
        and _renderer_identities_compatible(
            normalized_hint,
            _normalize_renderer_identity(adapter.description),
        )
    )
    if not candidate_ids:
        return observation

    candidate_count = len(candidate_ids)
    candidate_text = "candidate" if candidate_count == 1 else "candidates"
    preserved_detail = observation.detail.rstrip()
    detail = (f"{preserved_detail} " if preserved_detail else "") + (
        f"All {candidate_count} compatible non-software renderer {candidate_text} "
        "will be evaluated for memory headroom; no single active adapter was guessed."
    )
    return replace(
        observation,
        adapters=tuple(
            replace(adapter, is_active=adapter.adapter_id in candidate_ids)
            for adapter in observation.adapters
        ),
        detail=detail,
    )


class CtypesWindowsGraphicsBudgetProbe:
    """Lazy ctypes implementation of DXGI and ``GlobalMemoryStatusEx`` queries."""

    def __init__(
        self,
        *,
        interop_factory: Callable[[], _DxgiInterop] | None = None,
        system_memory_query: Callable[[], WindowsSystemMemorySnapshot] | None = None,
    ) -> None:
        self._interop_factory = interop_factory or _CtypesDxgiInterop
        self._system_memory_query = system_memory_query or _query_system_memory_with_ctypes

    def query_adapters(self) -> tuple[WindowsAdapterMemorySnapshot, ...]:
        """Enumerate adapters, releasing every acquired COM interface in all paths."""

        interop = self._interop_factory()
        factory: object | None = None
        snapshots: list[WindowsAdapterMemorySnapshot] = []
        try:
            factory = interop.create_factory()
            index = 0
            while True:
                adapter = interop.enum_adapter(factory, index)
                if adapter is None:
                    break
                try:
                    descriptor = interop.get_adapter_description(adapter)
                    adapter3: object | None = None
                    try:
                        adapter3 = interop.query_adapter3(adapter)
                        local = interop.query_video_memory(
                            adapter3,
                            segment_group=_DXGI_MEMORY_SEGMENT_GROUP_LOCAL,
                        )
                        non_local = interop.query_video_memory(
                            adapter3,
                            segment_group=_DXGI_MEMORY_SEGMENT_GROUP_NON_LOCAL,
                        )
                    finally:
                        if adapter3 is not None:
                            interop.release(adapter3)
                    snapshots.append(
                        WindowsAdapterMemorySnapshot(
                            adapter_id=descriptor.adapter_id,
                            description=descriptor.description,
                            dedicated_video_memory_bytes=(descriptor.dedicated_video_memory_bytes),
                            dedicated_system_memory_bytes=(
                                descriptor.dedicated_system_memory_bytes
                            ),
                            shared_system_memory_bytes=descriptor.shared_system_memory_bytes,
                            local_budget_bytes=local.budget_bytes,
                            local_usage_bytes=local.usage_bytes,
                            non_local_budget_bytes=non_local.budget_bytes,
                            non_local_usage_bytes=non_local.usage_bytes,
                            is_software=descriptor.is_software,
                        )
                    )
                finally:
                    interop.release(adapter)
                index += 1
        finally:
            if factory is not None:
                interop.release(factory)
        return tuple(snapshots)

    def query_system_memory(self) -> WindowsSystemMemorySnapshot:
        """Query system RAM without importing a non-standard Windows package."""

        return self._system_memory_query()


@dataclass(frozen=True)
class _AdapterDescription:
    adapter_id: str
    description: str
    dedicated_video_memory_bytes: int
    dedicated_system_memory_bytes: int
    shared_system_memory_bytes: int
    is_software: bool


@dataclass(frozen=True)
class _VideoMemoryInfo:
    budget_bytes: int
    usage_bytes: int


class _DxgiInterop(Protocol):
    def create_factory(self) -> object: ...

    def enum_adapter(self, factory: object, index: int) -> object | None: ...

    def get_adapter_description(self, adapter: object) -> _AdapterDescription: ...

    def query_adapter3(self, adapter: object) -> object: ...

    def query_video_memory(self, adapter3: object, *, segment_group: int) -> _VideoMemoryInfo: ...

    def release(self, interface: object) -> None: ...


class _Guid(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, value: str) -> _Guid:
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)


class _Luid(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class _DxgiAdapterDesc1(ctypes.Structure):
    _fields_ = [
        ("Description", ctypes.c_wchar * 128),
        ("VendorId", ctypes.c_uint32),
        ("DeviceId", ctypes.c_uint32),
        ("SubSysId", ctypes.c_uint32),
        ("Revision", ctypes.c_uint32),
        ("DedicatedVideoMemory", ctypes.c_size_t),
        ("DedicatedSystemMemory", ctypes.c_size_t),
        ("SharedSystemMemory", ctypes.c_size_t),
        ("AdapterLuid", _Luid),
        ("Flags", ctypes.c_uint32),
    ]


class _DxgiQueryVideoMemoryInfo(ctypes.Structure):
    _fields_ = [
        ("Budget", ctypes.c_uint64),
        ("CurrentUsage", ctypes.c_uint64),
        ("AvailableForReservation", ctypes.c_uint64),
        ("CurrentReservation", ctypes.c_uint64),
    ]


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


class _CtypesDxgiInterop:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise WindowsGraphicsBudgetUnsupported(
                "DXGI graphics-memory budgets are available only on Windows."
            )
        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None or getattr(ctypes, "WINFUNCTYPE", None) is None:
            raise WindowsGraphicsBudgetUnsupported("ctypes Windows COM support is unavailable.")
        try:
            self._dxgi = win_dll("dxgi", use_last_error=True)
        except OSError as exc:
            raise WindowsGraphicsBudgetUnsupported("Windows DXGI.dll is unavailable.") from exc
        self._dxgi.CreateDXGIFactory1.argtypes = [
            ctypes.POINTER(_Guid),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._dxgi.CreateDXGIFactory1.restype = ctypes.c_int32

    def create_factory(self) -> object:
        factory = ctypes.c_void_p()
        iid = _Guid.parse(_IID_IDXGI_FACTORY1)
        result = int(self._dxgi.CreateDXGIFactory1(ctypes.byref(iid), ctypes.byref(factory)))
        try:
            _raise_for_hresult(result, operation="CreateDXGIFactory1")
        except Exception:
            if factory.value:
                self.release(factory)
            raise
        if not factory.value:
            raise WindowsGraphicsBudgetQueryError(
                "CreateDXGIFactory1 succeeded without returning an interface."
            )
        return factory

    def enum_adapter(self, factory: object, index: int) -> object | None:
        factory_pointer = _as_com_pointer(factory)
        adapter = ctypes.c_void_p()
        method = _com_method(
            factory_pointer,
            _FACTORY_ENUM_ADAPTERS1_VTABLE_INDEX,
            ctypes.c_int32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        )
        result = int(method(factory_pointer, index, ctypes.byref(adapter)))
        if _unsigned_hresult(result) == _DXGI_ERROR_NOT_FOUND:
            if adapter.value:
                self.release(adapter)
            return None
        try:
            _raise_for_hresult(result, operation=f"IDXGIFactory1::EnumAdapters1({index})")
        except Exception:
            if adapter.value:
                self.release(adapter)
            raise
        if not adapter.value:
            raise WindowsGraphicsBudgetQueryError(
                "EnumAdapters1 succeeded without returning an interface."
            )
        return adapter

    def get_adapter_description(self, adapter: object) -> _AdapterDescription:
        adapter_pointer = _as_com_pointer(adapter)
        descriptor = _DxgiAdapterDesc1()
        method = _com_method(
            adapter_pointer,
            _ADAPTER_GET_DESC1_VTABLE_INDEX,
            ctypes.c_int32,
            ctypes.POINTER(_DxgiAdapterDesc1),
        )
        result = int(method(adapter_pointer, ctypes.byref(descriptor)))
        _raise_for_hresult(result, operation="IDXGIAdapter1::GetDesc1")
        return _AdapterDescription(
            adapter_id=_format_luid(descriptor.AdapterLuid),
            description=str(descriptor.Description).strip() or "Unnamed DXGI adapter",
            dedicated_video_memory_bytes=int(descriptor.DedicatedVideoMemory),
            dedicated_system_memory_bytes=int(descriptor.DedicatedSystemMemory),
            shared_system_memory_bytes=int(descriptor.SharedSystemMemory),
            is_software=bool(int(descriptor.Flags) & _DXGI_ADAPTER_FLAG_SOFTWARE),
        )

    def query_adapter3(self, adapter: object) -> object:
        adapter_pointer = _as_com_pointer(adapter)
        adapter3 = ctypes.c_void_p()
        iid = _Guid.parse(_IID_IDXGI_ADAPTER3)
        method = _com_method(
            adapter_pointer,
            _IUnknown_QUERY_INTERFACE_VTABLE_INDEX,
            ctypes.c_int32,
            ctypes.POINTER(_Guid),
            ctypes.POINTER(ctypes.c_void_p),
        )
        result = int(method(adapter_pointer, ctypes.byref(iid), ctypes.byref(adapter3)))
        if _unsigned_hresult(result) == _E_NOINTERFACE:
            if adapter3.value:
                self.release(adapter3)
            raise WindowsGraphicsBudgetUnsupported(
                "The installed Windows/DXGI version does not expose IDXGIAdapter3."
            )
        try:
            _raise_for_hresult(
                result,
                operation="IDXGIAdapter1::QueryInterface(IDXGIAdapter3)",
            )
        except Exception:
            if adapter3.value:
                self.release(adapter3)
            raise
        if not adapter3.value:
            raise WindowsGraphicsBudgetQueryError(
                "QueryInterface succeeded without returning IDXGIAdapter3."
            )
        return adapter3

    def query_video_memory(self, adapter3: object, *, segment_group: int) -> _VideoMemoryInfo:
        adapter_pointer = _as_com_pointer(adapter3)
        info = _DxgiQueryVideoMemoryInfo()
        method = _com_method(
            adapter_pointer,
            _ADAPTER_QUERY_VIDEO_MEMORY_INFO_VTABLE_INDEX,
            ctypes.c_int32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(_DxgiQueryVideoMemoryInfo),
        )
        result = int(method(adapter_pointer, 0, segment_group, ctypes.byref(info)))
        segment_name = "local" if segment_group == 0 else "non-local"
        _raise_for_hresult(
            result,
            operation=f"IDXGIAdapter3::QueryVideoMemoryInfo({segment_name})",
        )
        return _VideoMemoryInfo(
            budget_bytes=int(info.Budget),
            usage_bytes=int(info.CurrentUsage),
        )

    def release(self, interface: object) -> None:
        pointer = _as_com_pointer(interface)
        method = _com_method(
            pointer,
            _IUnknown_RELEASE_VTABLE_INDEX,
            ctypes.c_uint32,
        )
        method(pointer)


def _query_system_memory_with_ctypes() -> WindowsSystemMemorySnapshot:
    if sys.platform != "win32":
        raise WindowsGraphicsBudgetUnsupported("GlobalMemoryStatusEx is available only on Windows.")
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:
        raise WindowsGraphicsBudgetUnsupported("ctypes Windows DLL support is unavailable.")
    try:
        kernel32 = win_dll("kernel32", use_last_error=True)
    except OSError as exc:
        raise WindowsGraphicsBudgetUnsupported("Windows Kernel32.dll is unavailable.") from exc
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
    kernel32.GlobalMemoryStatusEx.restype = ctypes.c_int
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        error_code = ctypes.get_last_error()
        raise WindowsGraphicsBudgetQueryError(
            f"GlobalMemoryStatusEx failed with Windows error {error_code}."
        )
    return WindowsSystemMemorySnapshot(
        total_bytes=int(status.ullTotalPhys),
        available_bytes=int(status.ullAvailPhys),
    )


def _com_method(
    interface: ctypes.c_void_p,
    index: int,
    result_type: type[ctypes._SimpleCData],
    *argument_types: type[object],
) -> Any:
    win_function_type = getattr(ctypes, "WINFUNCTYPE", None)
    if win_function_type is None:
        raise WindowsGraphicsBudgetUnsupported("ctypes Windows COM support is unavailable.")
    try:
        vtable = ctypes.cast(
            interface,
            ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
        ).contents
        address = vtable[index]
    except (ValueError, TypeError, IndexError) as exc:
        raise WindowsGraphicsBudgetQueryError("A DXGI COM interface was invalid.") from exc
    if not address:
        raise WindowsGraphicsBudgetQueryError("A required DXGI COM method is unavailable.")
    prototype = win_function_type(result_type, ctypes.c_void_p, *argument_types)
    return prototype(address)


def _as_com_pointer(interface: object) -> ctypes.c_void_p:
    if isinstance(interface, ctypes.c_void_p) and interface.value:
        return interface
    raise WindowsGraphicsBudgetQueryError("A DXGI COM interface pointer was invalid.")


def _raise_for_hresult(result: int, *, operation: str) -> None:
    if result == _S_OK:
        return
    raise WindowsGraphicsBudgetQueryError(
        f"{operation} failed with HRESULT 0x{_unsigned_hresult(result):08X}."
    )


def _unsigned_hresult(value: int) -> int:
    return value & 0xFFFFFFFF


def _format_luid(luid: _Luid) -> str:
    return f"{int(luid.HighPart) & 0xFFFFFFFF:08X}:{int(luid.LowPart):08X}"


def _memory_kind(adapter: WindowsAdapterMemorySnapshot) -> AdapterMemoryKind:
    if adapter.dedicated_video_memory_bytes > 0:
        return AdapterMemoryKind.DISCRETE
    if adapter.dedicated_system_memory_bytes > 0 or adapter.shared_system_memory_bytes > 0:
        return AdapterMemoryKind.UMA
    return AdapterMemoryKind.UNKNOWN


def _select_active_adapter(
    adapters: tuple[WindowsAdapterMemorySnapshot, ...],
    *,
    renderer_hint: str | None,
) -> tuple[str | None, str]:
    normalized_hint = _normalize_renderer_identity(renderer_hint)
    if normalized_hint:
        exact_matches = tuple(
            adapter
            for adapter in adapters
            if _normalize_renderer_identity(adapter.description) == normalized_hint
        )
        if len(exact_matches) == 1:
            adapter = exact_matches[0]
            return (
                adapter.adapter_id,
                f"Active DXGI adapter matched the OpenGL renderer: '{adapter.description}'.",
            )
        if len(exact_matches) > 1:
            return (
                None,
                "DXGI telemetry was queried, but the renderer exactly matched multiple "
                "adapters; no active adapter was guessed.",
            )

        compatible_matches = tuple(
            adapter
            for adapter in adapters
            if _renderer_identities_compatible(
                normalized_hint,
                _normalize_renderer_identity(adapter.description),
            )
        )
        if len(compatible_matches) == 1:
            adapter = compatible_matches[0]
            return (
                adapter.adapter_id,
                f"Active DXGI adapter matched the OpenGL renderer: '{adapter.description}'.",
            )
        if len(compatible_matches) > 1:
            return (
                None,
                "DXGI telemetry was queried, but the renderer matched multiple adapters; "
                "no active adapter was guessed.",
            )

    hardware_adapters = tuple(adapter for adapter in adapters if not adapter.is_software)
    if len(hardware_adapters) == 1 and (not normalized_hint or len(adapters) == 1):
        adapter = hardware_adapters[0]
        return (
            adapter.adapter_id,
            f"The only hardware DXGI adapter was selected: '{adapter.description}'.",
        )
    if not hardware_adapters and len(adapters) == 1:
        adapter = adapters[0]
        return (
            adapter.adapter_id,
            f"The only DXGI adapter is software-rendered: '{adapter.description}'.",
        )

    hint_detail = (
        "the renderer hint did not identify one adapter"
        if normalized_hint
        else "no renderer hint was available"
    )
    return (
        None,
        "DXGI telemetry was queried, but "
        f"{hint_detail} among {len(adapters)} candidates; no active adapter was guessed.",
    )


def _normalize_renderer_identity(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    tokens = re.findall(r"[a-z0-9]+", value.casefold())
    return tuple(token for token in tokens if token not in _RENDERER_NOISE_TOKENS)


def _renderer_identities_compatible(
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> bool:
    if not first or not second:
        return False
    first_tokens = set(first)
    second_tokens = set(second)
    return first_tokens.issubset(second_tokens) or second_tokens.issubset(first_tokens)


def _validate_native_snapshots(
    adapters: tuple[WindowsAdapterMemorySnapshot, ...],
    system_memory: WindowsSystemMemorySnapshot,
) -> None:
    adapter_ids: set[str] = set()
    byte_fields = (
        "dedicated_video_memory_bytes",
        "dedicated_system_memory_bytes",
        "shared_system_memory_bytes",
        "local_budget_bytes",
        "local_usage_bytes",
        "non_local_budget_bytes",
        "non_local_usage_bytes",
    )
    for adapter in adapters:
        if not adapter.adapter_id or adapter.adapter_id in adapter_ids:
            raise WindowsGraphicsBudgetQueryError(
                "DXGI returned a missing or duplicate adapter identifier."
            )
        adapter_ids.add(adapter.adapter_id)
        if not adapter.description.strip():
            raise WindowsGraphicsBudgetQueryError("DXGI returned an unnamed adapter.")
        if any(getattr(adapter, name) < 0 for name in byte_fields):
            raise WindowsGraphicsBudgetQueryError("DXGI returned a negative memory value.")
    if system_memory.total_bytes <= 0:
        raise WindowsGraphicsBudgetQueryError("Windows reported no physical memory.")
    if not 0 <= system_memory.available_bytes <= system_memory.total_bytes:
        raise WindowsGraphicsBudgetQueryError("Windows reported invalid available physical memory.")
