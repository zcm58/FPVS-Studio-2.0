"""Execute default-hardware preference flows without importing or constructing Qt."""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from fpvs_studio.core.models import ProjectRecordingSettings

_KEY = "recording/default_configuration"
_BACKENDS = (
    "serial", "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
    "unicorn_udp",
)
_LEGACY_SETTINGS = {"recording/backend": "unicorn_udp", "recording/unicorn_udp_port": 4321}


class _Settings:
    """In-memory QSettings-shaped fake, including failed-write status."""

    def __init__(self, values=None, *, sync_failures=0):
        self.values = dict(values or {})
        self.sync_failures = sync_failures
        self.sync_calls = 0
        self.mutations = []
        self._status = 0

    def value(self, key, default=None, **_kwargs):
        return self.values.get(key, default)

    def setValue(self, key, value):  # noqa: N802
        self.values[key] = value
        self.mutations.append((key, value))

    def remove(self, key):
        self.values.pop(key, None)
        self.mutations.append((key, None))

    def sync(self):
        self.sync_calls += 1
        self._status = int(self.sync_calls <= self.sync_failures)

    def status(self):
        return self._status


def _bind_controller(controller, **namespace):
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/controller.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    key = next(node for node in parsed.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name)
                       and target.id == "_DEFAULT_RECORDING_CONFIGURATION_KEY"
                       for target in node.targets))
    assert ast.literal_eval(key.value) == _KEY
    owner = next(node for node in parsed.body if isinstance(node, ast.ClassDef)
                 and node.name == "StudioController")
    names = {
        "load_default_recording_configuration", "save_default_recording_configuration",
        "ensure_default_recording_configured", "ensure_fpvs_root_configured",
    }
    methods = [node for node in owner.body if isinstance(node, ast.FunctionDef)
               and node.name in names]
    assert {method.name for method in methods} == names
    for method in methods:
        method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    namespace.update({
        "_DEFAULT_RECORDING_CONFIGURATION_KEY": _KEY,
        "ProjectRecordingSettings": ProjectRecordingSettings,
        "QSettings": SimpleNamespace(Status=SimpleNamespace(NoError=0)),
        "_LOGGER": logging.getLogger(__name__),
        "Path": Path,
    })
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    for name in names:
        setattr(controller, name, MethodType(namespace[name], controller))


def _controller(settings=None, *, dialog_factory=None, main_window=True, **namespace):
    controller = SimpleNamespace(
        _settings=settings if settings is not None else _Settings(),
        _app=SimpleNamespace(quit=Mock()),
        main_window=SimpleNamespace(document=Mock()) if main_window else None,
        welcome_window=object(),
    )
    _bind_controller(
        controller,
        DefaultRecordingHardwareDialog=(
            dialog_factory if dialog_factory is not None else Mock(
                side_effect=AssertionError("Hardware picker must not open"),
            )
        ),
        **namespace,
    )
    return controller


def _dialog(backend="serial", *, accepted=True):
    return SimpleNamespace(
        selected_backend=backend,
        DialogCode=SimpleNamespace(Accepted=1),
        exec=Mock(return_value=int(accepted)),
    )


def test_unset_default_does_not_reuse_obsolete_global_preferences():
    settings = _Settings(_LEGACY_SETTINGS)
    controller = _controller(settings)

    assert controller.load_default_recording_configuration() is None
    assert settings.mutations == []
    assert settings.sync_calls == 0


@pytest.mark.parametrize("raw", [
    "", "not JSON", "null", "[]", 42, {},
    '{"recording_backend":"unknown"}',
    '{"recording_backend":"serial","unrecognized":true}',
])
def test_invalid_default_is_explicit_and_is_not_replaced(raw):
    original = {**_LEGACY_SETTINGS, _KEY: raw}
    settings = _Settings(original)
    controller = _controller(settings)

    with pytest.raises(ValueError):
        controller.load_default_recording_configuration()

    assert settings.values == original
    assert settings.mutations == []
    controller.main_window.document.set_default_recording_configuration.assert_not_called()


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("main_window", [False, True])
def test_default_roundtrip_serializes_the_model_and_updates_only_after_success(
    backend, main_window,
):
    settings = _Settings()
    controller = _controller(settings, main_window=main_window)
    configuration = {
        "recording_backend": backend,
        "unicorn_udp_port": 4321,
        "brainproducts_serial_port": " COM18 ",
        "brainproducts_parallel_address": 0xD010,
        "brainproducts_pulse_width_ms": 20,
    }
    expected = ProjectRecordingSettings.model_validate(configuration).model_dump(mode="json")
    if main_window:
        def injected(actual):
            assert settings.sync_calls == 1
            assert settings.status() == 0
            assert json.loads(settings.values[_KEY]) == actual

        controller.main_window.document.set_default_recording_configuration.side_effect = injected

    controller.save_default_recording_configuration(configuration)

    assert isinstance(settings.values[_KEY], str)
    assert json.loads(settings.values[_KEY]) == expected
    assert controller.load_default_recording_configuration() == expected
    assert settings.sync_calls == 1
    if main_window:
        controller.main_window.document.set_default_recording_configuration.assert_called_once_with(
            expected,
        )
        controller.main_window.document.save_recording_configuration.assert_not_called()


@pytest.mark.parametrize("configuration", [
    {"recording_backend": "unknown"},
    {"recording_backend": None},
    {"recording_backend": "unicorn_udp", "unicorn_udp_port": True},
    {"recording_backend": "serial", "unexpected": "value"},
])
def test_invalid_save_keeps_previous_preference_and_live_document(configuration):
    previous = ProjectRecordingSettings(recording_backend="biosemi_active_three").model_dump_json()
    settings = _Settings({_KEY: previous})
    controller = _controller(settings)

    with pytest.raises(ValueError):
        controller.save_default_recording_configuration(configuration)

    assert settings.values == {_KEY: previous}
    assert settings.mutations == []
    assert settings.sync_calls == 0
    controller.main_window.document.set_default_recording_configuration.assert_not_called()


