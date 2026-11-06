"""BioSemi recovery distinguishes port access, device I/O and Studio dependencies."""

import errno

import pytest

from fpvs_studio.triggers.biosemi_errors import (
    BIOSEMI_SERIAL_SUPPORT_MESSAGE,
    biosemi_port_error_message,
    biosemi_write_error_message,
)


@pytest.mark.parametrize("error, summary, action", [
    (PermissionError(errno.EACCES, "Denied"), "is occupied or access was denied", "Fully exit"),
    ("[Errno 13] Permission denied", "is occupied or access was denied", "serial test tools"),
    ("[WinError 32] Sharing violation", "is occupied or access was denied", "other Studio"),
    (FileNotFoundError(2, "Absent"), "was not found", "current COM number"),
    ("FileNotFoundError(2, 'Absent', None, 2)", "was not found", "Device Manager"),
    (ValueError("Unsupported settings"), "settings on COM9 were rejected", "115200 baud"),
    ("Cannot configure port: invalid settings", "settings on COM9 were rejected", "115200 baud"),
    (TimeoutError("Stalled"), "did not respond in time", "Reconnect"),
    ("[WinError 1167] Disconnected", "USB communication on COM9 failed", "Device Manager"),
    ("Closing the port also failed: denied", "could not be closed", "Restart Studio"),
    (OSError("Unexpected error"), "could not open trigger port COM9", "USB Trigger Interface"),
])
def test_biosemi_access_recovery_names_observed_failure(error, summary, action):
    message = biosemi_port_error_message("COM9", error)
    assert message.startswith("BioSemi ")
    assert summary in message and action in message
    assert "TriggerBox" not in message and "BrainVision" not in message
    assert "ActiView" not in message and "USB Receiver" not in message
    assert "[WinError" not in message and "[Errno" not in message
    if "occupied" not in summary:
        assert "Stopping a test" not in message


@pytest.mark.parametrize("error", [ImportError("serial"), "pyserial is required to check ports."])
def test_missing_studio_serial_support_is_not_a_vendor_driver_claim(error):
    assert biosemi_port_error_message("COM3", error) == BIOSEMI_SERIAL_SUPPORT_MESSAGE
    assert "driver" not in BIOSEMI_SERIAL_SUPPORT_MESSAGE


@pytest.mark.parametrize("reset", [False, True])
@pytest.mark.parametrize("error, expected", [
    (TimeoutError("Stalled"), "timed out"),
    (OSError("[WinError 1117] I/O failed"), "could not finish"),
])
def test_write_recovery_preserves_operation_and_requires_marker_review(error, expected, reset):
    message = biosemi_write_error_message("COM4", error, reset=reset)
    assert expected in message and "COM4" in message
    assert ("clearing the trigger signal" if reset else "sending a marker") in message
    assert "review any saved EEG markers" in message
    assert "could not open" not in message and "TriggerBox" not in message
