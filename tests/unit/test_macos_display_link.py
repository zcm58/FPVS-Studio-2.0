"""Display-link recovery with fake callbacks and no native graphics imports."""

from __future__ import annotations

import ast
import builtins
from importlib import metadata
from types import SimpleNamespace

import numpy as np
import pytest
from tests.platform_adapters import set_module_platform
from tests.unit.test_psychopy_engine import _build_fake_psychopy, _patch_fake_psychopy

from fpvs_studio.engines import psychopy_engine as engine_module
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


def _keyboard_device():
    return SimpleNamespace(dispatchMessages=lambda: None, parseMessage=lambda name: name,
                           receiveMessage=lambda response: None)


def _presentation_app(monkeypatch, events, *, failure=None):
    previous = 0x1234
    app = SimpleNamespace(options=previous)

    def set_options(value):
        events.append(("presentation_options", value))
        app.options = value
        if failure == "options" and value == 10:
            raise RuntimeError("presentation options failed")

    def activate(value):
        events.append(("activate", value))
        if failure == "activation":
            raise RuntimeError("presentation activation failed")

    app.presentationOptions = lambda: app.options
    app.setPresentationOptions_ = set_options
    app.activateIgnoringOtherApps_ = activate
    appkit = SimpleNamespace(
        NSApplication=SimpleNamespace(sharedApplication=lambda: app),
        NSApplicationPresentationHideDock=2,
        NSApplicationPresentationHideMenuBar=8,
        NSApplicationPresentationDisableProcessSwitching=32,
        NSApplicationPresentationDisableForceQuit=64,
    )

    def load(name):
        assert name == "AppKit"
        return appkit

    monkeypatch.setattr(adapter, "import_module", load)
    return app, previous


def test_mac_presentation_hides_only_chrome_and_restores_all_previous_bits(monkeypatch, mac_clock):
    events = []
    app, previous = _presentation_app(monkeypatch, events)
    activate, restore = adapter.prepare_macos_fullscreen_presentation()
    assert app.options == previous
    assert events == []
    activate()
    assert app.options == 10
    assert events == [("presentation_options", 10), ("activate", True)]
    assert callable(restore)
    restore()
    restore()
    assert app.options == previous
    assert events == [("presentation_options", 10), ("activate", True),
                      ("presentation_options", previous)]


@pytest.mark.parametrize("failure", ["options", "activation"])
def test_mac_presentation_setup_failure_restores_previous_options(monkeypatch, mac_clock, failure):
    events = []
    app, previous = _presentation_app(monkeypatch, events, failure=failure)
    activate, restore = adapter.prepare_macos_fullscreen_presentation()
    assert events == []
    with pytest.raises(RuntimeError, match="presentation"):
        activate()
    # A native window must close before its caller restores these captured options.
    assert app.options == 10
    restore()
    assert app.options == previous
    assert events[0] == ("presentation_options", 10)
    assert events[-1] == ("presentation_options", previous)


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platforms_never_import_mac_presentation_apis(monkeypatch, platform):
    set_module_platform(monkeypatch, adapter, platform)
    monkeypatch.setattr(adapter, "import_module", lambda _: pytest.fail("Unexpected AppKit import"))
    assert adapter.prepare_macos_fullscreen_presentation() is None


@pytest.mark.parametrize("operation", ["probe", "session"])
@pytest.mark.parametrize("failure", [None, "guard", "gpu", "close",
                                    "presentation_options", "presentation_activation"])