@pytest.mark.parametrize("previous", [
    None, ProjectRecordingSettings(recording_backend="biosemi_active_three").model_dump_json(),
])
def test_failed_save_restores_previous_preference_without_updating_document(previous):
    original = {_KEY: previous} if previous is not None else {}
    settings = _Settings(original, sync_failures=1)
    controller = _controller(settings)

    with pytest.raises(OSError, match="save"):
        controller.save_default_recording_configuration({"recording_backend": "unicorn_udp"})

    assert settings.values == original
    controller.main_window.document.set_default_recording_configuration.assert_not_called()


def test_existing_valid_default_skips_picker_and_writes():
    saved = ProjectRecordingSettings(recording_backend="unicorn_udp").model_dump_json()
    settings = _Settings({_KEY: saved})
    controller = _controller(settings)

    assert controller.ensure_default_recording_configured() is True
    assert settings.mutations == []
    controller._app.quit.assert_not_called()


@pytest.mark.parametrize("backend", _BACKENDS)
def test_first_picker_saves_only_selected_hardware_without_guessing_amplifier(backend):
    factory = Mock(return_value=_dialog(backend))
    controller = _controller(dialog_factory=factory, main_window=False)

    assert controller.ensure_default_recording_configured() is True

    factory.assert_called_once_with(parent=controller.welcome_window, error_message="")
    expected = ProjectRecordingSettings(recording_backend=backend).model_dump(mode="json")
    assert controller.load_default_recording_configuration() == expected
    assert expected["brainproducts_amplifier"] == (
        "actichamp" if backend == "brainproducts_parallel" else None
    )
    assert expected["brainproducts_parallel_address"] is None
    assert expected["brainproducts_sampling_rate_hz"] is None
    controller._app.quit.assert_not_called()


def test_picker_cancel_exits_without_selecting_or_saving_hardware():
    controller = _controller(dialog_factory=Mock(return_value=_dialog(accepted=False)))

    assert controller.ensure_default_recording_configured() is False

    assert controller._settings.values == {}
    assert controller._settings.mutations == []
    controller._app.quit.assert_called_once()
    controller.main_window.document.set_default_recording_configuration.assert_not_called()


def test_corrupt_preference_is_repaired_through_explicit_picker():
    settings = _Settings({_KEY: "corrupt JSON"})
    factory = Mock(return_value=_dialog("biosemi_active_three"))
    controller = _controller(settings, dialog_factory=factory)

    assert controller.ensure_default_recording_configured() is True

    assert factory.call_args.kwargs["parent"] is controller.main_window
    assert factory.call_args.kwargs["error_message"]
    assert controller.load_default_recording_configuration()["recording_backend"] == (
        "biosemi_active_three"
    )


def test_picker_retries_failed_persistence_before_updating_document():
    settings = _Settings(sync_failures=1)
    factory = Mock(side_effect=[_dialog("unicorn_udp"), _dialog("biosemi_active_three")])
    controller = _controller(settings, dialog_factory=factory)

    assert controller.ensure_default_recording_configured() is True

    assert factory.call_count == 2
    assert factory.call_args_list[0].kwargs["error_message"] == ""
    assert factory.call_args_list[1].kwargs["error_message"]
    expected = ProjectRecordingSettings(recording_backend="biosemi_active_three").model_dump(
        mode="json",
    )
    controller.main_window.document.set_default_recording_configuration.assert_called_once_with(
        expected,
    )
    assert controller.load_default_recording_configuration() == expected


@pytest.mark.parametrize("hardware_accepted", [False, True])
def test_valid_root_gates_normal_workflow_on_hardware_choice(tmp_path, hardware_accepted):
    controller = _controller()
    controller.load_fpvs_root_dir = Mock(return_value=tmp_path)
    controller._normalize_fpvs_root_layout = Mock(return_value=True)
    controller.ensure_default_recording_configured = Mock(return_value=hardware_accepted)

    assert controller.ensure_fpvs_root_configured() is hardware_accepted

    controller.ensure_default_recording_configured.assert_called_once_with()


def test_root_selection_finishes_before_hardware_picker(tmp_path):
    events = []
    root_factory = Mock(side_effect=lambda **_kwargs: (
        events.append("root dialog") or _dialog()
    ))
    controller = _controller(RootFolderSetupDialog=root_factory)
    controller.load_fpvs_root_dir = Mock(return_value=None)
    controller._choose_fpvs_root_dir = Mock(side_effect=lambda **_kwargs: (
        events.append("choose root") or tmp_path
    ))
    controller.save_fpvs_root_dir = Mock(side_effect=lambda _path: events.append("save root"))
    controller._normalize_fpvs_root_layout = Mock(side_effect=lambda: (
        events.append("validate root") or True
    ))
    controller.ensure_default_recording_configured = Mock(side_effect=lambda: (
        events.append("hardware picker") or True
    ))

    assert controller.ensure_fpvs_root_configured() is True

    assert events == ["root dialog", "choose root", "save root", "validate root", "hardware picker"]
    controller.save_fpvs_root_dir.assert_called_once_with(tmp_path)


def test_root_cancel_never_opens_hardware_picker():
    controller = _controller(RootFolderSetupDialog=Mock(return_value=_dialog(accepted=False)))
    controller.load_fpvs_root_dir = Mock(return_value=None)
    controller.ensure_default_recording_configured = Mock()

    assert controller.ensure_fpvs_root_configured() is False

    controller.ensure_default_recording_configured.assert_not_called()
    controller._app.quit.assert_called_once()
