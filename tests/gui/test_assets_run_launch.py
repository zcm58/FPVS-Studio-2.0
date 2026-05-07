"""PySide6 GUI workflow tests for the Phase 5 authoring application."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox,
)
from tests.gui.helpers import (
    _open_created_project,
    _prepare_compile_ready_project,
    _write_image_directory,
)

from fpvs_studio.core.enums import RunMode, StimulusVariant
from fpvs_studio.core.execution import SessionExecutionSummary
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.main_window import ParticipantNumberDialog


def test_assets_preprocessing_import_and_materialize_updates_status(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Assets Project")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    base_dir = _write_image_directory(tmp_path / "asset-base")
    oddball_dir = _write_image_directory(tmp_path / "asset-oddball")
    selection = iter([str(base_dir), str(oddball_dir)])
    monkeypatch.setattr(
        "fpvs_studio.gui.assets_pages.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: next(selection),
    )

    window.assets_page.refresh()
    window.assets_page.assets_table.selectRow(0)
    window.assets_page.import_source_button.click()
    window.assets_page.assets_table.selectRow(1)
    window.assets_page.import_source_button.click()
    window.assets_page.materialize_button.click()

    qtbot.waitUntil(
        lambda: StimulusVariant.GRAYSCALE
        in window.document.project.stimulus_sets[0].available_variants
    )
    assert window.document.manifest is not None
    assert "Catalog status:" in window.assets_page.assets_status_text.toPlainText()


def test_assets_import_validation_failure_is_reported(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Invalid Assets Project")
    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)

    invalid_dir = tmp_path / "invalid-assets"
    _write_image_directory(invalid_dir, size=(96, 96))
    Image.new("RGB", (128, 96), color=(255, 0, 0)).save(invalid_dir / "mismatch.png")

    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.assets_pages.QFileDialog.getExistingDirectory",
        lambda *args, **kwargs: str(invalid_dir),
    )

    def _capture_exec(dialog: QMessageBox) -> int:
        messages.append(dialog.text())
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr("fpvs_studio.gui.window_helpers.QMessageBox.exec", _capture_exec)

    window.assets_page.refresh()
    window.assets_page.assets_table.selectRow(0)
    window.assets_page.import_source_button.click()

    assert any("identical resolution" in message for message in messages)


def test_launch_invokes_backend_preflight_before_participant_prompt(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Preflight Project")
    _prepare_compile_ready_project(window, tmp_path / "preflight")

    captures: dict[str, object] = {}
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )
    phase_trace: list[str] = []

    def _fake_prompt() -> None:
        phase_trace.append("prompt")
        return None

    launch_calls = 0

    def _fake_launch(*_args, **_kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("launch_session should not run when prompt returns None")

    def _capture_preflight(project_root, session_plan, engine):
        phase_trace.append("preflight")
        captures.update(
            {
                "project_root": project_root,
                "session_id": session_plan.session_id,
                "engine": engine,
            }
        )

    monkeypatch.setattr("fpvs_studio.gui.document.preflight_session_plan", _capture_preflight)
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert captures["project_root"] == window.document.project_root
    assert captures["engine"] == {"engine_name": "psychopy"}
    assert phase_trace == ["preflight", "prompt"]
    assert launch_calls == 0
    assert "launch checks passed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_action_wires_runtime_launcher_with_serial_settings(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Project")
    _prepare_compile_ready_project(window, tmp_path / "launch")

    captures: dict[str, object] = {}
    participant_number = "00042"
    prompt_calls = 0
    progress_events: list[str] = []
    progress_dialogs: list[object] = []

    class _FakeProgressDialog:
        def __init__(self, label, cancel_text, minimum, maximum, parent) -> None:
            self.label = label
            self.cancel_text = cancel_text
            self.minimum = minimum
            self.maximum = maximum
            self.parent = parent
            self.window_title = ""
            self.cancel_button = object()
            self.window_modality = None
            self.minimum_duration = None
            self.shown = False
            self.closed = False
            progress_events.append("created")
            progress_dialogs.append(self)

        def setWindowTitle(self, title) -> None:  # noqa: N802
            self.window_title = title

        def setCancelButton(self, button) -> None:  # noqa: N802
            self.cancel_button = button

        def setWindowModality(self, modality) -> None:  # noqa: N802
            self.window_modality = modality

        def setMinimumDuration(self, duration_ms) -> None:  # noqa: N802
            self.minimum_duration = duration_ms

        def show(self) -> None:
            self.shown = True
            progress_events.append("shown")

        def close(self) -> None:
            self.closed = True
            progress_events.append("closed")

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        assert progress_events == ["created", "shown"]
        captures["project_root"] = project_root
        captures["session_plan"] = session_plan
        captures["participant_number"] = participant_number
        captures["launch_settings"] = launch_settings
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir=f"runs/{session_plan.session_id}",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return participant_number

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr("fpvs_studio.gui.main_window.QProgressDialog", _FakeProgressDialog)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    window.run_page.serial_port_edit.setText("COM3")
    window.run_page.serial_port_edit.editingFinished.emit()
    window.document.update_trigger_settings(baudrate=57600)
    window.run_page.display_index_edit.setText("1")
    assert window.run_page.serial_baudrate_spin.isEnabled() is False
    assert (
        window.setup_dashboard_page.runtime_settings_editor.serial_baudrate_spin.isEnabled()
        is False
    )
    assert window.run_page.fullscreen_checkbox.isChecked() is True

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: "launch_settings" in captures)
    launch_settings = captures["launch_settings"]
    assert len(progress_dialogs) == 1
    progress_dialog = progress_dialogs[0]
    qtbot.waitUntil(lambda: progress_dialog.closed)
    assert prompt_calls == 1
    assert captures["participant_number"] == participant_number
    assert captures["project_root"] == window.document.project_root
    assert progress_dialog.label == "Launching experiment: Please wait"
    assert progress_dialog.window_title == "FPVS Studio"
    assert progress_dialog.minimum == 0
    assert progress_dialog.maximum == 0
    assert progress_dialog.cancel_button is None
    assert progress_dialog.window_modality == Qt.WindowModality.WindowModal
    assert progress_dialog.minimum_duration == 0
    assert progress_dialog.shown is True
    assert progress_dialog.closed is True
    assert progress_events == ["created", "shown", "closed"]
    assert launch_settings.serial_port == "COM3"
    assert launch_settings.serial_baudrate == 57600
    assert launch_settings.display_index == 1
    assert launch_settings.test_mode is True
    assert launch_settings.fullscreen is True
    assert launch_settings.strict_timing is True
    assert launch_settings.strict_timing_warmup is False
    assert launch_settings.timing_miss_threshold_multiplier == 4.0
    assert (
        f"participant number: {participant_number}"
        in window.run_page.summary_text.toPlainText().lower()
    )
    assert "runtime launch completed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_after_preview_reprepares_once_per_click(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Preview Then Launch Project")
    _prepare_compile_ready_project(window, tmp_path / "preview-then-launch")

    qtbot.mouseClick(window.run_page.compile_button, Qt.MouseButton.LeftButton)
    assert "session preview refreshed" in window.run_page.summary_text.toPlainText().lower()

    original_prepare = window.document.prepare_test_session_launch
    prepare_calls: list[float] = []
    preflight_session_ids: list[str] = []
    launched_session_ids: list[str] = []

    def _capture_prepare(*, refresh_hz, engine_name="psychopy"):
        prepare_calls.append(refresh_hz)
        return original_prepare(refresh_hz=refresh_hz, engine_name=engine_name)

    def _capture_launch(project_root, session_plan, participant_number, launch_settings):
        launched_session_ids.append(session_plan.session_id)
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir=f"runs/{session_plan.session_id}",
        )

    monkeypatch.setattr(window.document, "prepare_test_session_launch", _capture_prepare)
    monkeypatch.setattr(
        "fpvs_studio.gui.document.create_engine",
        lambda engine_name: {"engine_name": engine_name},
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.document.preflight_session_plan",
        lambda project_root, session_plan, engine: preflight_session_ids.append(
            session_plan.session_id
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "00052")
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _capture_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert len(prepare_calls) == 1
    assert len(preflight_session_ids) == 1
    qtbot.waitUntil(lambda: bool(launched_session_ids))
    assert launched_session_ids == preflight_session_ids
    assert "runtime launch completed" in window.run_page.summary_text.toPlainText().lower()


def test_launch_action_surfaces_abort_reason_when_runtime_aborts(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Abort Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-abort")

    participant_number = "00043"
    info_calls = 0
    warning_payloads: list[tuple[str, str]] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 0, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=0,
            aborted=True,
            abort_reason=(
                "Strict timing aborted run during warmup: frame interval at index 18 was "
                "0.025840 s, exceeding 1.50x expected 0.016667 s."
            ),
            output_dir="runs/00043",
        )

    def _capture_information(*_args, **_kwargs):
        nonlocal info_calls
        info_calls += 1
        return QMessageBox.StandardButton.Ok

    def _capture_warning(_parent, title, text):
        warning_payloads.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(
        window.run_page,
        "_prompt_participant_number",
        lambda: participant_number,
    )
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        _capture_information,
    )
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.warning",
        _capture_warning,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: bool(warning_payloads))
    summary_text = window.run_page.summary_text.toPlainText().lower()
    assert info_calls == 0
    assert len(warning_payloads) == 1
    assert warning_payloads[0][0] == "Launch Aborted"
    assert "strict timing aborted run during warmup" in warning_payloads[0][1].lower()
    assert "runtime launch completed" not in summary_text
    assert "runtime launch aborted" in summary_text
    assert "abort reason:" in summary_text


def test_launch_action_closes_progress_dialog_when_runtime_launch_raises(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Error Progress Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-error-progress")

    events: list[str] = []
    captured_errors: list[tuple[str, str]] = []

    class _FakeProgressDialog:
        def __init__(self, label, cancel_text, minimum, maximum, parent) -> None:
            self.label = label
            self.cancel_text = cancel_text
            self.minimum = minimum
            self.maximum = maximum
            self.parent = parent
            self.window_title = ""
            self.cancel_button = object()
            self.window_modality = None
            self.minimum_duration = None
            self.closed = False
            events.append("created")

        def setWindowTitle(self, title) -> None:  # noqa: N802
            self.window_title = title

        def setCancelButton(self, button) -> None:  # noqa: N802
            self.cancel_button = button

        def setWindowModality(self, modality) -> None:  # noqa: N802
            self.window_modality = modality

        def setMinimumDuration(self, duration_ms) -> None:  # noqa: N802
            self.minimum_duration = duration_ms

        def show(self) -> None:
            events.append("shown")

        def close(self) -> None:
            self.closed = True
            events.append("closed")

    def _fake_launch(*_args, **_kwargs):
        events.append("launch_called")
        raise RuntimeError("Intentional launch failure.")

    def _capture_error_dialog(_parent, title, error) -> None:
        events.append("error_dialog")
        captured_errors.append((title, str(error)))

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: "00077")
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr("fpvs_studio.gui.main_window.QProgressDialog", _FakeProgressDialog)
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog", _capture_error_dialog)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: bool(captured_errors))
    assert captured_errors == [("Launch Error", "Intentional launch failure.")]
    assert events[0:2] == ["created", "shown"]
    assert "launch_called" in events
    assert "closed" in events
    assert "error_dialog" in events


def test_launch_action_duplicate_participant_yes_still_launches(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Duplicate Participant Yes")
    _prepare_compile_ready_project(window, tmp_path / "launch-duplicate-yes")

    captures: dict[str, object] = {}
    prompt_calls = 0
    warning_messages: list[str] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["participant_number"] = participant_number
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir="runs/00011_run2",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return "00011"

    def _fake_question(_parent, _title, text, *_args, **_kwargs):
        warning_messages.append(text)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr(
        window.document, "has_completed_session_for_participant", lambda value: value == "00011"
    )
    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.question", _fake_question)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert prompt_calls == 1
    qtbot.waitUntil(lambda: "participant_number" in captures)
    assert captures["participant_number"] == "00011"
    assert len(warning_messages) == 1
    assert "already completed this study" in warning_messages[0]


def test_launch_action_duplicate_participant_no_reprompts_until_new_value(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Duplicate Participant No")
    _prepare_compile_ready_project(window, tmp_path / "launch-duplicate-no")

    captures: dict[str, object] = {}
    prompt_sequence = iter(["00011", "00011", "00012"])
    prompt_calls = 0
    warning_messages: list[str] = []

    def _fake_launch(project_root, session_plan, participant_number, launch_settings):
        captures["participant_number"] = participant_number
        return SessionExecutionSummary(
            project_id=session_plan.project_id,
            session_id=session_plan.session_id,
            engine_name="stub",
            run_mode=RunMode.TEST,
            participant_number=participant_number,
            random_seed=session_plan.random_seed,
            started_at=datetime(2026, 3, 8, 10, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 8, 10, 1, tzinfo=timezone.utc),
            total_condition_count=session_plan.total_runs,
            completed_condition_count=session_plan.total_runs,
            output_dir="runs/00012",
        )

    def _fake_prompt() -> str:
        nonlocal prompt_calls
        prompt_calls += 1
        return next(prompt_sequence)

    def _fake_question(_parent, _title, text, *_args, **_kwargs):
        warning_messages.append(text)
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", _fake_prompt)
    monkeypatch.setattr(
        window.document, "has_completed_session_for_participant", lambda value: value == "00011"
    )
    monkeypatch.setattr("fpvs_studio.gui.main_window.QMessageBox.question", _fake_question)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert prompt_calls == 3
    assert len(warning_messages) == 2
    qtbot.waitUntil(lambda: "participant_number" in captures)
    assert captures["participant_number"] == "00012"


def test_launch_action_cancelled_participant_prompt_aborts_launch(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Launch Cancel Project")
    _prepare_compile_ready_project(window, tmp_path / "launch-cancel")

    launch_calls = 0

    def _fake_launch(*args, **kwargs):
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError(
            "launch_session should not be called when participant entry is cancelled"
        )

    monkeypatch.setattr(
        window.document,
        "prepare_test_session_launch",
        lambda refresh_hz, engine_name="psychopy": window.document.compile_session(
            refresh_hz=refresh_hz
        ),
    )
    monkeypatch.setattr(window.run_page, "_prompt_participant_number", lambda: None)
    monkeypatch.setattr("fpvs_studio.gui.document.launch_session", _fake_launch)

    qtbot.mouseClick(window.run_page.launch_button, Qt.MouseButton.LeftButton)

    assert launch_calls == 0
    assert "runtime launch completed" not in window.run_page.summary_text.toPlainText().lower()


def test_participant_number_dialog_requires_digits_and_trims_whitespace(qtbot, monkeypatch) -> None:
    dialog = ParticipantNumberDialog()
    qtbot.addWidget(dialog)
    assert dialog.prompt_label.text() == "Please enter the participant number."

    messages: list[str] = []
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.warning",
        lambda _parent, _title, message: messages.append(message),
    )

    dialog.participant_number_edit.setText("   ")
    dialog.accept()
    assert dialog.result() != int(dialog.DialogCode.Accepted)

    dialog.participant_number_edit.setText("A12")
    dialog.accept()
    assert dialog.result() != int(dialog.DialogCode.Accepted)

    dialog.participant_number_edit.setText(" 0012 ")
    dialog.accept()
    assert dialog.result() == int(dialog.DialogCode.Accepted)
    assert dialog.participant_number == "0012"
    assert any("Enter a participant number" in message for message in messages)
    assert any("digits only" in message for message in messages)


def test_unsaved_changes_state_and_guard(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _, window = _open_created_project(controller, qtbot, tmp_path, "Dirty Project")

    qtbot.mouseClick(window.conditions_page.add_condition_button, Qt.MouseButton.LeftButton)
    assert window.document.dirty is True
    assert window.windowTitle().startswith("*")

    assert window.save_project() is True
    assert window.document.dirty is False
    assert not window.windowTitle().startswith("*")

    window.setup_dashboard_page.project_overview_editor.project_name_edit.setText(
        "Dirty Project Updated"
    )
    window.setup_dashboard_page.project_overview_editor.project_name_edit.editingFinished.emit()
    assert window.document.dirty is True

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert window.maybe_save_changes() is False

    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    assert window.maybe_save_changes() is True