def test_engine_restores_mac_presentation_after_native_window_cleanup(
    monkeypatch, operation, failure,
):
    captures = {}
    events = []
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[], key_batches=[["space"]])
    create_window = fake.visual.Window
    create_text = fake.visual.TextStim
    checked = []

    def verify_pixel_mode(window):
        assert window.useRetina is False
        assert window.size is captures["backing"]
        assert window.frameBufferSize is captures["backing"]
        checked.append(True)

    def make_window(**kwargs):
        window = create_window(**kwargs)
        captures["backing"] = np.array((2880, 1800))
        window.size = window.frameBufferSize = captures["backing"]
        close = window.close

        def close_window():
            events.append(("window_close", None))
            close()
            app.options = 0  # CocoaWindow.close calls set_exclusive_keyboard(False).
            if failure == "close":
                raise RuntimeError("window close failed")

        def measure(**_):
            verify_pixel_mode(window)
            return 60.0

        window.close = close_window
        window.getActualFrameRate = measure
        if failure == "guard":
            del window.backend.refreshEventHandlerMacOS
        return window

    def text(window, **kwargs):
        verify_pixel_mode(window)
        return create_text(window, **kwargs)

    fake.visual.Window = make_window
    fake.visual.TextStim = text
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    presentation_failure = (
        failure.removeprefix("presentation_")
        if failure is not None and failure.startswith("presentation_") else None
    )
    app, previous = _presentation_app(monkeypatch, events, failure=presentation_failure)
    if failure == "gpu":
        class FailingLifetime:
            def __init__(self, _window):
                pass

            def assert_owner(self):
                pass

            def activate(self):
                raise RuntimeError("GPU cleanup failed")

            def retire(self):
                events.append(("retire", None))

        monkeypatch.setattr(engine_module, "GraphicsLifetime", FailingLifetime)

    def execute():
        if operation == "probe":
            assert engine.measure_refresh_hz() == 60.0
        else:
            engine.open_session(runtime_options={"fullscreen": True})
            if failure is None:
                assert engine.show_transition_screen(
                    heading="Participant instructions", body="Read this text before continuing.",
                    countdown_seconds=None, continue_key="space",
                ) is False
            engine.close_session()

    if failure is None:
        execute()
        assert checked
    else:
        expected = {"guard": "callback support", "gpu": "GPU cleanup", "close": "window close",
                    "presentation_options": "presentation options",
                    "presentation_activation": "presentation activation"}
        with pytest.raises(RuntimeError, match=expected[failure]):
            execute()
    assert captures["window"].closed
    assert app.options == previous
    if failure == "guard":
        assert events == [("window_close", None), ("presentation_options", previous)]
    assert events[-2:] == [("window_close", None), ("presentation_options", previous)]


def test_engine_restores_mac_presentation_after_keyboard_clear_failure(monkeypatch):
    captures = {}
    events = []
    engine = PsychoPyEngine()
    fake = _build_fake_psychopy(captures, flip_times=[])

    def clear_events():
        assert captures["window"].useRetina is False
        raise RuntimeError("foreground keyboard clear failed")

    fake.hardware.keyboard.Keyboard = lambda **_: SimpleNamespace(
        getBackend=lambda: "event", clearEvents=clear_events, device=_keyboard_device(),
    )
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="darwin")
    app, previous = _presentation_app(monkeypatch, events)
    with pytest.raises(RuntimeError, match="foreground keyboard clear failed"):
        engine.open_session(runtime_options={"fullscreen": True})
    assert captures["window"].closed
    assert engine._window is None
    assert engine._keyboard is None
    assert app.options == previous
    assert events[-1] == ("presentation_options", previous)


@pytest.mark.parametrize("retina", [False, True])
def test_mac_pixel_coordinates_preserve_realized_backing_surface(mac_clock, retina):
    dimensions = (2880, 1800) if retina else (1440, 900)
    backend = object()
    backing = np.asarray(dimensions)
    size = np.asarray(dimensions)
    client = np.asarray((1440, 900))
    viewport = (0, 0, *dimensions)
    scale = 2.0 if retina else 1.0
    window = SimpleNamespace(backend=backend, frameBufferSize=backing, size=size,
                             clientSize=client, viewport=viewport, useRetina=retina,
                             getContentScaleFactor=lambda: scale)
    adapter.use_macos_framebuffer_pixels(window)
    adapter.use_macos_framebuffer_pixels(window)
    assert window.useRetina is False
    assert window.backend is backend
    assert window.frameBufferSize is backing
    assert window.size is size
    assert window.clientSize is client
    assert window.viewport is viewport
    assert window.getContentScaleFactor() == scale


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_other_platform_pixel_coordinates_stay_unchanged(monkeypatch, platform):
    set_module_platform(monkeypatch, adapter, platform)
    window = SimpleNamespace(useRetina=True)
    adapter.use_macos_framebuffer_pixels(window)
    assert window.useRetina is True
    adapter.use_macos_framebuffer_pixels(object())


