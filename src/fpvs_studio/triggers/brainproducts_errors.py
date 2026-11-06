"""Concise TriggerBox recovery based on observed serial failures, not guessed owners."""

from __future__ import annotations

from fpvs_studio.triggers.serial_errors import serial_failure_reason as triggerbox_failure_reason


def triggerbox_port_error_message(port: str, error: BaseException | str) -> str:
    """Return actionable display text; callers retain raw diagnostics separately."""

    reason = triggerbox_failure_reason(error)
    if reason == "close":
        return (
            f"TriggerBox port {port} could not be closed. Windows may not have released it. "
            "Restart Studio before retrying."
        )
    if reason == "busy":
        return (
            f"The {port} port is occupied or access was denied. Fully exit the TriggerBox "
            f"software (Configuration/Test IO) and other apps using {port}, then try again. "
            "Pressing Stop can leave the port occupied."
        )
    if reason == "missing":
        return (
            f"TriggerBox port {port} was not found. It may be unplugged or need its driver. "
            "Reconnect USB; check Device Manager and install its driver if needed."
        )
    if reason == "configuration":
        return (
            f"TriggerBox serial settings on {port} were rejected. The port or driver may be "
            "incorrect. Check the selected port and repair the TriggerBox driver if needed."
        )
    if reason == "timeout":
        return (
            f"TriggerBox port {port} did not respond in time. The USB connection may be "
            "unavailable. Reconnect the USB cable, then try again."
        )
    if reason == "device_io":
        return (
            f"TriggerBox communication on {port} failed. The USB connection may have been "
            "interrupted. Reconnect the USB cable, then try again."
        )
    return (
        f"TriggerBox could not open {port}. The USB connection or driver may be unavailable. "
        "Reconnect USB and check its port in Device Manager."
    )
