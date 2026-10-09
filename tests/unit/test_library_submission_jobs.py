"""Exercise the actual upload coordinator without importing Qt or contacting services."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from tests.unit.test_data_sharing_gui_jobs import _Lifecycle, _Object, _Result, _Signal

from fpvs_studio import __version__
from fpvs_studio.developer.library_publisher import PublicationRequest, PublisherError
from fpvs_studio.library.errors import LibraryError


class Text:
    def __init__(self, value=""):
        self.value = value

    def text(self):
        return self.value

    toPlainText = text

    def setText(self, value):
        self.value = value

    setPlainText = setText

    def setToolTip(self, value):
        self.tooltip = value

    def setAccessibleDescription(self, value):
        self.accessible_description = value

    def clear(self):
        self.value = ""


class Rights:
    def __init__(self):
        self.checked = True

    def isChecked(self):
        return self.checked

    def setChecked(self, checked):
        self.checked = checked


class Dialog:
    def __init__(self):
        self.action_requested, self.closing = _Signal(), _Signal()
        self.title_edit = Text("Whole project")
        self.description = Text("Purpose")
        self.author_edit = Text("Researcher")
        self.email_edit = Text("researcher@example.test")
        self.review, self.history, self.status = Text(), Text(), Text()
        self.rights = Rights()
        self.states = []

    def set_state(self, *state):
        self.states.append(state)

    def show(self):
        pass

    raise_ = show
    activateWindow = show


@pytest.fixture
def state(tmp_path):
    lifecycle = _Lifecycle()
    prepared = SimpleNamespace(
        request=SimpleNamespace(item_id=f"submitted-{uuid4()}"),
        bundle_path=tmp_path / "project.fpvsbundle",
    )
    calls, saves = [], []

    def prepare(source, request, **kwargs):
        calls.append(("prepare", source, request, kwargs))
        return prepared

    def upload(client, value, **kwargs):
        calls.append(("upload", client, value, kwargs))
        return SimpleNamespace(
            status="pending", review_notes="", title="Whole project", submission_id="request"
        )

    path = (
        Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/library_submission_controller.py"
    )
    parsed = ast.parse(path.read_text(encoding="utf-8"))
    node = next(value for value in parsed.body if isinstance(value, ast.ClassDef))
    module = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            node,
        ],
        type_ignores=[],
    )
    namespace = {
        "QObject": _Object,
        "LibraryClient": lambda: object(),
        "PublisherService": lambda: SimpleNamespace(prepare=prepare),
        "LibrarySubmissionDialog": Dialog,
        "update_lifecycle": lambda _app: lifecycle,
        "UpdateTaskResult": _Result,
        "PreparedPublication": object,
        "SubmissionStatus": object,
        "cast": cast,
        "LibraryError": LibraryError,
        "PublisherError": PublisherError,
        "PublicationRequest": PublicationRequest,
        "uuid4": uuid4,
        "__version__": __version__,
        "submit_project": upload,
        "publication_review": lambda _prepared: "Inventory",
    }
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    controller = namespace["LibrarySubmissionController"](object())
    controller._source = tmp_path
    controller._save = lambda: saves.append("save") or True
    return SimpleNamespace(
        controller=controller,
        lifecycle=lifecycle,
        prepared=prepared,
        calls=calls,
        saves=saves,
        namespace=namespace,
    )


def test_one_click_prepares_all_conditions_then_uploads_without_reenabling_controls(state):
    c = state.controller
    c._action("submit")
    assert state.saves == ["save"]
    assert not state.calls  # No disk or HTTP work happens in the UI callback.
    state.lifecycle.jobs[0].run()
    assert "condition_id" not in state.calls[0][3]
    assert c._job is state.lifecycle.jobs[1]
    assert c.dialog.states[-1] == (True, True, True, False)
    state.lifecycle.jobs[1].run()
    assert state.calls[1][2] is state.prepared
    assert c.dialog.states[-1] == (False, True, True, True)
    assert "awaiting review" in c.dialog.status.text()


def test_failed_upload_retries_original_preparation_without_saving_or_reexporting(state):
    def fail(*_args, **_kwargs):
        raise LibraryError("Offline")

    state.namespace["submit_project"] = fail
    c = state.controller
    c._action("submit")
    state.lifecycle.jobs[0].run()
    state.lifecycle.jobs[1].run()
    assert c._prepared is state.prepared
    assert c.dialog.states[-1] == (False, True, True, False)
    assert c.dialog.status.text() == "Offline"
    retried = []
    state.namespace["submit_project"] = lambda _client, prepared, **_kwargs: retried.append(
        prepared
    )
    c._action("submit")
    state.lifecycle.jobs[2].callback(None, state.lifecycle.jobs[2].cancel_event)
    assert retried == [state.prepared]
    assert state.saves == ["save"]
    assert len(state.calls) == 1


def test_close_and_shutdown_cancel_active_worker_and_new_upload_resets_form(state):
    c = state.controller
    c._action("submit")
    c.dialog.closing.emit()
    assert state.lifecycle.jobs[0].cancel_event.is_set()
    c._job = None
    c._prepared, c._attempted, c._completed = state.prepared, True, True
    c._action("new")
    assert c.dialog.states[-1] == (False, False, False, False)
    assert c._identity is None
    assert not c.dialog.rights.isChecked()


def test_upload_requires_rights_and_failed_save_does_not_start_worker(state):
    c = state.controller
    c.dialog.rights.setChecked(False)
    c._action("submit")
    assert not state.lifecycle.jobs
    c.dialog.rights.setChecked(True)
    c._save = lambda: False
    c._action("submit")
    assert not state.lifecycle.jobs


def test_long_errors_keep_the_complete_message_accessible_without_overfilling_the_form(state):
    message = "C:/long project folder/" * 100
    state.controller._status(message)
    status = state.controller.dialog.status
    assert len(status.text()) == 238
    assert status.tooltip == status.accessible_description == message


def test_prefilled_long_title_is_not_changed_and_validation_precedes_preparation(state):
    controller = state.controller
    title = "An authored long project title " * 10
    controller.dialog.title_edit.setText(title)
    controller._action("submit")
    assert controller.dialog.title_edit.text() == title
    assert not state.lifecycle.jobs
    assert not state.saves
    assert controller.dialog.status.text()


@pytest.mark.parametrize("completed", [False, True])
def test_new_upload_after_project_switch_uses_current_project_and_preserves_old_request(
    state, completed,
):
    c = state.controller
    old_root = c._source
    c.show(project_root=old_root, title="Project A", description="A", save_project=lambda: False)
    c._prepared, c._attempted, c._completed = state.prepared, True, completed
    old_identity = ("Researcher A", "a@example.test")
    c._identity = old_identity
    new_root = old_root / "project-b"
    saves = []
    c.show(
        project_root=new_root, title="Project B", description="B",
        save_project=lambda: saves.append("B") or True,
    )
    assert c._prepared is state.prepared
    assert c._identity == old_identity
    assert c._source == old_root  # A retry still uses the original immutable request.
    c._action("new")
    assert c._retained_uploads[state.prepared.request.item_id] == (state.prepared, old_identity)
    assert c._source == new_root
    assert c.dialog.title_edit.text() == "Project B"
    assert c.dialog.description.toPlainText() == "B"
    assert not c.dialog.rights.isChecked()
    c._action("submit")
    assert not state.lifecycle.jobs
    c.dialog.rights.setChecked(True)
    c._action("submit")
    state.lifecycle.jobs[0].run()
    assert saves == ["B"]
    assert state.calls[0][1] == new_root
    assert state.calls[0][2].title == "Project B"


def test_project_switch_before_preparation_requires_fresh_sharing_confirmation(state):
    c = state.controller
    c.show(project_root=c._source, title="A", description="A", save_project=lambda: True)
    c.dialog.rights.setChecked(True)
    c.show(
        project_root=c._source / "project-b", title="B", description="B",
        save_project=lambda: True,
    )
    assert not c.dialog.rights.isChecked()
    c._action("submit")
    assert not state.lifecycle.jobs


def test_project_switch_during_cancelled_preparation_rebinds_when_worker_finishes(state):
    c = state.controller
    old_root = c._source
    c.show(project_root=old_root, title="A", description="A", save_project=lambda: True)
    c.dialog.rights.setChecked(True)
    c._action("submit")
    c.dialog.closing.emit()
    saves = []
    new_root = old_root / "project-b"
    c.show(
        project_root=new_root, title="B", description="B",
        save_project=lambda: saves.append("B") or True,
    )
    state.lifecycle.jobs[0].finished.emit(_Result(cancelled=True))
    assert c._source == new_root
    assert c.dialog.title_edit.text() == "B"
    assert not c.dialog.rights.isChecked()
    c.dialog.rights.setChecked(True)
    c._action("submit")
    assert saves == ["B"]
