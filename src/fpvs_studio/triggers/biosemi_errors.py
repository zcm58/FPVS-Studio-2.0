"""BioSemi USB Trigger Interface recovery, without inferring device ownership."""

from __future__ import annotations

from fpvs_studio.triggers.serial_errors import serial_failure_reason

BIOSEMI_SERIAL_SUPPORT_MESSAGE = (
    "BioSemi trigger output cannot start because Studio serial support is unavailable. "
    "Repair or reinstall Studio, then try again."
)


def biosemi_port_error_message(port: str, error: BaseException | str) -> str:
    """Explain the observed access failure; callers retain native diagnostics."""

    if isinstance(error, ImportError) or "pyserial is required" in str(error).lower():
        return BIOSEMI_SERIAL_SUPPORT_MESSAGE
    reason = serial_failure_reason(error)
    if reason == "busy":
        return (
            f"BioSemi trigger port {port} is occupied or access was denied. Fully exit "
            f"serial test tools or other Studio instances using {port}, then retry. "
            "Stopping a test can leave the port occupied."
        )
    if reason == "missing":
        return (
            f"BioSemi trigger port {port} was not found. Reconnect the USB Trigger Interface "
            "and check its current COM number in Device Manager."
        )
    if reason == "configuration":
        return (
            f"BioSemi serial settings on {port} were rejected. The selected port or its "
            "settings may be incorrect. Check the USB Trigger Interface port and use "
            "115200 baud for the standard BioSemi interface."
        )
    if reason == "close":
        return (
            f"BioSemi trigger port {port} could not be closed. Windows may not have "
            "released it. Restart Studio before retrying."
        )
    if reason == "timeout":
        return (
            f"BioSemi trigger port {port} did not respond in time. The USB connection "
            "or driver may be unavailable. Reconnect the USB Trigger Interface, then retry."
        )
    if reason == "device_io":
        return (
            f"BioSemi USB communication on {port} failed. The USB connection may have "
            "been interrupted. Reconnect the USB Trigger Interface and check Device Manager."
        )
    return (
        f"BioSemi could not open trigger port {port}. The USB connection or driver may be "
        "unavailable. Reconnect the USB Trigger Interface and check its port in Device Manager."
    )


def biosemi_write_error_message(
    port: str, error: BaseException | str, *, reset: bool = False,
) -> str:
    """Keep sending/resetting failures distinct from connection discovery."""

    operation = "clearing the trigger signal" if reset else "sending a marker"
    if serial_failure_reason(error) == "timeout":
        problem = f"BioSemi timed out while {operation} on {port}."
    else:
        problem = f"BioSemi could not finish {operation} on {port}."
    return (
        f"{problem} The USB connection may have been interrupted. Reconnect the USB "
        "Trigger Interface and review any saved EEG markers before retrying."
    )
