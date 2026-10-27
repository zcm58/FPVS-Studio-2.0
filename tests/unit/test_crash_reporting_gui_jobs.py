"""Exercise crash coordinator completion with real method code and no Qt import."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from fpvs_studio.support.client import ReportCancelled, ReportServiceError

_LOGGER_NAME = "fpvs_studio.gui.crash_report_controller"
_PRIVATE_MESSAGE = "private-response-body synthetic-secret-token participant=private-person"


@pytest.fixture
def completion():
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/crash_report_controller.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    controller = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "CrashReportController"
    )
    method = next(
        node for node in controller.body
        if isinstance(node, ast.FunctionDef) and node.name == "_done"
    )
    method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        method,
    ], type_ignores=[])
    namespace = {
        "ReportCancelled": ReportCancelled,
        "ReportServiceError": ReportServiceError,
        "_LOGGER": logging.getLogger(_LOGGER_NAME),
    }
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    notifications, retries, preference_failures, uploads = [], [], [], []
    value = SimpleNamespace(
        _stage="sync", _job=object(), busy=True, enabled=True,
        _lifecycle=SimpleNamespace(is_shutting_down=False),
        _job_revision=0, _preference_revision=0,
        _retry=SimpleNamespace(start=lambda: retries.append(True)),
        _notify=notifications.append,
        _preference_failed=lambda: preference_failures.append(True),
        _upload=lambda: uploads.append(True),
    )
    return SimpleNamespace(
        done=lambda result: namespace["_done"](value, result),
        value=value, notifications=notifications, retries=retries,
        preference_failures=preference_failures, uploads=uploads,
    )


@pytest.mark.parametrize("stage", ["load", "sync"])
@pytest.mark.parametrize("error,status", [
    (ReportServiceError(_PRIVATE_MESSAGE, status=401), 401),
    (ReportServiceError(_PRIVATE_MESSAGE, status=429), 429),
    (ReportServiceError(_PRIVATE_MESSAGE, status=503), 503),
    (OSError(_PRIVATE_MESSAGE), None),
])
def test_failure_log_preserves_only_operation_type_and_status(
    completion, caplog, stage, error, status,
):
    completion.value._stage = stage
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        completion.done(SimpleNamespace(error=error, cancelled=False))

    record, = caplog.records
    assert record.levelno == logging.WARNING
    assert f"operation={stage}" in record.getMessage()
    assert f"error_type={type(error).__name__}" in record.getMessage()
    assert f"http_status={status}" in record.getMessage()
    assert record.exc_info is None
    for private in ("private-response-body", "synthetic-secret-token", "private-person"):
        assert private not in caplog.text
        assert private not in repr(record.__dict__)
    assert completion.value._job is None and not completion.value.busy
    assert completion.preference_failures == ([True] if stage == "load" else [])
    assert completion.retries == ([] if stage == "load" else [True])


@pytest.mark.parametrize("error,cancelled", [
    (None, True), (ReportCancelled(_PRIVATE_MESSAGE), False),
])
def test_expected_cancellation_is_quiet_and_preserves_retry_state(
    completion, caplog, error, cancelled,
):
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        completion.done(SimpleNamespace(error=error, cancelled=cancelled))

    record, = caplog.records
    assert record.levelno == logging.INFO
    assert "canceled (operation=sync)" in record.getMessage()
    assert "synthetic-secret-token" not in caplog.text
    assert completion.retries == [True]
    assert "Delivery is unavailable" in completion.notifications[-1]


@pytest.mark.parametrize("state", ["shutdown", "stale"])
def test_irrelevant_completion_remains_silent(completion, caplog, state):
    if state == "shutdown":
        completion.value._lifecycle.is_shutting_down = True
    else:
        completion.value._preference_revision = 1
    with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
        completion.done(SimpleNamespace(
            error=ReportServiceError(_PRIVATE_MESSAGE), cancelled=False,
        ))
    assert caplog.records == []
    assert completion.notifications == []
    assert completion.retries == []
    assert completion.uploads == ([True] if state == "stale" else [])
