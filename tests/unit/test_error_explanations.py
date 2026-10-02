"""Common error guidance follows the cause without inventing a diagnosis."""

import errno

import pytest

from fpvs_studio.support.error_explanations import explain_error


@pytest.mark.parametrize(
    "cause, expected",
    [
        (PermissionError(errno.EACCES, "denied"), "couldn't access"),
        (FileNotFoundError(errno.ENOENT, "missing"), "couldn't be found"),
        (OSError(errno.ENOSPC, "full"), "free space"),
        (TimeoutError("timeout"), "online service"),
        (ModuleNotFoundError("missing dependency"), "couldn't be loaded"),
    ],
)
def test_wrapped_import_error_uses_real_cause(cause, expected):
    error = ValueError("Unable to import project bundle: C:/private/study.fpvsbundle")
    error.__cause__ = cause
    explanation = explain_error("Import Error", str(error), error=error)
    assert expected in explanation.summary
    assert "private" not in explanation.description
    assert explanation.advice


@pytest.mark.parametrize(
    "details, expected",
    [
        ("PermissionError: [WinError 5] Access is denied", "couldn't access"),
        ("OSError: [WinError 32] file in use", "is in use"),
        ("OSError: [WinError 112] disk full", "free space"),
        ("BadZipFile: Bad CRC", "incomplete, damaged"),
        ("ImportError: DLL load failed", "couldn't be loaded"),
        ("ValidationError: 3 validation errors for ProjectFile", "aren't valid"),
    ],
)
def test_static_message_box_can_explain_technical_details(details, expected):
    explanation = explain_error("Error", "Unable to finish", details=details)
    assert expected in explanation.summary


def test_unknown_import_failure_is_honest_and_actionable():
    explanation = explain_error(
        "Import FPVS Studio Project Error", "Unable to import project bundle"
    )
    assert explanation.summary == "FPVS Studio couldn't import these files."
    assert "optional" in explanation.advice
    assert "permission" not in explanation.description


def test_existing_actionable_validation_message_is_preserved():
    explanation = explain_error("Project Name Required", "Enter a project name.")
    assert explanation.summary == "Enter a project name."


def test_chained_exception_cycle_is_bounded_and_suppressed_context_is_ignored():
    first = RuntimeError("Unable to import")
    second = RuntimeError("Unable to read")
    first.__cause__, second.__cause__ = second, first
    assert explain_error("Import Error", str(first), error=first).summary
    first.__cause__ = None
    first.__context__ = PermissionError(errno.EACCES, "denied")
    first.__suppress_context__ = True
    assert "access" not in explain_error("Import Error", str(first), error=first).summary
