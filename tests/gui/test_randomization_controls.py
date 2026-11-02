"""Registered participant reuse choices, launch lifecycle and compact layout coverage."""

from __future__ import annotations

from itertools import product

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
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


def test_legacy_choices_do_not_rewrite_source_and_can_be_changed_independently(qtbot, tmp_path):
    document, _first, _second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    expected = configured_randomization_seeds(original)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    assert document.project == original
    assert set(editor.mode_combos) == {"stimulus", "condition_order", "fixation"}
    assert all(combo.currentData() == "new" for combo in editor.mode_combos.values())
    for domain in editor.mode_combos:
        combo = editor.mode_combos[domain]
        combo.setCurrentIndex(combo.findData("fixed"))
        choices = document.project.settings.session.randomization_modes
        assert getattr(choices, domain) == "fixed"
        assert configured_randomization_seeds(document.project) == expected
        assert "Every participant receives the same" in combo.toolTip()
        assert combo.accessibleDescription() == combo.toolTip()
        assert editor.heading_labels[domain].buddy() is combo
        assert editor.heading_labels[domain].property("sectionCardRole") == "title"
    assert document.project.settings.session.randomization_mode == "fixed"
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.session.randomization_modes == choices
    assert configured_randomization_seeds(reopened.project) == expected



@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
@pytest.mark.parametrize("reuse_mode", ["fixed", "new"])
@pytest.mark.parametrize("count_mode", ["fixed", "randomized"])
def test_fixation_count_choices_preserve_participant_timing_policy(
    qtbot, tmp_path, background, reuse_mode, count_mode,
):
    document, _first, _second = _document(tmp_path)
    document.update_randomization_settings(modes={"fixation": reuse_mode})
    document.update_fixation_settings(
        target_count_mode=count_mode, changes_per_sequence=2,
        target_count_min=2, target_count_max=3, no_immediate_repeat_count=False,
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
    QApplication.processEvents()
    randomization = wizard.session_structure_editor.randomization_editor
    heading = randomization.heading_labels["fixation"]
    assert heading.text() == "Fixation cross color change timing"
    assert heading.width() >= heading.fontMetrics().horizontalAdvance(heading.text())
    assert randomization.mode_combos["fixation"].accessibleName() == heading.text()
    session_before = document.project.settings.session.model_copy(deep=True)
    seeds_before = configured_randomization_seeds(document.project)

    wizard.open_wizard(step_key="fixation", allow_step_jumps=True)
    QApplication.processEvents()
    editor = wizard.fixation_schedule_editor
    combo = editor.target_count_mode_combo
    label = editor.fixation_behavior_layout.labelForField(combo)
    assert label.text() == "Number of color changes"
    assert combo.itemText(combo.findData("fixed")) == "Same number per condition"
    assert combo.itemText(combo.findData("randomized")) == "Vary within a range"
    assert "Display & Session" in combo.toolTip()
    assert combo.accessibleDescription() == combo.toolTip()
    assert "2000 ms" in editor.min_gap_spin.toolTip()
    assert "before the first change" in editor.min_gap_spin.toolTip()
    assert combo.currentData() == count_mode
    assert combo.isEnabled()
    other_count_mode = "randomized" if count_mode == "fixed" else "fixed"
    combo.setCurrentIndex(combo.findData(other_count_mode))
    editor.target_duration_spin.setValue(editor.target_duration_spin.value() + 10)
    QApplication.processEvents()
    assert document.project.settings.fixation_task.target_count_mode == other_count_mode
    assert document.project.settings.session == session_before
    assert configured_randomization_seeds(document.project) == seeds_before
    assert editor.changes_per_sequence_spin.isEnabled() == (other_count_mode == "fixed")
    assert editor.target_count_min_spin.isEnabled() == (other_count_mode == "randomized")
    assert_visible_children_within_parent(wizard.fixation_step_surface)
    assert combo.width() >= combo.fontMetrics().horizontalAdvance(combo.currentText()) + 32
    assert label.width() >= label.fontMetrics().horizontalAdvance(label.text())

    wizard.open_wizard(step_key="session", allow_step_jumps=True)
    QApplication.processEvents()
    assert randomization.mode_combos["fixation"].currentData() == reuse_mode
    assert_visible_children_within_parent(wizard.display_session_step_surface)
    document.save()
    reopened = ProjectDocument.open_existing(document.project_root)
    assert reopened.project.settings.fixation_task.target_count_mode == other_count_mode
    assert reopened.project.settings.session == session_before
    assert configured_randomization_seeds(reopened.project) == seeds_before


def test_failed_policy_edit_retains_draft_and_can_be_retried(qtbot, monkeypatch, tmp_path):
    document, _first, _second = _document(tmp_path)
    original = document.project.model_copy(deep=True)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    update = document.update_randomization_settings

    def fail(**_kwargs):
        raise DocumentError("Could not apply the change. Try again.")

    monkeypatch.setattr(document, "update_randomization_settings", fail)
    combo = editor.mode_combos["fixation"]
    combo.setCurrentIndex(combo.findData("fixed"))
    assert editor.error_label.isVisible()
    assert editor.has_pending_edits()
    assert document.project == original
    monkeypatch.setattr(document, "update_randomization_settings", update)
    assert editor.apply_pending_edits()
    assert document.project.settings.session.randomization_modes.fixation == "fixed"
    assert not editor.has_pending_edits()


@pytest.mark.parametrize("choices", list(product(("fixed", "new"), repeat=3)))
def test_participant_retry_reuses_mixed_snapshot_and_policy_edits_invalidate_it(
    qtbot, monkeypatch, tmp_path, choices,
):
    document, _first, _second = _word_document(tmp_path)
    document.update_randomization_settings(
        mode="new", condition_order_seed=22, stimulus_seed=11, fixation_seed=33,
    )
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    modes = dict(zip(("stimulus", "condition_order", "fixation"), choices, strict=True))
    for domain, mode in modes.items():
        combo = editor.mode_combos[domain]
        combo.setCurrentIndex(combo.findData(mode))
    generated = iter((_seeds(101, 102, 103), _seeds(201, 202, 203), _seeds(301, 302, 303)))
    monkeypatch.setattr(
        "fpvs_studio.gui.document.generate_randomization_seeds", lambda: next(generated),
    )
    first = document.prepare_participant_randomization("0001", 1)
    assert document.prepare_participant_randomization("0001", 1) == first
    document.finish_participant_randomization()
    second = document.prepare_participant_randomization("0002", 1)
    for domain, field in (("condition_order", "condition_order_seed"),
                          ("stimulus", "stimulus_seed"), ("fixation", "fixation_seed")):
        assert (getattr(first, field) == getattr(second, field)) == (modes[domain] == "fixed")
    combo = editor.mode_combos["fixation"]
    combo.setCurrentIndex(combo.findData("new" if modes["fixation"] == "fixed" else "fixed"))
    assert document.resolved_randomization_status()[0] is None


def test_legacy_out_of_range_patterns_have_an_explicit_repair_action(qtbot, monkeypatch, tmp_path):
    document, _first, _second = _document(tmp_path)
    document.update_session_settings(session_seed=2**40)
    original = document.project.model_copy(deep=True)
    editor = RandomizationEditor(document)
    qtbot.addWidget(editor)
    editor.show()
    assert not editor.apply_pending_edits()
    assert document.project == original
    assert editor.reset_patterns_button.isVisible()
    monkeypatch.setattr("fpvs_studio.gui.document.generate_randomization_seeds", lambda: _seeds())
    editor.reset_patterns_button.click()
    assert configured_randomization_seeds(document.project) == _seeds()
    assert editor.apply_pending_edits()
    assert not editor.error_label.isVisible()
    assert not editor.reset_patterns_button.isVisible()


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
    assert document.resolved_randomization_status() == (pending, "Pending launch")
    assert configured_randomization_seeds(document.project) == _seeds()
    assert document.project == original
    document.finish_participant_randomization()
    assert document.resolved_randomization_status() == (pending, "Last launch")
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
@pytest.mark.parametrize(
    "state", ["fixed", "new", "mixed", "invalid", "saved", "inactive", "combined_errors"],
)
def test_plain_language_choices_fit_session_and_review(
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
    if state == "mixed":
        document.update_randomization_settings(modes={
            "stimulus": "fixed", "condition_order": "new", "fixation": "fixed",
        })
    elif state in {"saved", "inactive"}:
        document.update_condition_timing(saved_condition_order=[first, second, first, second])
        if state == "inactive":
            document.update_randomization_settings(mode="new")
    elif state in {"invalid", "combined_errors"}:
        document.update_randomization_settings(mode="new")
        document.project.settings.session.randomization_mode = None
        document.project.settings.session.stimulus_seed = None
        document.project.settings.session.fixation_seed = None
        document.project.settings.session.session_seed = 2**40
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda _self: None)
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
    if state == "combined_errors":
        wizard.runtime_settings_editor._on_refresh_detection_failed(RuntimeError(
            "The display's configured refresh rate could not be confirmed because stable "
            "fullscreen frame delivery was unavailable on the selected monitor."
        ))
    QApplication.processEvents()
    assert wizard.size().toTuple() == (1120, 820)
    assert wizard.step_stack.currentWidget() is wizard.display_session_step_surface
    assert editor.isVisible()
    assert not wizard.condition_timing_table.isVisible()
    assert wizard.runtime_settings_editor.isVisible()
    assert wizard.display_settings_card.title_label.isVisible()
    assert wizard.session_settings_card.title_label.isVisible()
    assert (wizard.display_settings_card.geometry().right()
            < wizard.session_settings_card.geometry().left())
    assert wizard.session_structure_editor.presentation_total_label.text() == "4 total"
    assert_visible_children_within_parent(wizard.display_session_step_surface)
    for domain, combo in editor.mode_combos.items():
        assert combo.width() >= combo.fontMetrics().horizontalAdvance(combo.currentText()) + 32
        assert combo.accessibleName()
        heading = editor.heading_labels[domain]
        assert heading.font().weight() > combo.font().weight()
        assert (wizard.session_settings_card.title_label.fontMetrics().height()
                > heading.fontMetrics().height())
        assert heading.geometry().bottom() < combo.geometry().top()
        assert combo.toolTip() == combo.accessibleDescription()
    assert editor.saved_order_status_label.isVisible() == (state in {"saved", "inactive"})
    if state not in {"saved", "inactive", "invalid", "combined_errors"}:
        assert [label for label in editor.findChildren(QLabel) if label.isVisible()] == list(
            editor.heading_labels.values()
        )
    for label in [*editor.findChildren(QLabel),
                  *wizard.runtime_settings_editor.findChildren(QLabel)]:
        if label.isVisible() and label.text():
            assert label.height() >= label.heightForWidth(label.width()) if label.wordWrap() else (
                label.width() >= label.fontMetrics().horizontalAdvance(label.text())
            )
    for button in (editor.condition_order_button, editor.clear_saved_order_button,
                   editor.reset_patterns_button):
        if button.isVisible():
            assert button.width() >= button.sizeHint().width()
    assert not editor.findChildren(QLineEdit)
    refresh_button = wizard.runtime_settings_editor.detect_refresh_button
    assert refresh_button.width() >= refresh_button.sizeHint().width()
    if state not in {"invalid", "combined_errors"}:
        wizard.open_wizard(step_key="review", allow_step_jumps=True)
        QApplication.processEvents()
        assert_visible_children_within_parent(wizard.review_step_surface)
        text = " ".join(label.text() for label in wizard.review_card.findChildren(QLabel))
        for title in ("Image / word order:", "Condition order:",
                      "Fixation cross color change timing:"):
            assert title in text
        assert "seed" not in text.lower()


@pytest.mark.parametrize("action", ["next", "back", "home", "progress"])
def test_failed_choice_draft_blocks_navigation_until_retry(
    qtbot, monkeypatch, tmp_path, action,
):
    document, _first, _second = _document(tmp_path)
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
    update = document.update_randomization_settings

    def fail(**_kwargs):
        raise DocumentError("Could not apply the change. Try again.")

    monkeypatch.setattr(document, "update_randomization_settings", fail)
    combo = editor.mode_combos["fixation"]
    combo.setCurrentIndex(combo.findData("fixed"))
    if action == "next":
        qtbot.mouseClick(wizard.setup_wizard_next_button, Qt.MouseButton.LeftButton)
    elif action == "progress":
        wizard._go_to_step_from_progress(wizard._step_index_for_key("experiment"))
    else:
        {"back": wizard._go_back, "home": wizard._return_home}[action]()
    QApplication.processEvents()
    assert wizard.step_stack.currentWidget() is wizard.display_session_step_surface
    assert editor.error_label.isVisible()
    assert combo.currentData() == "fixed"
    assert wizard.has_pending_edits()
    assert document.project == original
    assert not home_calls
    assert messages == (
        [("Complete this setup step", editor.error_label.text())] if action == "next" else []
    )
    monkeypatch.setattr(document, "update_randomization_settings", update)
    assert wizard.flush_pending_edits()
    wizard.open_wizard(step_key="experiment", allow_step_jumps=True)
    assert wizard.step_stack.currentWidget() is wizard.experiment_step_surface
    assert document.project.settings.session.randomization_modes.fixation == "fixed"
    assert not wizard.has_pending_edits()
