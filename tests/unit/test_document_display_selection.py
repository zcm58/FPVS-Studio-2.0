"""Transient monitor identity crosses the document boundary without project edits."""

from unittest.mock import Mock

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.gui import document_runtime
from fpvs_studio.gui.document_runtime import DocumentRuntimeMixin
from fpvs_studio.runtime import macos_session_process


class _Document(DocumentRuntimeMixin):
    def __init__(self, project, root):
        self._project = project
        self._project_root = root
        self._last_session_plan = None
        self._session_export_mode = "full"
        self.experiment_test_mode_enabled = True
        self.attentional_blink_pilot_mode_enabled = False
        self.local_testing_enabled = True
        self.recording_configuration = {"recording_backend": "serial"}
        self.uses_default_recording_configuration = True
        self.validate_recording_launch = Mock(return_value="null")
        self.refresh_participant_summary_if_stale = Mock()


@pytest.mark.parametrize("compile_first", [False, True])
@pytest.mark.parametrize("platform_name", ["win32", "darwin"])
def test_document_passes_selected_device_to_launch_without_persisting_it(
    monkeypatch, sample_project, sample_project_root, compile_first, platform_name,
):
    set_module_platform(monkeypatch, document_runtime, platform_name)
    document = _Document(sample_project, sample_project_root)
    plan = compile_session_plan(sample_project, refresh_hz=60, project_root=sample_project_root)
    before = sample_project.model_dump(mode="json")
    launch = Mock(return_value=object())
    monkeypatch.setattr(document_runtime, "_document_dependency", lambda _name: launch)
    monkeypatch.setattr(macos_session_process, "launch_macos_test_session", launch)
    selected = r"\\.\DISPLAY7" if platform_name == "win32" else "macos:73"
    if compile_first:
        document.prepare_participant_randomization = Mock(return_value=None)
        document.prepare_session_launch = Mock(return_value=plan)
        document.launch_session(
            refresh_hz=60, participant_number="0", display_index=None,
            display_device_name=selected,
        )
    else:
        document.launch_compiled_session(
            plan, participant_number="0", display_index=None, display_device_name=selected,
        )

    settings = launch.call_args.kwargs["launch_settings"]
    assert settings.display_device_name == selected
    assert settings.display_index is None
    assert settings.as_runtime_options()["display_device_name"] == selected
    assert sample_project.model_dump(mode="json") == before
