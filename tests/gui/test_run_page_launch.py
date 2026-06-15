"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _ImmediateProgressTask,
    _list_widget_text,
    _open_created_project,
    _prepare_compile_ready_project,
)

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import (
    load_project_file,
    save_project_file,
)
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.run_page import ParticipantLaunchDetails


def test_background_color_control_is_run_tab_presets_only(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Runtime Background Presets")

    assert (
        window.setup_dashboard_page.project_overview_editor.findChild(
            QWidget, "background_color_edit"
        )
        is None
    )

    runtime_background_combo = window.run_page.findChild(
        QComboBox, "runtime_background_color_combo"
    )
    assert runtime_background_combo is not None
    assert runtime_background_combo.count() == 2
    assert runtime_background_combo.itemText(0) == "Black"
    assert runtime_background_combo.itemData(0) == "#000000"
    assert runtime_background_combo.itemText(1) == "Dark Gray"
    assert runtime_background_combo.itemData(1) == "#101010"
    assert runtime_background_combo.currentText() == "Black"

    scope_label = window.run_page.findChild(QLabel, "runtime_background_scope_label")
    assert scope_label is not None
    assert scope_label.text() == "Used during FPVS image presentation."


def test_run_page_refresh_normalizes_legacy_background_to_black_and_marks_dirty(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    scaffold = create_project(tmp_path, "Legacy Background Migration")
    project_file_path = scaffold.project_root / "project.json"
    legacy_project = load_project_file(project_file_path)
    assert legacy_project.settings.display.background_color == "#000000"
    legacy_display_settings = legacy_project.settings.display.model_copy(
        update={"background_color": "#123456"}
    )
    legacy_settings = legacy_project.settings.model_copy(
        update={"display": legacy_display_settings}
    )
    save_project_file(
        legacy_project.model_copy(update={"settings": legacy_settings}),
        project_file_path,
    )
    assert load_project_file(project_file_path).settings.display.background_color == "#123456"

    document = controller.open_project(scaffold.project_root)
    assert document is not None
    assert controller.main_window is not None
    qtbot.addWidget(controller.main_window)
    window = controller.main_window

    assert window.document.project.settings.display.background_color == "#000000"
    assert window.document.dirty is True
    assert window.run_page.runtime_background_color_combo.currentText() == "Black"


def test_run_page_readiness_and_launch_feedback_is_updated_on_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Status Project")
    run_readiness_list = window.run_page.findChild(QListWidget, "run_readiness_checklist")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_test_session_button")
    run_status_label = window.run_page.findChild(QLabel, "run_readiness_badge")
    assert run_readiness_list is not None
    assert run_launch_button is not None
    assert run_status_label is not None
    readiness_text = _list_widget_text(run_readiness_list)
    assert "[OK]" not in readiness_text
    assert "[TODO]" not in readiness_text
    assert "runtime path: beta test-mode only" in readiness_text.lower()
    assert run_status_label.text()

    _prepare_compile_ready_project(window, tmp_path / "home-status-preflight")

    captures: dict[str, object] = {}
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: captures.update(
            {
                "project_root": project_root,
                "session_id": session_plan.session_id,
                "engine": engine,
            }
        ),
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: None)

    window.run_page.launch_test_session()

    assert window.home_page.findChild(QListWidget, "home_readiness_checklist") is None
    assert window.home_page.findChild(QListWidget, "home_recent_activity_list") is None
    assert window.home_page.findChild(QGroupBox, "home_preflight_card") is None

    assert captures["project_root"] == window.document.project_root
    qtbot.waitUntil(
        lambda: (
            "status: launch checks passed" in window.run_page.summary_text.toPlainText().lower()
        ),
    )


def test_run_page_launch_uses_fixed_current_runtime_defaults(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Fixed Runtime Defaults")
    _prepare_compile_ready_project(window, tmp_path / "fixed-runtime-defaults")
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: None,
    )
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(
        window.run_page,
        "_prompt_participant_number",
        lambda: ParticipantLaunchDetails(
            participant_number="7",
            participant_metadata=ParticipantMetadata(
                age=71,
                sex="Female",
                handedness="Right handed",
            ),
        ),
    )
    monkeypatch.setattr(window.run_page, "_on_launch_succeeded", lambda result: None)
    captures: dict[str, object] = {}

    def _capture_launch(session_plan, **kwargs):
        captures["session_id"] = session_plan.session_id
        captures.update(kwargs)
        return object()

    monkeypatch.setattr(window.document, "launch_compiled_session", _capture_launch)

    window.run_page.launch_test_session()

    assert captures["participant_number"] == "7"
    assert captures["participant_metadata"] == ParticipantMetadata(
        age=71,
        sex="Female",
        handedness="Right handed",
    )
    assert captures["display_index"] is None
    assert captures["fullscreen"] is True
    assert window.run_page.findChild(QWidget, "display_index_edit") is None
    assert window.run_page.findChild(QWidget, "engine_name_value") is None


def test_run_page_compact_export_completion_points_to_logs(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Compact Export Summary")
    _prepare_compile_ready_project(window, tmp_path / "compact-export-summary")
    session_plan = window.document.compile_session(refresh_hz=60.0)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )

    window.run_page._apply_launch_summary(
        session_plan,
        "0007",
        SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number="0007",
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir=None,
        ),
    )

    summary_text = window.run_page.summary_text.toPlainText()
    open_folder_button = window.run_page.findChild(QPushButton, "run_open_folder_button")
    copy_folder_button = window.run_page.findChild(QPushButton, "run_copy_folder_button")

    assert "Output: Compact summary logs" in summary_text
    assert open_folder_button is not None
    assert copy_folder_button is not None
    assert open_folder_button.isHidden()
    assert copy_folder_button.isHidden()
    assert messages == [
        "The experiment finished on the current beta test-mode path. "
        "Review participant summary files in the project logs folder."
    ]


def test_run_page_surfaces_blocking_resolution_mismatch_warning(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Resolution Warning")
    _prepare_compile_ready_project(window, tmp_path / "resolution-warning")
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: None,
    )
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "7")
    warning_message = (
        "Warning: this project was configured to be run on a display with "
        "1920x1080 resolution, but this monitor is currently running at "
        "3440x1440 resolution."
    )
    captured_errors: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.run_page._show_runtime_error_dialog",
        lambda parent, title, error: captured_errors.append((title, str(error))),
    )

    def _raise_resolution_warning(*_args, **_kwargs):
        raise RuntimeError(warning_message)

    monkeypatch.setattr(window.document, "launch_compiled_session", _raise_resolution_warning)

    window.run_page.launch_test_session()

    assert captured_errors == [("Launch Error", warning_message)]
    assert window.run_page._active_launch_task is None
