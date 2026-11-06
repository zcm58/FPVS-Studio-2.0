"""Common error guidance follows the cause without inventing a diagnosis."""

import errno
from zipfile import BadZipFile

import pytest

from fpvs_studio.support.error_explanations import describe_error, explain_error


@pytest.mark.parametrize(
    "cause, expected",
    [
        (PermissionError(errno.EACCES, "denied"), "couldn't access"),
        (FileNotFoundError(errno.ENOENT, "missing"), "couldn't be found"),
        (OSError(errno.ENOSPC, "full"), "free space"),
        (TimeoutError("timeout"), "took too long"),
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


@pytest.mark.parametrize("message", [
    "KeyError: 'condition_id'",
    "'condition_id'",
    "'NoneType' object has no attribute 'name'",
    "Catalog failed: TypeError('expected str, got None')",
    "Unexpected result: {'status': 500, 'payload': None}",
    'Traceback (most recent call last):\n  File "private.py", line 12, in load',
    "Refresh failed: frames_per_stimulus=0",
    "Publisher returned b'error'",
    "A component failed: <Worker object at 0x123456>",
    "Expected one of ['base', 'oddball']",
    "Unexpected dimensions [640, 480]",
    "A setting failed: width=0",
    "not enough values to unpack (expected 2, got 1)",
    "'dict' object is not callable",
])
def test_unknown_technical_diagnostics_are_not_primary_text(message):
    explanation = explain_error("Import Error", message)
    assert explanation.summary == "FPVS Studio couldn't import these files."
    assert "Try again" in explanation.advice
    assert message not in explanation.description
    assert "report button" not in explanation.description


@pytest.mark.parametrize("message", [
    "Enter a project name.",
    "The pulse width must be between 1 and 1000 ms.",
    "Choose an output folder before exporting.",
    "The image must be at least 64 pixels wide. Choose a larger image and try again.",
])
def test_plain_validation_keeps_meaningful_labels_and_bounds(message):
    explanation = explain_error("Invalid Setting", message)
    assert explanation.summary == message
    assert "report button" not in explanation.description


def test_plain_recovery_does_not_include_appended_diagnostics():
    message = "Choose a larger image and try again. Details: {'width': 0}"
    explanation = explain_error("Image Error", message)
    assert explanation.summary == "Choose a larger image and try again."
    assert "width" not in explanation.description


@pytest.mark.parametrize("message,expected,action", [
    ("Display refresh check timed out after 20 seconds. The fullscreen probe was stopped.",
     "display", "Displays"),
    ("Another FPVS Studio process is updating this project's reports. "
     "The reporting lock wait timed out.", "reports", "Wait"),
    ("The local task timed out.", "took too long", "Try again"),
])
def test_local_timeouts_do_not_send_users_to_internet_settings(message, expected, action):
    error = TimeoutError(message)
    if "reports" in message:
        error.__cause__ = PermissionError(errno.EACCES, "Access is denied")
    explanation = explain_error("Launch Error", message, error=error)
    assert expected in explanation.summary
    assert action in explanation.advice
    assert "internet" not in explanation.description
    assert "file or folder" not in explanation.description


@pytest.mark.parametrize("message,expected,action", [
    ("URLError: [Errno 110] Connection timed out", "online service", "internet connection"),
    ("JSONDecodeError: Expecting value: line 1 column 1 (char 0)", "read the data", "fresh copy"),
    ("UnidentifiedImageError: cannot identify image file 'private/stimulus.png'",
     "stimulus image", "image viewer"),
    ("ValidationError: 1 validation error for ProjectFile\nsettings.rate\n"
     "Input should be greater than 0 [type=greater_than, input_value=0, input_type=int]",
     "aren't valid", "Setup"),
])
def test_common_technical_failures_have_plain_recovery(message, expected, action):
    explanation = explain_error("Import Error", message)
    assert expected in explanation.summary
    assert action in explanation.advice
    assert "Error:" not in explanation.description
    assert "private/" not in explanation.description
    assert "input_value" not in explanation.description


def test_describe_error_keeps_exception_cause_and_uses_label_safe_advice():
    error = RuntimeError("Publisher could not save output")
    error.__cause__ = PermissionError(errno.EACCES, "private/output.json")
    result = describe_error("Save Error", error)
    assert "file or folder" in result
    assert "private/" not in result
    assert "report button" not in result


@pytest.mark.parametrize("message", [
    "serial_enabled must be a boolean.",
    "brainproducts_sampling_rate_hz must be an integer or None.",
])
def test_recording_configuration_syntax_becomes_recording_settings_recovery(message):
    from fpvs_studio.runtime.recording import RecordingConfigurationError

    result = describe_error("Recording Setup", RecordingConfigurationError(message))
    assert "recording settings" in result
    assert "Settings > Recording" in result
    assert message not in result


def test_recording_configuration_keeps_plain_field_specific_bounds():
    from fpvs_studio.runtime.recording import RecordingConfigurationError

    message = "The pulse width must be between 1 and 1000 ms."
    result = describe_error("Recording Setup", RecordingConfigurationError(message))
    assert message in result
    assert "Settings > Recording" in result


def test_validation_help_url_does_not_turn_validation_into_network_failure():
    explanation = explain_error(
        "Open Error", "1 validation error for ProjectFile\nconditions.0.name\nField required\n"
        "For further information visit https://errors.pydantic.dev/latest/missing",
    )
    assert "aren't valid" in explanation.summary
    assert "Setup" in explanation.advice
    assert "internet" not in explanation.description


@pytest.mark.parametrize("name", [
    "SerialBackendError", "UnicornUDPBackendError", "ParallelPortError",
])
@pytest.mark.parametrize("form", ["cause_chain", "serialized"])
def test_device_connection_failures_do_not_claim_file_or_internet_problems(name, form):
    error = type(name, (RuntimeError,), {})("Unable to connect: {'port': 'COM4'}")
    error.__cause__ = PermissionError(errno.EACCES, "Access is denied")
    explanation = explain_error(
        "Launch Error", str(error) if form == "cause_chain" else f"{name}: {error}",
        error=error if form == "cause_chain" else None,
    )
    assert "Recording Setup" in explanation.advice
    assert "file or folder" not in explanation.description
    assert "internet" not in explanation.description
    assert "{'port'" not in explanation.description


def test_plain_recorder_readiness_keeps_its_specific_recovery_despite_low_level_cause():
    from fpvs_studio.runtime.unicorn_recorder import RecorderReadinessError

    message = "Unicorn Recorder did not respond to the recording check. Check Recorder, then retry."
    error = RecorderReadinessError(message)
    error.__cause__ = TimeoutError("timed out")
    result = describe_error("Launch Error", error)
    assert message in result
    assert "internet" not in result


@pytest.mark.parametrize("cause", [
    PermissionError(errno.EACCES, "Access is denied"),
    FileNotFoundError(errno.ENOENT, "Cannot find the file specified"),
    TimeoutError("The operation timed out"),
])
@pytest.mark.parametrize("operation", ["connect", "reset"])
def test_triggerbox_errors_take_precedence_over_file_and_network_guidance(cause, operation):
    from fpvs_studio.triggers.brainproducts_backend import BrainProductsTriggerBoxError

    hardware = BrainProductsTriggerBoxError(
        "TriggerBox could not connect on COM9. Check the USB cable and COM port in Settings > "
        "Recording. Close TriggerBox Configuration/Test IO before retrying."
        if operation == "connect" else
        "TriggerBox could not clear the trigger signal. Check any saved EEG markers."
    )
    hardware.__cause__ = cause
    error = RuntimeError("Trigger preflight failed before launch")
    error.__cause__ = hardware

    explanation = explain_error("Launch Error", str(error), error=error)

    assert "TriggerBox" in explanation.summary
    assert "folder" not in explanation.description
    assert "online service" not in explanation.description
    if operation == "connect":
        assert "connect" in explanation.summary
        assert "COM port in Settings > Recording" in explanation.advice
        assert "Configuration/Test IO" in explanation.advice
    else:
        assert "clear" in explanation.summary
        assert "saved EEG markers" in explanation.advice


@pytest.mark.parametrize("use_details", [False, True])
@pytest.mark.parametrize("message,expected,advice", [
    ("Trigger preflight failed before launch: Unable to open Brain Products TriggerBox "
     "on COM9: [WinError 5] Access is denied", "connect", "Configuration/Test IO"),
    ("The experiment aborted. Reason: Trigger output failed during condition playback: "
     "TriggerBox could not send a marker. Check any saved EEG markers before retrying. "
     "Details: The operation timed out", "send", "saved EEG"),
    ("Trigger output failed: Two triggers are too close together. Increase their spacing, or "
     "shorten the pulse only if it meets the amplifier minimum at the sampling rate. "
     "Details: TriggerBox pulse overlaps the previous event.",
     "too close together", "sampling rate"),
    ("TriggerBox cannot connect because its serial support is missing. Use Update & Repair "
     "before retrying. Details: pyserial "
     "is not installed.", "serial support", "Update & Repair"),
])
def test_serialized_triggerbox_failure_keeps_hardware_guidance(
    use_details, message, expected, advice,
):
    explanation = explain_error(
        "Launch Aborted", "The experiment aborted." if use_details else message,
        details=message if use_details else "",
    )

    assert expected in explanation.summary
    assert advice in explanation.advice
    assert "folder" not in explanation.description
    assert "online service" not in explanation.description


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("message", [
    "TriggerBox port COM9 could not be closed. Restart FPVS Studio before retrying.",
    "TriggerBox could not start its automatic trigger reset. Restart FPVS Studio before retrying.",
    "TriggerBox can no longer clear trigger signals automatically. Restart FPVS Studio and "
    "check any saved EEG markers before retrying.",
    "TriggerBox is not connected. Check the USB cable and selected port, then retry.",
    "Two triggers are too close together. Increase their spacing before retrying.",
])
def test_triggerbox_lifecycle_failure_preserves_plain_explanation(message, wrapped):
    prefix = "The experiment aborted. Reason: Trigger output failed: " if wrapped else ""
    explanation = explain_error(
        "Launch Aborted", f"{prefix}{message} Details: [WinError 5] Access is denied",
    )
    assert explanation.description.replace("\n\n", " ") == message
    assert "WinError" not in explanation.description


def test_mentioning_triggerbox_does_not_hide_unrelated_export_permission_failure():
    error = PermissionError(errno.EACCES, "Unable to export the TriggerBox session workbook")
    explanation = explain_error("Export Error", str(error), error=error)
    assert "file or folder" in explanation.summary


@pytest.mark.parametrize("form", ["cause_chain", "message", "details"])
@pytest.mark.parametrize("summary,advice,cause", [
    ("The COM4 port is occupied or access was denied.",
     "Please close the TriggerBox software (Configuration/Test IO) if it is open, then try again.",
     PermissionError(errno.EACCES, "Access is denied")),
    ("TriggerBox port COM4 is busy or access was denied.",
     "Close TriggerBox Configuration/Test IO, then retry Detect.",
     PermissionError(errno.EACCES, "Access is denied")),
    ("TriggerBox port COM4 was not found.",
     "Reconnect TriggerBox and confirm its COM port in Device Manager.",
     FileNotFoundError(errno.ENOENT, "Cannot find the file specified")),
    ("TriggerBox serial settings on COM4 were rejected.",
     "Confirm the TriggerBox COM port and vendor driver, then retry.",
     ValueError("Cannot configure port")),
    ("TriggerBox communication on COM4 failed.",
     "Reconnect TriggerBox and check the USB cable before retrying.",
     OSError("WriteFile failed")),
    ("TriggerBox port COM4 did not respond in time.",
     "Reconnect TriggerBox, then retry Detect.", TimeoutError("The operation timed out")),
    ("TriggerBox could not open COM4.",
     "Confirm the selected port and reconnect TriggerBox before retrying.",
     OSError("Unknown serial failure")),
    ("TriggerBox timed out while sending a marker.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     TimeoutError("Write timeout")),
    ("TriggerBox timed out while clearing the trigger signal.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     TimeoutError("Write timeout")),
    ("TriggerBox did not accept the full marker byte.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     OSError("serial write returned 0, expected 1")),
    ("TriggerBox did not accept the zero reset byte.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     OSError("serial write returned 0, expected 1")),
    ("TriggerBox did not finish sending the marker.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     OSError("serial write returned 0, expected 1")),
    ("TriggerBox did not finish clearing the trigger signal.",
     "Reconnect TriggerBox and check any saved EEG markers before retrying.",
     OSError("serial write returned 0, expected 1")),
    ("TriggerBox could not load its connection component.",
     "The Studio installation may be incomplete. Repair or reinstall FPVS Studio, then try again.",
     ModuleNotFoundError("No module named 'serial'")),
])
def test_specific_triggerbox_failure_preserves_summary_and_recovery(form, summary, advice, cause):
    from fpvs_studio.triggers.brainproducts_backend import BrainProductsTriggerBoxError

    hardware = BrainProductsTriggerBoxError(f"{summary} {advice} Details: {cause}")
    hardware.__cause__ = cause
    wrapper = RuntimeError("Trigger preflight failed before launch")
    wrapper.__cause__ = hardware
    serialized = f"Trigger preflight failed: BrainProductsTriggerBoxError: {hardware}"

    explanation = explain_error(
        "Launch Error", serialized if form == "message" else str(wrapper),
        error=wrapper if form == "cause_chain" else None,
        details=serialized if form == "details" else "",
    )

    assert explanation.summary == summary
    assert explanation.advice == advice
    assert "Details:" not in explanation.description
    assert "folder" not in explanation.description
    assert "online service" not in explanation.description


@pytest.mark.parametrize("form", ["cause_chain", "message", "details"])
@pytest.mark.parametrize("message", [
    "TriggerBox could not export the session workbook.",
    "TriggerBox could not open C:/exports/session.xlsx.",
])
def test_triggerbox_export_wording_keeps_file_permission_guidance(form, message):
    cause = PermissionError(errno.EACCES, "Access is denied")
    error = RuntimeError(message)
    error.__cause__ = cause
    serialized = f"{message} Details: PermissionError: [WinError 5] Access is denied"

    explanation = explain_error(
        "Export Error", serialized if form == "message" else "Unable to export",
        error=error if form == "cause_chain" else None,
        details=serialized if form == "details" else "",
    )

    assert "file or folder" in explanation.summary
    assert "TriggerBox" not in explanation.description


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


@pytest.mark.parametrize("error", [
    IndexError("list index out of range"), TypeError("'float' object is not iterable"),
    NameError("name 'widget' is not defined"), AssertionError("unexpected worker state"),
])
def test_unprefixed_programming_errors_do_not_pass_as_instructions(error):
    result = describe_error("Save Error", error)
    assert "couldn't save these changes" in result
    assert str(error) not in result


def test_custom_validation_retains_human_field_label_without_internal_path():
    from pydantic import ValidationError

    error = ValidationError.from_exception_data("DisplayConfig", [{
        "type": "value_error", "loc": ("text_height_values",), "input": [1, 1],
        "ctx": {"error": ValueError("Text height values must not contain duplicates.")},
    }])
    result = describe_error("Display Settings", error)
    assert "Text height values must not contain duplicates." in result
    assert "Correct this value" in result
    assert "text_height_values" not in result
    assert "input" not in result


def test_human_data_error_can_keep_a_real_filename():
    message = "session_condition_history.csv has an invalid hit count."
    result = describe_error("Results Error", ValueError(message))
    assert message in result


def test_online_context_does_not_override_a_local_file_cause():
    error = RuntimeError("Library download failed: https://example.invalid/catalog")
    error.__cause__ = PermissionError(errno.EACCES, "private/cache/file")
    result = describe_error("Experiment Library", error)
    assert "file or folder" in result
    assert "internet" not in result


def test_http_access_denial_does_not_claim_internet_connection_failure():
    result = describe_error("Library Access", "HTTP Error 403: Forbidden")
    assert "did not allow this action" in result
    assert "access may have expired" in result
    assert "internet connection" not in result


def test_mac_display_timeout_retains_the_real_settings_path():
    result = describe_error(
        "Display Error", "Display refresh check timed out after 20 seconds. "
        "Check macOS System Settings > Displays for a fixed refresh rate before retrying.",
    )
    assert "macOS System Settings > Displays" in result
    assert "internet" not in result


@pytest.mark.parametrize("title,action", [
    ("Update Download", "download the update"),
    ("Download Update", "download the update"),
    ("Update Install", "install the update"),
    ("Update Check", "check for updates"),
    ("Start Update & Repair", "start Update & Repair"),
    ("Project Update", "update this experiment"),
    ("Open Participant Results", "open participant results"),
])
def test_unknown_error_names_the_actual_action(title, action):
    result = explain_error(title, "Unknown failure: {'status': None}")
    assert result.summary == f"FPVS Studio couldn't {action}."


def test_formatting_an_already_explained_inline_error_does_not_repeat_advice():
    original = describe_error("Save Error", PermissionError(errno.EACCES, "Access is denied"))
    assert describe_error("Save Error", ValueError(original)) == original


@pytest.mark.parametrize("message", [
    "Installer SHA-256 did not match the selected GitHub asset.",
    "Installer checksum mismatch",
    "Downloaded installer size did not match the release asset.",
    "Installer content length did not match the release asset.",
    "Installer exceeded the release asset size.",
])
def test_update_integrity_failure_names_the_update_and_its_recovery(message):
    from fpvs_studio.updates.models import UpdateIntegrityError

    result = describe_error("Update Install", UpdateIntegrityError(message))
    assert "Studio update file" in result
    assert "Update & Repair" in result
    assert "experiment file" not in result
    assert "SHA-256" not in result


@pytest.mark.parametrize("message", [
    "The release has ambiguous patch metadata assets.",
    "Patch metadata SHA-256 or size did not match GitHub.",
    "The installed application no longer matches this patch. "
    "Check for updates again to select the full installer.",
])
@pytest.mark.parametrize("serialized", [False, True])
def test_update_verification_failure_does_not_claim_a_damaged_download(message, serialized):
    from fpvs_studio.updates.models import UpdateIntegrityError

    error = f"UpdateIntegrityError: {message}" if serialized else UpdateIntegrityError(message)
    result = describe_error("Update Check", error)
    assert result.startswith("Studio couldn't verify this update.")
    assert "Check for updates again in Update & Repair" in result
    assert "latest full installer" in result
    assert "update file is incomplete" not in result
    assert "Download the update again" not in result
    assert "SHA-256" not in result


def test_update_integrity_error_with_corrupt_archive_keeps_download_recovery():
    from fpvs_studio.updates.models import UpdateIntegrityError

    error = UpdateIntegrityError("The update could not be verified.")
    error.__cause__ = BadZipFile("Truncated file header")
    result = describe_error("Update Install", error)
    assert "Studio update file" in result
    assert "Download the update again" in result


@pytest.mark.parametrize("serialized", [False, True])
def test_library_upload_timeout_preserves_same_bundle_retry_instruction(serialized):
    from fpvs_studio.library.errors import LibraryError

    message = "The submission upload timed out. Retry the same prepared bundle."
    error = message if serialized else LibraryError(message)
    assert describe_error("Submit Experiment", error) == message


@pytest.mark.parametrize("serialized", [False, True])
def test_reporting_timeout_preserves_saved_draft_and_checks_status_before_retry(serialized):
    from fpvs_studio.support.client import ReportServiceError

    message = "The reporting request timed out. Your draft is preserved."
    result = describe_error("Report Error", message if serialized else ReportServiceError(message))
    assert message in result
    assert "Check the report's status" in result


def test_library_service_failure_explains_recovery_without_raw_status():
    from fpvs_studio.library.errors import LibraryError

    result = describe_error(
        "Experiment Library",
        LibraryError("The Library service could not complete the request (500)."),
    )
    assert "couldn't finish this request" in result
    assert "Wait a moment" in result
    assert "500" not in result


def test_missing_update_file_does_not_instruct_downloading_an_experiment():
    result = describe_error("Update Install", FileNotFoundError(errno.ENOENT, "missing"))
    assert "restore the missing file" in result
    assert "experiment" not in result


def test_serialized_github_update_timeout_has_network_recovery():
    result = describe_error("Update Check", "GitHub update check timed out.")
    assert "online service" in result
    assert "internet connection" in result


def test_parallel_platform_requirement_is_not_treated_as_driver_failure():
    from fpvs_studio.triggers.parallel_backend import ParallelPortError

    result = describe_error("Launch Error", ParallelPortError(
        "Native parallel-port output requires Windows.",
    ))
    assert "requires Windows" in result
    assert "Use a Windows computer" in result
    assert "driver may be unavailable" not in result
