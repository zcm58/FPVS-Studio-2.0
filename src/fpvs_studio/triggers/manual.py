"""One-shot hardware output for an operator's Trigger Tester keypress."""

from __future__ import annotations

from fpvs_studio.triggers.base import TriggerBackend
from fpvs_studio.triggers.serial_backend import SerialBackend


def send_test_trigger(backend: TriggerBackend, code: int) -> None:
    """Send a digit and release the hardware on the calling worker."""

    if type(code) is not int or not 0 <= code <= 9:
        raise ValueError("Test trigger code must be an integer from 0 to 9.")
    if not backend.emits_hardware_triggers:
        raise ValueError("Choose a hardware output for the test trigger.")

    try:
        backend.connect()
        if code:
            backend.send_trigger(code)
        elif isinstance(backend, SerialBackend):
            backend.write_idle()
        else:
            backend.reset()
        backend.finish_pending_output()
    except BaseException as error:
        try:
            backend.close()
        except Exception as close_error:
            if close_error is not error:
                raise RuntimeError(
                    f"{error} Details: Closing trigger output also failed: {close_error}"
                ) from error
        raise
    else:
        backend.close()