@pytest.mark.parametrize("backing, size", [
    (None, (2880, 1800)), ((0, 1800), (0, 1800)), ((2880, -1), (2880, -1)),
    ((2880,), (2880,)), ((2880, 1800), (1440, 900)),
    ((2880.0, 1800), (2880.0, 1800)), ((True, 1800), (True, 1800)),
])
def test_mac_pixel_mode_rejects_unknown_or_inconsistent_backing(mac_clock, backing, size):
    window = SimpleNamespace(frameBufferSize=backing, size=size, useRetina=True)
    with pytest.raises(RuntimeError, match="could not confirm the Mac display's backing pixels"):
        adapter.use_macos_framebuffer_pixels(window)
    assert window.useRetina is True


def test_mac_pixel_mode_requires_realized_window(mac_clock):
    with pytest.raises(RuntimeError, match="could not confirm the Mac display's backing pixels"):
        adapter.use_macos_framebuffer_pixels(object())


def test_installed_psychopy_units_map_to_framebuffer_pixels(mac_clock):
    """Exercise upstream pixel and normalized conversions without importing graphics."""
    try:
        distribution = metadata.distribution("psychopy")
    except metadata.PackageNotFoundError:
        pytest.skip("Optional PsychoPy engine is not installed")
    window_source = distribution.locate_file("psychopy/visual/window.py")
    module = ast.parse(window_source.read_text(encoding="utf-8"))
    window_class = next(node for node in module.body
                        if isinstance(node, ast.ClassDef) and node.name == "Window")
    set_scale = next(node for node in window_class.body
                     if isinstance(node, ast.FunctionDef) and node.name == "setScale")
    unit_source = distribution.locate_file("psychopy/tools/monitorunittools.py")
    unit_module = ast.parse(unit_source.read_text(encoding="utf-8"))
    conversions = [node for node in unit_module.body if isinstance(node, ast.FunctionDef)
                   and node.name in {"_pix2pix", "_norm2pix", "_height2pix"}]
    scales = []
    namespace = {"numpy": np, "array": np.array, "GL": SimpleNamespace(
        glScalef=lambda x, y, z: scales.append(np.array((x, y))))}
    exec(compile(ast.Module(body=[set_scale, *conversions], type_ignores=[]),
                 str(window_source), "exec"), namespace)
    window = SimpleNamespace(size=np.array((2880, 1800)),
                             frameBufferSize=np.array((2880, 1800)),
                             useRetina=True, USE_LEGACY_GL=True)
    upstream_scale = namespace["setScale"](window, "pix")
    assert upstream_scale == pytest.approx(np.array((4 / 2880, 4 / 1800)))
    adapter.use_macos_framebuffer_pixels(window)
    pixel_scale = namespace["setScale"](window, "pix")
    assert scales[-1] == pytest.approx(np.array((2 / 2880, 2 / 1800)))
    # Normalized device coordinates map to half the framebuffer on either axis.
    physical_scale = pixel_scale * window.frameBufferSize / 2.0
    assert physical_scale == pytest.approx((1.0, 1.0))
    rect_size = namespace["_pix2pix"](np.array((350, 160)), np.zeros(2), window)
    assert rect_size * physical_scale == pytest.approx((350, 160))
    rect_position = namespace["_pix2pix"](np.zeros(2), np.array((-600, -200)), window)
    assert rect_position * physical_scale == pytest.approx((-600, -200))
    norm = namespace["_norm2pix"](np.array((1, 1)), np.zeros(2), window)
    assert norm * physical_scale == pytest.approx((1440, 900))
    height = namespace["_height2pix"](np.array((0.5, 0.5)), np.zeros(2), window)
    assert height * physical_scale == pytest.approx((900, 900))


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
    keyboard = SimpleNamespace(getBackend=lambda: "event", device=_keyboard_device())

    def create(**kwargs):
        calls.append(kwargs)
        return keyboard

    result = adapter.create_macos_test_keyboard(SimpleNamespace(
        Keyboard=create, event=SimpleNamespace(getKeys=lambda **_: []),
    ))
    assert result is keyboard
    assert calls == [{"backend": "event"}]


