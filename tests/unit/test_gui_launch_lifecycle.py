"""Execute launch continuation methods without constructing Qt objects."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest


def _bind_methods(instance, filename, owner, names, **namespace):
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui" / filename
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(node for node in parsed.body if isinstance(node, ast.ClassDef)
               and node.name == owner)
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef)
               and node.name in names]
    assert {node.name for node in methods} == set(names)
    for method in methods:
        method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    for name in names:
        setattr(instance, name, MethodType(namespace[name], instance))


@pytest.fixture
def wizard_steps():
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/setup_wizard_page.py"
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    declaration = next(node for node in parsed.body if isinstance(node, ast.AnnAssign)
                       and isinstance(node.target, ast.Name) and node.target.id == "_WIZARD_STEPS")
    return ast.literal_eval(declaration.value)


def test_setup_has_combined_display_and_session_after_timing(wizard_steps):
    assert wizard_steps == (
        ("project", "Project"), ("conditions", "Conditions"), ("experiment", "Timing"),
        ("session", "Display & Session"), ("image_size", "Image Size"),
        ("fixation", "Fixation"), ("response", "Response"), ("review", "Review"),
    )


@pytest.mark.parametrize("alias,index", [("experiment", 2), ("timing", 2), ("display", 3),
                                        ("runtime", 3), ("session", 3), ("display_session", 3)])
def test_setup_shortcuts_open_the_matching_timing_or_display_step(wizard_steps, alias, index):
    wizard = SimpleNamespace(_active_step_index=0, _step_jump_enabled=False, refresh=Mock(),
                             flush_pending_edits=Mock(return_value=True))
    wizard._select_step = lambda selected: setattr(wizard, "_active_step_index", selected)
    _bind_methods(
        wizard, "setup_wizard_page.py", "SetupWizardPage", ["_step_index_for_key", "open_wizard"],
        _WIZARD_STEPS=wizard_steps,
    )
    wizard.open_wizard(step_key=alias)
    assert wizard._active_step_index == index
    wizard.flush_pending_edits.assert_called_once_with(defer_timing=index == 3)


@pytest.mark.parametrize("start_index,deferred", [(2, True), (3, False)])
def test_next_keeps_timing_drafts_until_display_choices_are_accepted(
    wizard_steps, start_index, deferred,
):
    wizard = SimpleNamespace(
        _active_step_index=start_index, _next_navigation_busy=lambda: False,
        _document=SimpleNamespace(project=SimpleNamespace(settings=SimpleNamespace(
            display=SimpleNamespace(preferred_refresh_hz=60.0),
        ))),
        flush_pending_edits=Mock(return_value=True), _current_step_valid=lambda: True,
        refresh=Mock(),
    )
    wizard._select_step = lambda selected: setattr(wizard, "_active_step_index", selected)
    _bind_methods(
        wizard, "setup_wizard_page.py", "SetupWizardPage",
        ["_go_next", "_current_step_key", "_advance_to_next_step"], _WIZARD_STEPS=wizard_steps,
    )
    wizard._go_next()
    assert wizard._active_step_index == start_index + 1
    wizard.flush_pending_edits.assert_called_once_with(defer_timing=deferred)



def test_persisted_order_mismatch_does_not_block_timing_count_feasibility(multi_condition_project):
    from fpvs_studio.core.models import SessionSettings
    from fpvs_studio.core.session_ordering import (
        active_saved_condition_order,
        validate_condition_presentation_counts,
    )

    project = multi_condition_project
    project.settings.session = SessionSettings.model_validate({
        **project.settings.session.model_dump(), "randomization_mode": "fixed",
        "session_seed": 1, "stimulus_seed": 2, "fixation_seed": 3,
        "saved_condition_order": [item.condition_id for item in project.conditions] * 2,
    })
    project.conditions.pop()
    before = project.model_dump_json()
    table = SimpleNamespace(_document=SimpleNamespace(project=project))
    _bind_methods(
        table, "condition_timing_table.py", "ConditionTimingTable", ["presentation_count_blocker"],
        active_saved_condition_order=active_saved_condition_order,
        validate_condition_presentation_counts=validate_condition_presentation_counts,
    )
    assert table.presentation_count_blocker()
    assert table.presentation_count_blocker(include_saved_order=False) == ""
    assert project.model_dump_json() == before



@pytest.mark.parametrize("state", [
    "valid", "staged_counts", "persisted_mismatch",
    "invalid_duration", "invalid_counts", "inactive",
])
def test_saved_order_blocker_classifies_only_order_conflicts_without_mutation(
    multi_condition_project, state,
):
    from fpvs_studio.core.condition_timing import propose_condition_timing
    from fpvs_studio.core.models import SessionSettings
    from fpvs_studio.core.randomization import (
        effective_randomization_modes,
        supports_independent_randomization,
    )
    from fpvs_studio.core.session_ordering import (
        condition_presentation_counts,
        validate_saved_condition_order,
    )

    project = multi_condition_project
    project.settings.display.preferred_refresh_hz = 60.0
    project.settings.session = SessionSettings.model_validate({
        **project.settings.session.model_dump(), "randomization_mode": "fixed",
        "session_seed": 1, "stimulus_seed": 2, "fixation_seed": 3,
        "saved_condition_order": [item.condition_id for item in project.conditions] * 2,
    })
    first = project.conditions[0].condition_id
    durations, counts = {}, {}
    if state == "staged_counts":
        counts[first] = 3
    elif state == "persisted_mismatch":
        project.conditions.pop()
    elif state == "invalid_duration":
        durations[first] = 0.0
        counts[first] = 3
    elif state == "invalid_counts":
        counts[first] = 8
    elif state == "inactive":
        project.settings.session.randomization_mode = "new"
        project.conditions.pop()
    before = project.model_dump_json()
    table = SimpleNamespace(
        _document=SimpleNamespace(project=project), _shared_dirty=False,
        shared_frequency_spin=SimpleNamespace(value=lambda: 6.0),
        _overrides={}, _durations=durations, _presentation_counts=counts,
    )
    _bind_methods(
        table, "condition_timing_table.py", "ConditionTimingTable", ["saved_order_blocker"],
        propose_condition_timing=propose_condition_timing,
        supports_independent_randomization=supports_independent_randomization,
        effective_randomization_modes=effective_randomization_modes,
        condition_presentation_counts=condition_presentation_counts,
        validate_saved_condition_order=validate_saved_condition_order,
    )
    message = table.saved_order_blocker()
    assert bool(message) == (state in {"staged_counts", "persisted_mismatch"})
    if message:
        assert "Edit condition order" in message
        assert "Display & Session" in message
    assert project.model_dump_json() == before


def test_saved_order_validation_belongs_to_session_after_timing(wizard_steps):
    order_message = "Update the saved condition order in Display & Session."
    table = SimpleNamespace(
        presentation_count_blocker=Mock(return_value=""),
        saved_order_blocker=Mock(return_value=order_message),
    )
    wizard = SimpleNamespace(
        _active_step_index=3, condition_timing_table=table,
        runtime_settings_editor=SimpleNamespace(
            timing_is_compatible=lambda: True, timing_blocker=lambda: "",
        ),
    )
    _bind_methods(
        wizard, "setup_wizard_page.py", "SetupWizardPage",
        ["_step_valid", "_current_step_blocker"], _WIZARD_STEPS=wizard_steps,
    )
    assert wizard._step_valid(2)
    table.presentation_count_blocker.assert_called_once_with(include_saved_order=False)
    assert not wizard._step_valid(3)
    assert wizard._current_step_blocker() == order_message



@pytest.mark.parametrize("order_conflict,expected_index", [(True, 3), (False, 2)])
def test_failed_timing_flush_routes_order_repair_to_its_single_session_entry(
    order_conflict, expected_index,
):
    table = SimpleNamespace(
        apply_pending_edits=Mock(return_value=False),
        saved_order_blocker=Mock(return_value="Edit condition order" if order_conflict else ""),
    )
    wizard = SimpleNamespace(
        _active_step_index=3, _next_navigation_busy=lambda: False,
        condition_timing_table=table,
        session_structure_editor=SimpleNamespace(randomization_editor=SimpleNamespace(
            apply_pending_edits=lambda: True,
        )),
        _step_index_for_key=lambda key: {"session": 3, "experiment": 2}[key],
        refresh=Mock(),
    )
    _bind_methods(wizard, "setup_wizard_page.py", "SetupWizardPage", ["flush_pending_edits"])
    assert not wizard.flush_pending_edits()
    assert wizard._active_step_index == expected_index
    wizard.refresh.assert_called_once()


def test_display_check_worker_blocks_navigation_from_every_setup_step(wizard_steps):
    wizard = SimpleNamespace(
        _condition_image_task_active=lambda: False,
        runtime_settings_editor=SimpleNamespace(is_verifying_display=lambda: True),
    )
    _bind_methods(wizard, "setup_wizard_page.py", "SetupWizardPage", ["_next_navigation_busy"])
    for index in range(len(wizard_steps)):
        wizard._active_step_index = index
        assert wizard._next_navigation_busy()


@pytest.mark.parametrize("check_state", ["unchecked", "checked", "failed"])
@pytest.mark.parametrize("compatible", [True, False])
def test_optional_refresh_check_does_not_gate_timing_readiness(check_state, compatible):
    errors = [] if compatible else ["The selected base rate needs at least one display frame."]
    editor = SimpleNamespace(
        timing_report=lambda: SimpleNamespace(compatible=compatible, errors=errors),
        refresh_is_verified=lambda: check_state == "checked",
        _refresh_probe_task=None,
        _refresh_measurement_error="Measurement unavailable" if check_state == "failed" else None,
    )
    _bind_methods(
        editor, "runtime_settings_page.py", "DisplaySettingsEditor",
        ["timing_is_compatible", "timing_blocker"],
    )
    assert editor.timing_is_compatible() is compatible
    assert editor.timing_blocker() == ("" if compatible else errors[0])


def test_an_optional_refresh_check_in_progress_still_waits_for_worker_cleanup():
    editor = SimpleNamespace(
        timing_report=lambda: SimpleNamespace(compatible=True, errors=[]),
        _refresh_probe_task=object(),
    )
    _bind_methods(
        editor, "runtime_settings_page.py", "DisplaySettingsEditor", ["timing_blocker"],
    )
    assert editor.timing_blocker() == "Wait for display verification to finish"


@pytest.mark.parametrize("closed_at", ["before_completion", "before_dispatch", None])
@pytest.mark.parametrize("shutting_down", [False, True])
def test_deferred_seed_launch_does_not_resume_after_close_or_shutdown(
    closed_at, shutting_down,
):
    callbacks = []
    lifecycle = SimpleNamespace(is_shutting_down=False)
    window = SimpleNamespace(
        _session_seed_task=object(), _launch_after_session_seed_ready=True,
        isVisible=Mock(return_value=True), launch_session=Mock(),
    )
    _bind_methods(
        window, "main_window.py", "StudioMainWindow",
        ["_on_deferred_session_seed_finished", "_resume_deferred_launch"],
        QTimer=SimpleNamespace(singleShot=lambda _delay, callback: callbacks.append(callback)),
        update_lifecycle=lambda: lifecycle,
    )
    if closed_at == "before_completion":
        window.isVisible.return_value = False
    window._on_deferred_session_seed_finished()
    assert window._session_seed_task is None
    assert not window._launch_after_session_seed_ready
    if closed_at == "before_dispatch":
        window.isVisible.return_value = False
    lifecycle.is_shutting_down = shutting_down
    for callback in callbacks:
        callback()
    assert window.launch_session.call_count == int(closed_at is None and not shutting_down)


@pytest.mark.parametrize("session_number", [1, 2])
@pytest.mark.parametrize(
    "shutdown_at", ["before_completion", "during_finished", "during_dialog", None],
)
def test_participant_confirmation_does_not_continue_during_shutdown(session_number, shutdown_at):
    lifecycle = SimpleNamespace(is_shutting_down=shutdown_at == "before_completion")
    events = []
    dialogs = []

    def finished():
        events.append("finished")
        if shutdown_at == "during_finished":
            lifecycle.is_shutting_down = True

    def confirmation(*_args):
        dialogs.append("repeat")

        def execute():
            if shutdown_at == "during_dialog":
                lifecycle.is_shutting_down = True
            return 1

        return SimpleNamespace(exec=execute)

    check = SimpleNamespace(
        _session_number=session_number, _allow_repeated_sessions=True,
        _participant_number="0007", _parent_widget=object(),
        finished=SimpleNamespace(emit=finished),
        confirmed=SimpleNamespace(emit=lambda number: events.append(("confirmed", number))),
        deleteLater=Mock(),
    )
    _bind_methods(
        check, "run_page.py", "ParticipantSessionCheckTask", ["_on_finished"],
        update_lifecycle=lambda: lifecycle,
        ParticipantSessionConfirmationDialog=confirmation,
        QDialog=SimpleNamespace(DialogCode=SimpleNamespace(Accepted=1)),
    )
    check._on_finished()
    continued = shutdown_at is None or (shutdown_at == "during_dialog" and session_number == 1)
    assert events == (["finished", ("confirmed", session_number)] if continued
                      else ["finished"])
    assert dialogs == (["repeat"] if session_number > 1
                       and shutdown_at != "before_completion" else [])
    check.deleteLater.assert_called_once()


@pytest.mark.parametrize("shutting_down", [False, True])
def test_launch_cleanup_does_not_start_recovery_worker_during_shutdown(shutting_down):
    task_factory = Mock()
    controller = SimpleNamespace(
        _active=True, _window=SimpleNamespace(isVisible=lambda: True),
        _is_busy=lambda: False, _task=None, _ack_task=None, _project_root=Path("project"),
        _loaded=Mock(), _failed=Mock(), _finished=Mock(),
    )
    _bind_methods(
        controller, "condition_recovery_dialog.py", "ConditionRecoveryController",
        ["_available", "check"], BackgroundTask=task_factory,
        update_lifecycle=lambda: SimpleNamespace(is_shutting_down=shutting_down),
    )
    controller.check(automatic=True)
    assert task_factory.call_count == int(not shutting_down)
    if not shutting_down:
        task_factory.return_value.start.assert_called_once()
