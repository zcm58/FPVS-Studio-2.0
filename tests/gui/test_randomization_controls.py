"""Registered configured seed editing, launch lifecycle and compact layout coverage."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel
from tests.gui.helpers import (
    _open_created_project,
    assert_visible_children_within_parent,
    record_setup_validation_dialogs,
)
from tests.gui.test_condition_timing_table import _document

from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.core.randomization import RandomizationSeeds, configured_randomization_seeds
from fpvs_studio.gui.document import DocumentError, ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import ExperimentDesignerWidget
from fpvs_studio.gui.randomization_editor import RandomizationEditor
from fpvs_studio.gui.run_page import LaunchTaskResult, ParticipantLaunchDetails
from fpvs_studio.gui.setup_wizard_page import SetupWizardPage


class _HoldLaunchTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, **kwargs):
        super().__init__(kwargs["parent_widget"])
        self.callback = kwargs["callback"]

    def start(self):
        pass


def _seeds(order=22, stimulus=11, fixation=33):
    return RandomizationSeeds(
        condition_order_seed=order, stimulus_seed=stimulus, fixation_seed=fixation,
    )


def _word_document(tmp_path):
    document, first, second = _document(tmp_path)
    document.set_condition_stimulus_modality(first, modality=StimulusModality.WORD)
    document.update_condition_words(first, role="base", words=["chair", "desk"])
    document.update_condition_words(first, role="oddball", words=["fear", "anger"])
    document.update_fixation_settings(enabled=False, accuracy_task_enabled=False)
    return document, first, second


def test_legacy_seed_controls_do_not_rewrite_source_and_one_policy_covers_all_fields(
    qtbot, tmp_path,
):
    document, _first, _second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    expected = configured_randomization_seeds(original)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    assert document.project == original
    assert editor.mode_combo.currentData() == "new"
    assert set(editor.seed_edits) == {"stimulus_seed", "condition_order_seed", "fixation_seed"}
    assert editor.seed_edits["condition_order_seed"].text() == str(expected.condition_order_seed)
    editor.mode_combo.setCurrentIndex(editor.mode_combo.findData("fixed"))
    assert document.project.settings.session.randomization_mode == "fixed"
    assert configured_randomization_seeds(document.project) == expected
    editor.seed_edits["stimulus_seed"].setText("101")
    assert editor.apply_pending_edits()
    assert configured_randomization_seeds(document.project) == _seeds(
        order=expected.condition_order_seed, stimulus=101, fixation=expected.fixation_seed,
    )
    assert "Configured seeds reused" in editor.resolved_label.text()


@pytest.mark.parametrize("invalid", ["", "-1", "1.5", "2147483648"])
def test_invalid_seed_draft_preserves_source_until_corrected(qtbot, tmp_path, invalid):
    document, _first, _second = _document(tmp_path)
    document.update_randomization_settings(
        mode="fixed", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    original = document.project.model_copy(deep=True)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    editor.seed_edits["fixation_seed"].setText(invalid)
    assert not editor.apply_pending_edits()
    assert editor.error_label.isVisible()
    assert "integer seed" in editor.error_label.text()
    assert document.project == original
    assert editor.seed_edits["fixation_seed"].text() == invalid
    editor.seed_edits["fixation_seed"].setText("44")
    assert editor.apply_pending_edits()
    assert document.project.settings.session.fixation_seed == 44


def test_explicit_generation_replaces_exactly_three_configured_seeds(qtbot, monkeypatch, tmp_path):
    document, _first, _second = _document(tmp_path)
    calls = []
    generated = _seeds()
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds",
        lambda: calls.append(True) or generated,
    )
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.generate_button.click()
    assert calls == [True]
    assert configured_randomization_seeds(document.project) == generated
    assert editor.seed_edits["stimulus_seed"].text() == "11"
    assert editor.seed_edits["condition_order_seed"].text() == "22"
    assert editor.seed_edits["fixation_seed"].text() == "33"
    assert document.dirty


def test_legacy_out_of_range_seed_opens_for_explicit_repair(qtbot, monkeypatch, tmp_path):
    document, _first, _second = _document(tmp_path)
    document.update_session_settings(session_seed=2**40)
    original = document.project.model_copy(deep=True)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    assert editor.seed_edits["condition_order_seed"].text() == str(2**40)
    assert not editor.apply_pending_edits()
    assert document.project == original
    monkeypatch.setattr("fpvs_studio.gui.document.generate_randomization_seeds", lambda: _seeds())
    editor.generate_button.click()
    assert configured_randomization_seeds(document.project) == _seeds()
    assert editor.apply_pending_edits()


def test_fixed_seeds_survive_reload_compilation_and_completed_seed_history(
    qtbot, monkeypatch, tmp_path,
):
    document, _first, _second = _word_document(tmp_path)
    document.update_randomization_settings(
        mode="fixed", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    original = reopened.project.model_copy(deep=True)

    def unexpected(*_args, **_kwargs):
        pytest.fail("Fixed mode must not read completed-seed history or generate replacement seeds")

    monkeypatch.setattr("fpvs_studio.gui.document.completed_session_seeds", unexpected)
    monkeypatch.setattr("fpvs_studio.gui.document.generate_randomization_seeds", unexpected)
    monkeypatch.setattr(reopened, "_generate_unused_session_seed", unexpected)
    assert reopened.generate_session_seed_for_app_launch() == 22
    assert reopened.ensure_unused_session_seed_for_launch() == 22
    first = reopened.compile_session(refresh_hz=60)
    second = reopened.compile_session(refresh_hz=60)
    assert first.randomization_seeds == second.randomization_seeds == _seeds()
    assert first.randomization_mode == "fixed"
    assert reopened.prepare_participant_randomization("0001", 1) == _seeds()
    reopened.finish_participant_randomization()
    assert reopened.prepare_participant_randomization("0002", 1) == _seeds()
    assert reopened.project == original
    assert not reopened.dirty


def test_new_mode_resolves_once_for_pending_retry_and_does_not_change_configured_seeds(
    qtbot, monkeypatch, tmp_path,
):
    document, _first, _second = _word_document(tmp_path)
    document.update_randomization_settings(
        mode="new", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    original = document.project.model_copy(deep=True)
    generated = iter((_seeds(101, 102, 103), _seeds(201, 202, 203), _seeds(301, 302, 303)))
    calls = []

    def generate():
        calls.append(True)
        return next(generated)

    monkeypatch.setattr("fpvs_studio.gui.document.generate_randomization_seeds", generate)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    pending = document.prepare_participant_randomization("0001", 1)
    assert pending == document.prepare_participant_randomization("0001", 1)
    compiled = document.compile_session(refresh_hz=60, resolved_seeds=pending)
    assert compiled.randomization_seeds == pending
    assert document.compile_session(refresh_hz=60).randomization_seeds == _seeds()
    assert calls == [True]
    assert "Pending launch: images/words 102" in editor.resolved_label.text()
    assert editor.seed_edits["stimulus_seed"].text() == "11"
    assert document.project == original
    document.finish_participant_randomization()
    assert "Last launch:" in editor.resolved_label.text()
    assert document.prepare_participant_randomization("0001", 2) != pending
    assert len(calls) == 2
    document.update_randomization_settings(stimulus_seed=12)
    assert document.resolved_randomization_status()[0] is None
    document.prepare_participant_randomization("0001", 2)
    assert len(calls) == 3


def test_fixed_mode_skips_open_worker_and_rejects_stale_background_results(
    qtbot, controller, monkeypatch, tmp_path,
):
    _, window = _open_created_project(controller, qtbot, tmp_path, "Stale seed worker")
    stale_signature = window.document.randomization_settings_signature()
    window.document.update_randomization_settings(
        mode="fixed", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    original = window.document.project.model_copy(deep=True)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.BackgroundTask",
        lambda **_kwargs: pytest.fail("Ordinary FPVS must not generate app-open seeds"),
    )
    window._session_seed_ready = False
    window._start_deferred_session_seed_task()
    assert window._session_seed_ready
    assert window._session_seed_task is None
    window._session_seed_generation_signature = stale_signature
    window._on_deferred_session_seed_generated(999)
    assert window.document.project == original
    assert not window.document.apply_session_seed_for_app_launch(
        888, expected_signature=stale_signature,
    )
    assert window.document.project == original


@pytest.mark.parametrize("surface", ["home", "run"])
def test_launch_entrypoints_reuse_pending_seed_triplet_after_compile_failure(
    qtbot, controller, monkeypatch, tmp_path, surface,
):
    from types import SimpleNamespace

    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    _, window = _open_created_project(controller, qtbot, tmp_path, "Pending launch seeds")
    source, _first, _second = _word_document(tmp_path)
    source.project.meta = window.document.project.meta.model_copy(deep=True)
    window.document.apply_condition_modifier_project(source.project)
    document = window.document
    document.set_experiment_test_mode_enabled(True)
    document.set_require_biosemi_recording_confirmation(False)
    owner = window if surface == "home" else window.run_page
    if surface == "run":
        owner.set_launch_gate(lambda callback: callback())
    generated = _seeds(101, 102, 103)
    generated_calls = []
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds",
        lambda: generated_calls.append(True) or generated,
    )
    monkeypatch.setattr(document, "validate_recording_launch", lambda: None)
    monkeypatch.setattr(window, "_notify_session_started", lambda callback: callback())
    monkeypatch.setattr(window, "_notify_session_completed", lambda: None)
    monkeypatch.setattr(window, "_show_home_launch_summary", lambda *_args: None)
    monkeypatch.setattr(window.run_page, "_apply_launch_summary", lambda *_args: None)
    monkeypatch.setattr("fpvs_studio.gui.main_window._show_error_dialog", lambda *_args: None)
    monkeypatch.setattr("fpvs_studio.gui.run_page._show_runtime_error_dialog", lambda *_args: None)
    original_compile = document.compile_session
    supplied = []
    compiled = []

    def compile_with_retry(**kwargs):
        supplied.append(kwargs["resolved_seeds"])
        if len(supplied) == 1:
            raise DocumentError("Correct the launch setup, then retry.")
        plan = original_compile(**kwargs)
        compiled.append(plan)
        return plan

    monkeypatch.setattr(document, "compile_session", compile_with_retry)
    monkeypatch.setattr("fpvs_studio.gui.main_window.ProgressTask", _HoldLaunchTask)
    monkeypatch.setattr("fpvs_studio.gui.run_page.ProgressTask", _HoldLaunchTask)
    details = ParticipantLaunchDetails(participant_number="TEST")
    owner._launch_participant_session(details, 60, None)
    owner._launch_participant_session(details, 60, None)
    assert supplied == [generated, generated]
    assert generated_calls == [True]
    assert compiled[0].randomization_seeds == generated
    result = LaunchTaskResult(session_plan=compiled[0], summary=SimpleNamespace())
    if surface == "home":
        owner._on_home_launch_succeeded(result)
    else:
        owner._on_launch_succeeded(result)
    assert document.resolved_randomization_status() == (generated, "Last launch")
    assert document._pending_randomization is None


def test_direct_document_launch_retains_new_seeds_after_preflight_failure(
    qtbot, monkeypatch, tmp_path,
):
    document, _first, _second = _word_document(tmp_path)
    generated = _seeds(101, 102, 103)
    calls = []
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds",
        lambda: calls.append(True) or generated,
    )
    checked = []

    def preflight(plan, **_kwargs):
        checked.append(plan.randomization_seeds)
        if len(checked) == 1:
            raise DocumentError("Retry preflight")

    summary = object()
    monkeypatch.setattr(document, "preflight_compiled_session", preflight)
    monkeypatch.setattr(document, "launch_compiled_session", lambda *_args, **_kwargs: summary)
    with pytest.raises(DocumentError, match="Retry preflight"):
        document.launch_session(refresh_hz=60, participant_number="0001", display_index=None)
    plan, result = document.launch_session(
        refresh_hz=60, participant_number="0001", display_index=None,
    )
    assert result is summary
    assert plan.randomization_seeds == generated
    assert checked == [generated, generated]
    assert calls == [True]
    assert document._pending_randomization is None


@pytest.mark.parametrize("frozen", [False, True])
def test_recovery_preserves_frozen_seeds_or_builds_explicit_current_setup_replacement(
    qtbot, controller, monkeypatch, tmp_path, frozen,
):
    from types import SimpleNamespace

    from PySide6.QtWidgets import QDialog, QMessageBox

    from fpvs_studio.runtime.condition_recovery import build_replacement_session_plan

    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    _, window = _open_created_project(controller, qtbot, tmp_path, "Recovery seed policy")
    source, first, second = _word_document(tmp_path)
    source.project.meta = window.document.project.meta.model_copy(deep=True)
    window.document.apply_condition_modifier_project(source.project)
    document = window.document
    document.update_allow_repeated_participant_sessions(True)
    document.set_require_biosemi_recording_confirmation(False)
    document.update_condition_timing(presentation_counts={first: 3, second: 2})
    original_counts = [condition.presentation_count for condition in document.project.conditions]
    original_plan = build_replacement_session_plan(document.compile_session(refresh_hz=60), first)
    record = SimpleNamespace(
        can_rerun=frozen, status="unverified", condition_id=first,
        condition_name="Words", participant_number="0001",
    )
    details = ParticipantLaunchDetails(participant_number="0001")

    class ParticipantDialog:
        DialogCode = QDialog.DialogCode
        participant_details = details
        participant_number_edit = SimpleNamespace(
            setText=lambda _text: None, setReadOnly=lambda _value: None,
        )

        def __init__(self, *_args, **_kwargs):
            pass

        def setWindowTitle(self, _text):
            pass

        def exec(self):
            return int(self.DialogCode.Accepted)

    monkeypatch.setattr("fpvs_studio.gui.main_window.ParticipantNumberDialog", ParticipantDialog)
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.QMessageBox.question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr("fpvs_studio.gui.main_window.ProgressTask", _HoldLaunchTask)
    monkeypatch.setattr(window, "_notify_session_started", lambda callback: None)
    monkeypatch.setattr(window, "flush_pending_edits", lambda: True)
    monkeypatch.setattr(window._condition_recovery, "close_dialog", lambda: None)
    monkeypatch.setattr(document, "validate_recording_launch", lambda: None)
    monkeypatch.setattr(document, "next_participant_session_number", lambda _participant: 2)
    monkeypatch.setattr(document, "launch_compiled_session", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        "fpvs_studio.gui.main_window.build_recovery_session_plan",
        lambda *_args, **_kwargs: original_plan,
    )
    generated = _seeds(101, 102, 103)
    generation_calls = []
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds",
        lambda: generation_calls.append(True) or generated,
    )
    original_compile = document.compile_session
    compiled_calls = []

    def compile_current(**kwargs):
        compiled_calls.append(kwargs)
        return original_compile(**kwargs)

    monkeypatch.setattr(document, "compile_session", compile_current)
    window._session_seed_ready = True
    window._launch_recovered_condition(record)
    result = window._active_launch_task.callback()
    assert result.session_plan.total_runs == 1
    assert result.session_plan.ordered_entries()[0].condition_id == first
    assert [condition.presentation_count for condition in document.project.conditions] == (
        original_counts
    )
    if frozen:
        assert result.session_plan == original_plan
        assert not generation_calls
        assert not compiled_calls
    else:
        assert generation_calls == [True]
        assert len(compiled_calls) == 1
        assert "condition_ids" not in compiled_calls[0]
        assert result.session_plan.randomization_seeds == generated


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("state", ["fixed", "new", "invalid", "pending", "last"])
def test_seed_controls_and_long_resolved_triplet_fit_session_and_review(
    qtbot, monkeypatch, tmp_path, background, state,
):
    document, first, second = _document(tmp_path)
    document.update_condition(
        first, name="Semantic categories with low visual similarity and high emotional salience",
    )
    document.update_condition(
        second, name="Unfamiliar written words with matched lexical and perceptual properties",
    )
    document.update_randomization_settings(
        mode="fixed" if state == "fixed" else "new", condition_order_seed=2_147_483_647,
        stimulus_seed=2_147_483_647, fixation_seed=2_147_483_647,
    )
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds",
        lambda: _seeds(2_147_483_647, 2_147_483_647, 2_147_483_647),
    )
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [],
    )
    qtbot.addWidget(wizard)
    palette = wizard.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(background))
    wizard.setPalette(palette)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="session", allow_step_jumps=True)
    editor = wizard.session_structure_editor.randomization_editor
    editor.seed_details_button.setChecked(state != "new")
    if state == "invalid":
        editor.seed_edits["fixation_seed"].setText("-1")
        assert not wizard.flush_pending_edits()
        assert wizard.has_pending_edits()
    elif state in {"pending", "last"}:
        document.prepare_participant_randomization("0001", 1)
        if state == "last":
            document.finish_participant_randomization()
    QApplication.processEvents()
    assert wizard.size().toTuple() == (1120, 820)
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface
    assert editor.isVisible()
    assert not wizard.condition_timing_table.isVisible()
    assert not wizard.runtime_settings_editor.isVisible()
    assert not wizard.session_settings_card.title_label.isVisible()
    assert wizard.session_structure_editor.presentation_total_label.text() == "4 total"
    assert_visible_children_within_parent(wizard.session_step_surface)
    for edit in editor.seed_edits.values():
        if edit.isVisible():
            assert edit.width() >= edit.fontMetrics().horizontalAdvance(edit.text()) + 12
    for label in editor.findChildren(QLabel):
        if label.isVisible() and label.text():
            assert label.height() >= label.heightForWidth(label.width()) if label.wordWrap() else (
                label.width() >= label.fontMetrics().horizontalAdvance(label.text())
            )
    if editor.generate_button.isVisible():
        assert editor.generate_button.width() >= editor.generate_button.sizeHint().width()
    if state != "invalid":
        wizard.open_wizard(step_key="review", allow_step_jumps=True)
        QApplication.processEvents()
        assert_visible_children_within_parent(wizard.review_step_surface)
        text = " ".join(label.text() for label in wizard.review_card.findChildren(QLabel))
        assert ("Same schedules for every participant." if state == "fixed"
                else "New seeds for each participant") in text


@pytest.mark.parametrize("action", ["next", "back", "home", "progress"])
def test_invalid_seed_draft_blocks_navigation_on_the_session_step(
    qtbot, monkeypatch, tmp_path, action,
):
    document, _first, _second = _document(tmp_path)
    document.update_randomization_settings(
        mode="fixed", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    home_calls = []
    wizard = SetupWizardPage(
        document, load_condition_template_profiles=lambda: [],
        manage_condition_templates=lambda: [], on_return_home=lambda: home_calls.append(True),
    )
    qtbot.addWidget(wizard)
    wizard.resize(1120, 820)
    wizard.show()
    wizard.open_wizard(step_key="session", allow_step_jumps=True)
    original = document.project.model_copy(deep=True)
    messages = record_setup_validation_dialogs(monkeypatch)
    editor = wizard.session_structure_editor.randomization_editor
    editor.seed_details_button.setChecked(True)
    editor.seed_edits["fixation_seed"].setText("-1")

    def unexpected_confirmation(*_args, **_kwargs):
        pytest.fail("Invalid seed drafts must block navigation before opening a confirmation")

    monkeypatch.setattr(
        "fpvs_studio.gui.setup_wizard_page.QMessageBox.question", unexpected_confirmation,
    )
    assert messages == []
    if action == "next":
        assert wizard.setup_wizard_next_button.isEnabled()
        qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    elif action == "progress":
        wizard._go_to_step_from_progress(wizard._step_index_for_key("experiment"))
    else:
        {"back": wizard._go_back, "home": wizard._return_home}[action]()
    QApplication.processEvents()
    assert wizard.step_stack.currentWidget() is wizard.session_step_surface
    assert editor.seed_details.isVisible()
    assert editor.error_label.isVisible()
    assert editor.seed_edits["fixation_seed"].text() == "-1"
    assert wizard.has_pending_edits()
    assert document.project == original
    assert not home_calls
    assert messages == (
        [("Complete this setup step", editor.error_label.text())] if action == "next" else []
    )

    editor.seed_edits["fixation_seed"].setText("44")
    assert wizard.flush_pending_edits()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
    assert document.project.settings.session.fixation_seed == 44
    assert not wizard.has_pending_edits()