def test_windows_session_preserves_default_keyboard_and_dispatcher(monkeypatch):
    captures = {}
    fake = _build_fake_psychopy(captures, flip_times=[])
    create = fake.hardware.keyboard.Keyboard
    dispatchers = []

    def create_keyboard(**kwargs):
        keyboard = create(**kwargs)
        dispatchers.append(keyboard.device.dispatchMessages)
        return keyboard

    def reject_mac_adapter(_module):
        pytest.fail("Windows must not use the Mac keyboard adapter")

    fake.hardware.keyboard.Keyboard = create_keyboard
    engine = PsychoPyEngine()
    _patch_fake_psychopy(monkeypatch, engine, fake, platform_name="win32")
    monkeypatch.setattr(engine_module, "create_macos_test_keyboard", reject_mac_adapter)
    try:
        engine.open_session(runtime_options={"fullscreen": False})
        assert captures["keyboard_kwargs"] == {}
        assert engine._keyboard.getBackend() == "ptb"
        assert engine._keyboard.device.dispatchMessages is dispatchers[0]
    finally:
        engine.close_session()


@pytest.mark.parametrize("backend", ["ptb", "iohub", None])
def test_mac_test_keyboard_rejects_unrequested_backend(backend):
    keyboard = SimpleNamespace(getBackend=lambda: backend)
    module = SimpleNamespace(Keyboard=lambda **_: keyboard)
    with pytest.raises(RuntimeError, match="foreground-window keyboard backend"):
        adapter.create_macos_test_keyboard(module)


@pytest.mark.parametrize("missing", ["device", "event_reader", "dispatcher", "parser", "receiver"])
def test_mac_keyboard_rejects_unsupported_event_interface(missing):
    device = _keyboard_device()
    keyboard = SimpleNamespace(getBackend=lambda: "event", device=device)
    event = SimpleNamespace(getKeys=lambda **_: [])
    if missing == "device":
        del keyboard.device
    elif missing == "event_reader":
        del event.getKeys
    else:
        method = {"dispatcher": "dispatchMessages", "parser": "parseMessage",
                  "receiver": "receiveMessage"}[missing]
        setattr(device, method, None)
    module = SimpleNamespace(Keyboard=lambda **_: keyboard, event=event)
    with pytest.raises(RuntimeError, match="foreground-window keyboard event interface"):
        adapter.create_macos_test_keyboard(module)


@pytest.fixture
def upstream_event_keyboard():
    """Use the dependency's keyboard/response methods with fake native input only."""
    try:
        distribution = metadata.distribution("psychopy")
    except metadata.PackageNotFoundError:
        pytest.skip("Optional PsychoPy engine is not installed")
    keyboard_source = distribution.locate_file("psychopy/hardware/keyboard.py")
    keyboard_ast = ast.parse(keyboard_source.read_text(encoding="utf-8"))
    base_source = distribution.locate_file("psychopy/hardware/base.py")
    base_ast = ast.parse(base_source.read_text(encoding="utf-8"))
    classes = {node.name: node for node in [*keyboard_ast.body, *base_ast.body]
               if isinstance(node, ast.ClassDef)}
    base_response = classes["BaseResponse"]
    base_response.body = [node for node in base_response.body
                          if isinstance(node, ast.FunctionDef) and node.name == "__init__"]
    response = classes["KeyPress"]
    keyboard_methods = [node for node in classes["KeyboardDevice"].body
                        if isinstance(node, ast.FunctionDef) and node.name in {
                            "dispatchMessages", "parseMessage", "getKeys", "getBackend",
                            "clearEvents",
                        }]
    receive = next(node for node in classes["BaseResponseDevice"].body
                   if isinstance(node, ast.FunctionDef) and node.name == "receiveMessage")
    state = SimpleNamespace(pending=[], focus=True, now=0.25, reads=[], clears=[])

    def read_events(*, modifiers, timeStamped):
        state.reads.append((modifiers, timeStamped))
        pending, state.pending = state.pending, []
        return pending if timeStamped else [entry[0] for entry in pending]

    def clear_events(event_type):
        state.clears.append(event_type)
        state.pending.clear()

    event = SimpleNamespace(getKeys=read_events, clearEvents=clear_events)
    device_class = type("SourceKeyboardDevice", (), {"_backend": "event"})
    systemtools = SimpleNamespace(isRegisteredApp=lambda: state.focus)

    def source_import(name, globals=None, locals=None, fromlist=(), level=0):
        assert name == "psychopy.tools.systemtools", f"Unexpected graphics import: {name}"
        return systemtools

    namespace = {
        "__builtins__": {**vars(builtins), "__import__": source_import},
        "KeyboardDevice": device_class,
        "event": event,
        "logging": SimpleNamespace(exp=lambda *_: None, error=lambda *_: None,
                                   info=lambda *_args, **_kwargs: None),
    }
    exec(compile(ast.Module(body=[base_response, response, *keyboard_methods, receive],
                            type_ignores=[]), str(keyboard_source), "exec"), namespace)
    for method in [*keyboard_methods, receive]:
        setattr(device_class, method.name, namespace[method.name])
    device_class.responseClass = namespace["KeyPress"]

    def create():
        device = device_class()
        device.clock = SimpleNamespace(getTime=lambda: state.now)
        device.responses, device.listeners = [], []
        device.muteOutsidePsychopy = True
        device.checkCallbacks = lambda _: None
        keyboard = SimpleNamespace(device=device, getBackend=device.getBackend,
                                   getKeys=device.getKeys, clearEvents=device.clearEvents,
                                   clock=device.clock)
        module = SimpleNamespace(Keyboard=lambda **_: keyboard, event=event)
        return keyboard, module

    return SimpleNamespace(state=state, create=create, device_class=device_class)


