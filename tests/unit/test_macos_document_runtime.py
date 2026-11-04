"""Mac local calibration and launch policy without Qt, a process, or hardware."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.gui import document_runtime
from fpvs_studio.gui.document_runtime import DocumentRuntimeMixin
from fpvs_studio.gui.document_support import DocumentError


class Document(DocumentRuntimeMixin):
    def __init__(self, project, root, *, test=True):
        self._project = project
        self._project_root = root
        self.experiment_test_mode_enabled = test
        self.attentional_blink_pilot_mode_enabled = False
        self.local_testing_enabled = test
        self.recording_configuration = {
            "recording_backend": "unicorn_udp", "unicorn_udp_port": 1234,
        }
        self.uses_default_recording_configuration = False
        self._session_export_mode = "full"
        self._last_session_plan = None
        self.session_plan_changed = Mock()
        self.ensure_unused_session_seed_for_launch = Mock(return_value=1)
        self.refresh_participant_summary_if_stale = Mock()


def test_local_calibration_compiles_a_copy_and_preserves_lab_values(
    monkeypatch, sample_project, sample_project_root,
):
    set_module_platform(monkeypatch, document_runtime, "darwin")
    document = Document(sample_project, sample_project_root)
    before = sample_project.model_dump(mode="json")
    local = sample_project.settings.display.model_copy(deep=True)
    local.screen_width_px = 2880
    local.screen_height_px = 1800
    local.screen_width_cm = 33.0
    local.viewing_distance_cm = 55
    local.preferred_refresh_hz = 120
    actual = document.compile_session(refresh_hz=120, local_display=local)
    expected_project = sample_project.model_copy(deep=True)
    expected_project.settings.display = local
    expected = compile_session_plan(
        expected_project, refresh_hz=120, project_root=sample_project_root,
    )
    assert actual == expected
    assert sample_project.model_dump(mode="json") == before
    assert actual.ordered_entries()[0].run_spec.display.screen_width_px == 2880
    assert document.recording_configuration["recording_backend"] == "unicorn_udp"


def test_same_target_local_copy_preserves_seeded_schedules(
    sample_project, sample_project_root,
):
    document = Document(sample_project, sample_project_root)
    regular = document.compile_session(refresh_hz=60)
    local = document.compile_session(
        refresh_hz=60, local_display=sample_project.settings.display,
    )
    assert regular == local


def test_mac_production_launch_is_blocked_before_backend_resolution(
    monkeypatch, sample_project, sample_project_root,
):
    set_module_platform(monkeypatch, document_runtime, "darwin")
    resolver = Mock(side_effect=AssertionError("Must not inspect acquisition"))
    monkeypatch.setattr(document_runtime, "validate_recording_configuration", resolver)
    document = Document(sample_project, sample_project_root, test=False)
    with pytest.raises(DocumentError, match="Enable Experiment Test Mode"):
        document.validate_recording_launch()
    resolver.assert_not_called()


def test_mac_test_uses_null_options_and_preserves_selected_hardware(
    monkeypatch, sample_project, sample_project_root,
):
    set_module_platform(monkeypatch, document_runtime, "darwin")
    document = Document(sample_project, sample_project_root)
    assert document.validate_recording_launch() == "null"
    assert document.recording_launch_options()["serial_enabled"] is False
    assert document.recording_configuration == {
        "recording_backend": "unicorn_udp", "unicorn_udp_port": 1234,
    }


def test_mac_local_launch_uses_process_and_keeps_refresh_verification(
    monkeypatch, sample_project, sample_project_root,
):
    from fpvs_studio.runtime import macos_session_process

    document = Document(sample_project, sample_project_root)
    plan = document.compile_session(refresh_hz=60)
    set_module_platform(monkeypatch, document_runtime, "darwin")
    monkeypatch.setattr(document_runtime, "_sharing_protocol", lambda *_: None)
    monkeypatch.setattr(document_runtime, "_toolbox_handoff_config", lambda *_: {})
    direct = Mock(side_effect=AssertionError("Must not render on GUI worker"))
    monkeypatch.setattr(document_runtime, "_document_dependency", lambda _: direct)
    process = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(macos_session_process, "launch_macos_test_session", process)
    document.launch_compiled_session(plan, participant_number="0", display_index=None)
    settings = process.call_args.kwargs["launch_settings"]
    assert settings.verify_refresh_rate is True
    assert settings.serial_enabled is False
    assert settings.experiment_test_mode is True
    assert settings.recording_backend == "unicorn_udp"
    direct.assert_not_called()


def test_production_cannot_use_preview_local_calibration(sample_project, sample_project_root):
    document = Document(sample_project, sample_project_root, test=False)
    with pytest.raises(DocumentError, match="requires Test or Pilot"):
        document.compile_session(refresh_hz=60, local_display=sample_project.settings.display)


@pytest.mark.parametrize("platform_name", ["darwin", "win32", "linux"])
@pytest.mark.parametrize("mode", ["test", "pilot", "production"])
@pytest.mark.parametrize("structural_error", [False, True])
def test_local_display_readiness_defers_only_refresh_dependent_errors(
    monkeypatch, sample_project, sample_project_root, platform_name, mode, structural_error,
):
    set_module_platform(monkeypatch, document_runtime, platform_name)
    sample_project.settings.protocol.base_hz = 12
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50
    if structural_error:
        sample_project.stimulus_sets[1].source_dir = sample_project.stimulus_sets[0].source_dir
    before = sample_project.model_dump(mode="json")
    document = Document(sample_project, sample_project_root, test=mode == "test")
    document.attentional_blink_pilot_mode_enabled = mode == "pilot"
    document.local_testing_enabled = mode != "production"
    assert not document.validation_report(refresh_hz=60).is_valid
    assert document.local_display_can_resolve_validation() is (
        platform_name == "darwin" and mode != "production" and not structural_error
    )
    assert sample_project.model_dump(mode="json") == before
    document.ensure_unused_session_seed_for_launch.assert_not_called()
    document.session_plan_changed.emit.assert_not_called()
    if structural_error:
        with pytest.raises(DocumentError, match="same folder"):
            document.compile_session(refresh_hz=120)


@pytest.mark.parametrize("base_hz, resolvable", [(9, True), (7, False)])
def test_local_display_readiness_requires_a_rate_without_timing_warnings(
    monkeypatch, sample_project, sample_project_root, base_hz, resolvable,
):
    set_module_platform(monkeypatch, document_runtime, "darwin")
    sample_project.settings.protocol.base_hz = base_hz
    document = Document(sample_project, sample_project_root)
    assert document.validation_report(refresh_hz=60).is_valid
    assert document.local_display_can_resolve_validation() is resolvable


def test_local_readiness_still_requires_confirmed_refresh_to_compile(
    monkeypatch, sample_project, sample_project_root,
):
    set_module_platform(monkeypatch, document_runtime, "darwin")
    sample_project.settings.protocol.base_hz = 12
    sample_project.conditions[0].duty_cycle_mode = DutyCycleMode.BLANK_50
    document = Document(sample_project, sample_project_root)
    assert document.local_display_can_resolve_validation()
    local = sample_project.settings.display.model_copy(deep=True)
    with pytest.raises(DocumentError):
        document.compile_session(refresh_hz=60, local_display=local)
    plan = document.compile_session(refresh_hz=120, local_display=local)
    assert plan == compile_session_plan(
        sample_project, refresh_hz=120, project_root=sample_project_root,
    )
