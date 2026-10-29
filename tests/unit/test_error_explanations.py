"""Common error guidance follows the cause without inventing a diagnosis."""

import errno
from zipfile import BadZipFile

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


@pytest.mark.parametrize("wrapped", [False, True])
def test_bad_zip_exception_uses_download_guidance_without_traceback_details(wrapped):
    cause = BadZipFile("Truncated file header")
    error = RuntimeError("Unable to import project bundle") if wrapped else cause
    if wrapped:
        error.__cause__ = cause

    explanation = explain_error("Import Error", "Unable to import project bundle", error=error)

    assert "incomplete, damaged" in explanation.summary
    assert "Download a fresh copy" in explanation.advice


def test_unsupported_project_config_schema_uses_update_guidance():
    error = ValueError(
        "Unsupported project config schema version: '99.0.0'. "
        "Expected a supported version from 1.2.0 through 1.8.0."
    )

    explanation = explain_error("Import Error", "Unable to import project config", error=error)

    assert "format this version of FPVS Studio can't read" in explanation.summary
    assert "latest Studio update" in explanation.advice


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


@pytest.mark.parametrize("wrapped", [False, True])
def test_parallel_driver_failure_prompts_for_external_driver_setup(wrapped):
    from fpvs_studio.triggers.parallel_backend import ParallelPortDriverUnavailableError

    unavailable = ParallelPortDriverUnavailableError("Driver device unavailable")
    # Driver availability takes precedence over generic file/permission guidance.
    unavailable.__cause__ = PermissionError(errno.EACCES, "Access is denied")
    error = RuntimeError("Trigger preflight failed before launch") if wrapped else unavailable
    if wrapped:
        error.__cause__ = unavailable

    explanation = explain_error("Launch Error", str(error), error=error)

    assert explanation.summary == "FPVS Studio couldn't access the parallel-port driver."
    assert "parallel-port interface" in explanation.advice
    assert "compatible InpOut driver are installed and running" in explanation.advice
    assert "Close any other app" in explanation.advice
    assert "Studio does not install drivers." in explanation.advice
    assert "folder" not in explanation.description


def test_serialized_parallel_driver_failure_keeps_setup_prompt():
    explanation = explain_error(
        "Launch Error", "Trigger preflight failed before launch",
        details=(
            "An already installed, running InpOut driver is required for native LPT output "
            "(Windows error 2)."
        ),
    )

    assert "parallel-port driver" in explanation.summary
    assert "installed and running" in explanation.advice


@pytest.mark.parametrize("message", [
    "Unable to open Brain Products TriggerBox on COM3: Access is denied",
    "Confirm the configured serial port is available",
    "Native parallel-port output requires Windows.",
    "Unable to send trigger code 55 at LPT address 0x0378: port write failed",
])
def test_other_recording_failures_do_not_prompt_for_parallel_drivers(message):
    explanation = explain_error("Launch Error", message)

    assert "InpOut" not in explanation.advice
    assert "installed and running" not in explanation.advice


def test_chained_exception_cycle_is_bounded_and_suppressed_context_is_ignored():
    first = RuntimeError("Unable to import")
    second = RuntimeError("Unable to read")
    first.__cause__, second.__cause__ = second, first
    assert explain_error("Import Error", str(first), error=first).summary
    first.__cause__ = None
    first.__context__ = PermissionError(errno.EACCES, "denied")
    first.__suppress_context__ = True
    assert "access" not in explain_error("Import Error", str(first), error=first).summary
