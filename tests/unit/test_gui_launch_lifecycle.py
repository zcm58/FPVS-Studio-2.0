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
        _is_busy=lambda: False, _task=None, _project_root=Path("project"),
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
