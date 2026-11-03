"""Display-link recovery with fake callbacks and no native graphics imports."""

from __future__ import annotations

import ast
from importlib import metadata
from types import SimpleNamespace

import pytest
from tests.platform_adapters import set_module_platform
from tests.unit.test_psychopy_engine import _build_fake_psychopy, _patch_fake_psychopy

from fpvs_studio.engines import psychopy_macos_display as adapter
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine


@pytest.fixture
def mac_clock(monkeypatch):
    set_module_platform(monkeypatch, adapter, "darwin")
    clock = SimpleNamespace(now=10.0)
    monkeypatch.setattr(adapter.time, "monotonic", lambda: clock.now)
    return clock


def _window():
    target = SimpleNamespace(frameLock=None, callback_identity="native target")
    return SimpleNamespace(backend=SimpleNamespace(refreshEventHandlerMacOS=target)), target


def test_callback_clears_original_native_target_and_preserves_delegation(mac_clock):
    window, target = _window()
    adapter.guard_macos_display_link(window)
    guard = window.backend.refreshEventHandlerMacOS
    guard.frameLock = True
    assert target.frameLock is True
    assert guard.callback_identity == "native target"
    mac_clock.now += 0.9
    assert guard.frameLock is True
    target.frameLock = False  # The native display link still invokes the original target.
    mac_clock.now += 2.0
    assert guard.frameLock is False
    adapter.guard_macos_display_link(window)
    assert window.backend.refreshEventHandlerMacOS is guard


def test_missing_callback_fails_closed_and_fresh_window_can_retry(mac_clock):
    window, target = _window()
    adapter.guard_macos_display_link(window)
    guard = window.backend.refreshEventHandlerMacOS
    guard.frameLock = True
    mac_clock.now += adapter.DISPLAY_LINK_TIMEOUT_SECONDS
    with pytest.raises(RuntimeError, match="macOS display refresh callback did not arrive"):
        _ = guard.frameLock
    assert target.frameLock is True  # No fallback claims that a callback occurred.
    retry, retry_target = _window()
    adapter.guard_macos_display_link(retry)
    retry.backend.refreshEventHandlerMacOS.frameLock = True
    retry_target.frameLock = False
    assert retry.backend.refreshEventHandlerMacOS.frameLock is False


def test_each_flip_gets_its_own_deadline(mac_clock):
    window, target = _window()
    adapter.guard_macos_display_link(window)
    guard = window.backend.refreshEventHandlerMacOS
    guard.frameLock = True
    mac_clock.now += 0.9
    target.frameLock = False
    assert guard.frameLock is False
    guard.frameLock = True
    mac_clock.now += 0.9
    assert guard.frameLock is True
    target.frameLock = False
    assert guard.frameLock is False
    guard.frameLock = False
    mac_clock.now += 2.0
    assert guard.frameLock is False


@pytest.mark.parametrize("window", [SimpleNamespace(), SimpleNamespace(backend=object()),
                                    SimpleNamespace(backend=SimpleNamespace(
                                        refreshEventHandlerMacOS=object()))])
def test_missing_display_link_fails_before_presentation(mac_clock, window):
    with pytest.raises(RuntimeError, match="callback support is unavailable"):
        adapter.guard_macos_display_link(window)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_leave_backend_untouched(monkeypatch, platform):
    set_module_platform(monkeypatch, adapter, platform)
    window, target = _window()
    adapter.guard_macos_display_link(window)
    assert window.backend.refreshEventHandlerMacOS is target
    adapter.guard_macos_display_link(object())


def test_mac_test_keyboard_requests_foreground_backend_explicitly():
    calls = []
    keyboard = SimpleNamespace(getBackend=lambda: "event")

    def create(**kwargs):
        calls.append(kwargs)
        return keyboard

    result = adapter.create_macos_test_keyboard(SimpleNamespace(Keyboard=create))
    assert result is keyboard
    assert calls == [{"backend": "event"}]


@pytest.mark.parametrize("backend", ["ptb", "iohub", None])
def test_mac_test_keyboard_rejects_unrequested_backend(backend):
    keyboard = SimpleNamespace(getBackend=lambda: backend)
    module = SimpleNamespace(Keyboard=lambda **_: keyboard)
    with pytest.raises(RuntimeError, match="foreground-window keyboard backend"):
        adapter.create_macos_test_keyboard(module)