def test_upstream_event_dispatcher_mislabels_timestamped_keys_and_drops_batch(
    upstream_event_keyboard,
):
    if metadata.version("psychopy") != "2026.2.5":
        pytest.skip("Bug reproduction targets PsychoPy 2026.2.5; adapter tests are separate")
    source = upstream_event_keyboard
    keyboard, _module = source.create()
    source.state.pending = [["space", 10.0], ["escape", 10.1]]
    assert keyboard.getKeys(keyList=["space", "escape"], waitRelease=False, clear=True) == []
    assert [key.name for key in keyboard.device.responses] == [["space", 10.0]]
    assert source.state.pending == []
    assert source.state.reads == [(False, True)]


def test_mac_dispatcher_preserves_all_key_names_filtering_and_instance_scope(
    upstream_event_keyboard,
):
    source = upstream_event_keyboard
    keyboard, module = source.create()
    untouched, _ = source.create()
    original_dispatch = source.device_class.dispatchMessages
    original_parse, original_receive = keyboard.device.parseMessage, keyboard.device.receiveMessage
    result = adapter.create_macos_test_keyboard(module)
    source.state.pending = [["space", 10.0], ["escape", 10.1], ["f", 10.2]]
    keys = result.getKeys(keyList=["space", "escape"], waitRelease=False, clear=True)
    assert [key.name for key in keys] == ["space", "escape"]
    assert all(isinstance(key.name, str) and key.rt == source.state.now for key in keys)
    assert [key.name for key in result.getKeys(keyList=["f"], waitRelease=False)] == ["f"]
    assert result.device.responses == []
    assert source.state.reads == [(False, False), (False, False)]
    assert source.device_class.dispatchMessages is original_dispatch
    assert untouched.device.dispatchMessages.__func__ is original_dispatch
    assert keyboard.device.parseMessage == original_parse
    assert keyboard.device.receiveMessage == original_receive
    assert keyboard.device.muteOutsidePsychopy is True


def test_mac_dispatcher_keeps_ignore_clear_and_foreground_muting(upstream_event_keyboard):
    source = upstream_event_keyboard
    keyboard, module = source.create()
    adapter.create_macos_test_keyboard(module)
    source.state.pending = [["escape", 10.0], ["f", 10.1]]
    keys = keyboard.getKeys(ignoreKeys=["escape"], waitRelease=False, clear=False)
    assert [key.name for key in keys] == ["f"]
    assert [key.name for key in keyboard.getKeys(keyList=["f"], waitRelease=False)] == ["f"]
    assert [key.name for key in keyboard.device.responses] == ["escape"]
    source.state.pending = [["space", 10.2]]
    keyboard.clearEvents()
    assert keyboard.device.responses == []
    assert source.state.pending == []
    assert source.state.clears == [None]
    source.state.focus = False
    source.state.pending = [["space", 10.3], ["escape", 10.4]]
    assert keyboard.getKeys(waitRelease=False) == []
    assert keyboard.device.muteOutsidePsychopy is True
    source.state.focus = True
    source.state.pending = [["escape", 10.5]]
    assert [key.name for key in keyboard.getKeys(waitRelease=False)] == ["escape"]


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
