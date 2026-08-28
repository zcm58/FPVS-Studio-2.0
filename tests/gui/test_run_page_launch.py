"""Focused GUI workflow tests split from the former layout dashboard suite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QWidget,
)
from tests.gui.helpers import (
    _assert_visible_children_within_parent,
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
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.run_page import (
    TEST_MODE_PARTICIPANT_NUMBER,
    BioSemiRecordingConfirmationDialog,
    ParticipantLaunchDetails,
    ParticipantNumberDialog,
    TestModeLaunchConfirmationDialog,
    TestModeLaunchSelection,
)


def test_participant_dialog_collects_and_prefills_manual_removed_electrodes(
    qtbot,
) -> None:
    dialog = ParticipantNumberDialog(
        manual_removed_electrodes={"0007": ["FT7", "P9"]}
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    participant_number_edit = dialog.findChild(QLineEdit, "participant_number_edit")
    manual_removed_edit = dialog.findChild(
        QLineEdit,
        "participant_manual_removed_electrodes_edit",
    )
    assert participant_number_edit is not None
    assert manual_removed_edit is not None
    assert dialog.minimumSize().width() == 600
    assert dialog.minimumSize().height() == 360
    assert manual_removed_edit.placeholderText() == (
        "Input manually removed electrodes (optional)"
    )
    assert manual_removed_edit.fontMetrics().horizontalAdvance(
        manual_removed_edit.placeholderText()
    ) <= manual_removed_edit.contentsRect().width() - 16

    participant_number_edit.setText("0007")
    assert manual_removed_edit.text() == "FT7, P9"

    participant_number_edit.setText(" 0007 ")
    manual_removed_edit.setText(" ft7, P9; Oz\nFT7 ")
    assert dialog.manual_removed_electrodes == ("FT7", "P9", "OZ")
    _assert_visible_children_within_parent(dialog)

    dialog.age_edit.setText("30")
    dialog.sex_combo.setCurrentIndex(dialog.sex_combo.findData("Female"))
    dialog.handedness_combo.setCurrentIndex(
        dialog.handedness_combo.findData("Right handed")
    )
    dialog.colorblind_combo.setCurrentIndex(dialog.colorblind_combo.findData(False))
    dialog.accept()

    assert dialog.participant_number == "0007"
    assert dialog.manual_removed_electrodes == ("FT7", "P9", "OZ")


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

    assert window.document.project.settings.display.background_color == "#123456"
    assert window._setup_wizard_page is None

    run_page = window.run_page

    assert window.document.project.settings.display.background_color == "#000000"
    assert window.document.dirty is True
    assert run_page.runtime_background_color_combo.currentText() == "Black"


def test_run_page_readiness_and_launch_feedback_is_updated_on_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Home Status Project")
    run_readiness_list = window.run_page.findChild(QListWidget, "run_readiness_checklist")
    run_launch_button = window.run_page.findChild(QPushButton, "launch_session_button")
    run_status_label = window.run_page.findChild(QLabel, "run_readiness_badge")
    assert run_readiness_list is not None
    assert run_launch_button is not None
    assert run_status_label is not None
    readiness_text = _list_widget_text(run_readiness_list)
    assert "[OK]" not in readiness_text
    assert "[TODO]" not in readiness_text
    assert "fullscreen session with display and timing checks" in readiness_text.lower()
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
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "7")

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["participant_number"] = participant_number
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.SESSION,
            participant_number=participant_number,
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir=f"runs/{session_plan.session_id}",
        )

    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)

    window.run_page.launch_session()

    assert window.home_page.findChild(QListWidget, "home_readiness_checklist") is None
    assert window.home_page.findChild(QListWidget, "home_recent_activity_list") is None
    assert window.home_page.findChild(QGroupBox, "home_preflight_card") is None

    assert captures["project_root"] == window.document.project_root
    qtbot.waitUntil(
        lambda: (
            "status: runtime launch completed"
            in window.run_page.summary_text.toPlainText().lower()
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
                colorblind=True,
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

    window.run_page.launch_session()

    assert captures["participant_number"] == "7"
    assert captures["participant_metadata"] == ParticipantMetadata(
        age=71,
        sex="Female",
        handedness="Right handed",
        colorblind=True,
    )
    assert captures["display_index"] is None
    assert captures["fullscreen"] is True
    assert window.run_page.findChild(QWidget, "display_index_edit") is None
    assert window.run_page.findChild(QWidget, "engine_name_value") is None


def test_biosemi_recording_confirmation_dialog_blocks_continue_until_confirm(
    qtbot,
) -> None:
    dialog = BioSemiRecordingConfirmationDialog()
    qtbot.addWidget(dialog)

    prompt = dialog.findChild(QLabel, "biosemi_recording_confirmation_prompt")
    confirmation_edit = dialog.findChild(QLineEdit, "biosemi_recording_confirmation_edit")
    button_box = dialog.findChild(
        QDialogButtonBox,
        "biosemi_recording_confirmation_button_box",
    )
    assert prompt is not None
    assert confirmation_edit is not None
    assert button_box is not None
    continue_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert continue_button is not None
    assert continue_button.text() == "Continue"
    assert continue_button.isEnabled() is False
    assert dialog.windowTitle() == "Sophia Mode Recording Check"
    assert "NERD Lab Administrator" in prompt.text()
    assert "Sophia Mode is enabled" in prompt.text()

    confirmation_edit.setText("con")
    assert continue_button.isEnabled() is False

    confirmation_edit.setText(" CONFIRM ")
    assert continue_button.isEnabled() is True


def test_test_mode_launch_confirmation_requires_explicit_acknowledgement(
    qtbot,
) -> None:
    long_condition_name = (
        "Word Recognition With Pre-Task Encoding and a Deliberately Long Display Name"
    )
    dialog = TestModeLaunchConfirmationDialog(
        conditions=(
            ("faces", "Faces"),
            ("word-recognition", long_condition_name),
        )
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    prompt = dialog.findChild(QLabel, "test_mode_launch_confirmation_prompt")
    condition_combo = dialog.findChild(QComboBox, "test_mode_condition_combo")
    acknowledgement = dialog.findChild(
        QCheckBox,
        "test_mode_launch_acknowledgement_checkbox",
    )
    button_box = dialog.findChild(
        QDialogButtonBox,
        "test_mode_launch_confirmation_button_box",
    )
    assert prompt is not None
    assert condition_combo is not None
    assert acknowledgement is not None
    assert button_box is not None
    launch_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert launch_button is not None
    assert dialog.size().width() == 700
    assert dialog.size().height() == 380
    assert dialog.windowTitle() == "Confirm Experiment Test Launch"
    assert "Serial-port validation" in prompt.text()
    assert "participant information collection" in prompt.text()
    assert "reserved test ID 0" in prompt.text()
    assert "runtime timing QC" in prompt.text()
    assert condition_combo.count() == 3
    assert "All conditions" in condition_combo.currentText()
    assert dialog.selected_condition_ids is None
    assert launch_button.text() == "Launch Test"
    assert launch_button.isEnabled() is False
    assert acknowledgement.width() >= acknowledgement.fontMetrics().horizontalAdvance(
        acknowledgement.text()
    )

    condition_combo.setCurrentIndex(2)
    QApplication.processEvents()

    assert dialog.selected_condition_ids == ("word-recognition",)
    assert long_condition_name in condition_combo.currentText()
    assert condition_combo.toolTip() == condition_combo.currentText()
    _assert_visible_children_within_parent(dialog)

    acknowledgement.setChecked(True)

    assert launch_button.isEnabled() is True


def test_run_page_test_mode_confirmation_returns_selected_scope_or_cancel(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Test Scope Prompt")
    window.document.create_condition(name="Faces")
    selected_condition_id = window.document.create_condition(name="Word Recognition")

    def _accept_selected(dialog: TestModeLaunchConfirmationDialog) -> int:
        selected_index = dialog.condition_combo.findData(selected_condition_id)
        assert selected_index > 0
        dialog.condition_combo.setCurrentIndex(selected_index)
        return int(dialog.DialogCode.Accepted)

    monkeypatch.setattr(TestModeLaunchConfirmationDialog, "exec", _accept_selected)

    selection = window.run_page._confirm_test_mode_launch()

    assert selection == TestModeLaunchSelection(
        selected_condition_ids=(selected_condition_id,)
    )

    monkeypatch.setattr(
        TestModeLaunchConfirmationDialog,
        "exec",
        lambda dialog: int(dialog.DialogCode.Rejected),
    )

    assert window.run_page._confirm_test_mode_launch() is None


def test_run_page_test_mode_skips_participant_collection_and_uses_reserved_id(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Test Mode Launch")
    _prepare_compile_ready_project(window, tmp_path / "test-mode-launch-first")
    _prepare_compile_ready_project(window, tmp_path / "test-mode-launch-second")
    selected_condition_id = window.document.ordered_conditions()[1].condition_id
    window.document.set_experiment_test_mode_enabled(True)
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", _ImmediateProgressTask)
    monkeypatch.setattr(
        window.run_page,
        "_confirm_test_mode_launch",
        lambda: TestModeLaunchSelection(
            selected_condition_ids=(selected_condition_id,)
        ),
    )
    monkeypatch.setattr(
        window.run_page,
        "_prompt_participant_number",
        lambda: (_ for _ in ()).throw(
            AssertionError("Participant dialog must not open in Experiment Test Mode")
        ),
    )
    monkeypatch.setattr(
        window.run_page,
        "_confirm_biosemi_recording_started",
        lambda: (_ for _ in ()).throw(
            AssertionError("BioSemi confirmation must not open in Experiment Test Mode")
        ),
    )
    monkeypatch.setattr(window.document, "preflight_compiled_session", lambda _plan: None)
    captures: dict[str, object] = {}

    def _capture_launch(session_plan, **kwargs):
        captures["session_plan"] = session_plan
        captures.update(kwargs)
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.SESSION,
            participant_number=kwargs["participant_number"],
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
        )

    monkeypatch.setattr(window.document, "launch_compiled_session", _capture_launch)

    window.run_page.launch_session()

    assert captures["participant_number"] == TEST_MODE_PARTICIPANT_NUMBER
    assert captures["participant_metadata"] is None
    session_plan = captures["session_plan"]
    assert isinstance(session_plan, SessionPlan)
    assert session_plan.total_runs == window.document.project.settings.session.block_count
    assert {
        entry.condition_id for entry in session_plan.ordered_entries()
    } == {selected_condition_id}
    assert all(
        block.condition_order == [selected_condition_id]
        for block in session_plan.blocks
    )
    assert window.document.project.manual_removed_electrodes == {}
    assert (
        "Launch Mode: Experiment Test (reserved ID 0)" in window.run_page.summary_text.toPlainText()
    )


def test_run_page_biosemi_confirmation_cancel_blocks_runtime_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "BioSemi Cancel Project")
    _prepare_compile_ready_project(window, tmp_path / "biosemi-cancel")
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: None,
    )
    monkeypatch.setattr(
        window.run_page,
        "_prompt_participant_number",
        lambda: ParticipantLaunchDetails(
            participant_number="7",
            participant_metadata=ParticipantMetadata(
                age=71,
                sex="Female",
                handedness="Right handed",
                colorblind=True,
            ),
            manual_removed_electrodes=(" ft7 ", "P9", "FT7"),
        ),
    )
    monkeypatch.setattr(window.run_page, "_confirm_biosemi_recording_started", lambda: False)

    def _unexpected_launch(*_args, **_kwargs):
        raise AssertionError("Runtime launch should not start when BioSemi check is cancelled")

    monkeypatch.setattr(window.document, "launch_compiled_session", _unexpected_launch)

    window.run_page.launch_session()

    assert window.run_page._active_launch_task is None
    assert "status: launch checks queued" in window.run_page.summary_text.toPlainText().lower()
    assert load_project_file(
        window.document.project_file_path
    ).manual_removed_electrodes == {"7": ["FT7", "P9"]}


def test_run_page_participant_prompt_cancel_does_not_add_electrode_entry(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Participant Cancel")
    _prepare_compile_ready_project(window, tmp_path / "participant-cancel")
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: None)

    window.run_page.launch_session()

    assert window.run_page._active_launch_task is None
    assert load_project_file(
        window.document.project_file_path
    ).manual_removed_electrodes == {}


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
            run_mode=RunMode.SESSION,
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
        "The experiment finished. Review participant summary files in the project "
        "logs folder."
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

    window.run_page.launch_session()

    assert captured_errors == [("Launch Error", warning_message)]
    assert window.run_page._active_launch_task is None