@pytest.mark.parametrize("operation", ["probe", "session"])
def test_engine_closes_mac_window_when_callback_support_is_missing(monkeypatch, operation):
    captures = {}
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])
    create_window = fake.visual.Window

    def missing_callback(**kwargs):
        window = create_window(**kwargs)
        del window.backend.refreshEventHandlerMacOS
        return window

    fake.visual.Window = missing_callback
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    with pytest.raises(RuntimeError, match="callback support is unavailable"):
        if operation == "probe":
            engine.measure_refresh_hz()
        else:
            engine.open_session(runtime_options={"fullscreen": True})
    assert captures["window"].closed
    assert engine._window is None
    assert engine._graphics_lifetime is None


@pytest.mark.parametrize("failure", ["constructor", "unexpected_backend"])
def test_mac_keyboard_failure_precedes_native_window_creation(monkeypatch, failure):
    captures = {}
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])

    def unavailable_keyboard(**kwargs):
        assert kwargs == {"backend": "event"}
        assert "window" not in captures
        if failure == "constructor":
            raise RuntimeError("foreground input failed")
        return SimpleNamespace(getBackend=lambda: "ptb")

    fake.hardware.keyboard.Keyboard = unavailable_keyboard
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    expected = "foreground input failed" if failure == "constructor" else "foreground-window"
    with pytest.raises(RuntimeError, match=expected):
        engine.open_session(runtime_options={"fullscreen": True})
    assert "window" not in captures
    assert engine._window is None
    assert engine._keyboard is None


def test_engine_closes_probe_after_native_callback_timeout(monkeypatch, mac_clock):
    captures = {}
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])
    create_window = fake.visual.Window

    def stalled_callback(**kwargs):
        window = create_window(**kwargs)

        def measure(**_):
            handler = window.backend.refreshEventHandlerMacOS
            handler.frameLock = True
            while handler.frameLock:
                mac_clock.now += 0.25

        window.getActualFrameRate = measure
        return window

    fake.visual.Window = stalled_callback
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    with pytest.raises(RuntimeError, match="macOS display refresh callback did not arrive"):
        engine.measure_refresh_hz()
    assert captures["window"].closed


@pytest.mark.parametrize("callback_arrives", [False, True])
def test_installed_psychopy_swap_loop_recovers_without_importing_graphics(
    mac_clock, callback_arrives,
):
    """Execute the dependency's real swap loop with fake GL/window/callback owners."""
    try:
        distribution = metadata.distribution("psychopy")
    except metadata.PackageNotFoundError:
        pytest.skip("Optional PsychoPy engine is not installed")
    source = distribution.locate_file("psychopy/visual/backends/pygletbackend.py")
    module = ast.parse(source.read_text(encoding="utf-8"))
    backend_class = next(node for node in module.body
                         if isinstance(node, ast.ClassDef) and node.name == "PygletBackend")
    swap = next(node for node in backend_class.body
                if isinstance(node, ast.FunctionDef) and node.name == "swapBuffers")
    assert any(isinstance(node, ast.Attribute) and node.attr == "frameLock"
               for node in ast.walk(swap)), "Re-evaluate the adapter after upstream changes"
    window, target = _window()
    backend = window.backend
    backend.win = SimpleNamespace(_eventDispatchers=[])
    calls = SimpleNamespace(flips=0, dispatches=0)

    def dispatch():
        calls.dispatches += 1
        mac_clock.now += 0.25
        if callback_arrives and calls.dispatches >= 2:
            target.frameLock = False
        assert calls.dispatches < 10, "The native polling loop did not honor its deadline"

    def flip():
        calls.flips += 1

    backend.winHandle = SimpleNamespace(dispatch_events=dispatch, flip=flip)
    namespace = {"globalVars": SimpleNamespace(currWindow=backend), "USE_LEGACY_GL": False,
                 "pyglet": SimpleNamespace(version="2.0")}
    exec(compile(ast.Module(body=[swap], type_ignores=[]), str(source), "exec"), namespace)
    adapter.guard_macos_display_link(window)
    if callback_arrives:
        namespace["swapBuffers"](backend)
        assert target.frameLock is False
    else:
        with pytest.raises(RuntimeError, match="macOS display refresh callback did not arrive"):
            namespace["swapBuffers"](backend)
    assert calls.flips == 1
