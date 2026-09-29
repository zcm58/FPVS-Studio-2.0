"""Resolve local recording choices without changing portable experiment contracts."""

from __future__ import annotations

from collections.abc import Mapping

from fpvs_studio.core.execution import RecordingSnapshot
from fpvs_studio.triggers.serial_backend import resolve_serial_port

UNICORN_VALIDATION_NOTE = (
    "Unicorn marker output is enabled for recording tests. "
    "Full receiver and physical timing validation remain pending."
)


class RecordingConfigurationError(ValueError):
    """The requested local recording configuration cannot be used."""


def resolve_recording_backend(options: Mapping[str, object] | None = None) -> str:
    """Return the effective transport, preserving the legacy serial default."""

    values = options or {}
    selected = values.get("recording_backend")
    if selected not in (None, "serial", "unicorn_udp"):
        raise RecordingConfigurationError(
            "Unknown recording backend. Open Settings > Recording and choose BioSemi "
            "serial or Unicorn Recorder UDP."
        )
    for key in ("experiment_test_mode", "pilot_mode"):
        if not isinstance(values.get(key, False), bool):
            raise RecordingConfigurationError(f"{key} must be a boolean.")
    if values.get("experiment_test_mode", False) or values.get("pilot_mode", False):
        return "null"
    return "unicorn_udp" if selected == "unicorn_udp" else "serial"


def validate_recording_configuration(options: Mapping[str, object] | None = None) -> str:
    """Validate configuration without claiming receiver or acquisition readiness."""

    values = options or {}
    effective = resolve_recording_backend(values)
    if not isinstance(values.get("serial_enabled", True), bool):
        raise RecordingConfigurationError("serial_enabled must be a boolean.")
    if (effective == "serial" and values.get("recording_backend") is None
            and not values.get("serial_enabled", True)):
        raise RecordingConfigurationError(
            "Serial trigger output is required for recording. Null output is only allowed "
            "in Experiment Test Mode or Pilot Study Mode."
        )
    if values.get("recording_backend") == "unicorn_udp":
        port = values.get("unicorn_udp_port", 1000)
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise RecordingConfigurationError(
                "Unicorn UDP port must be an integer from 1 to 65535."
            )
    if not isinstance(values.get("recording_operator_confirmed", False), bool):
        raise RecordingConfigurationError("recording_operator_confirmed must be a boolean.")
    for key in ("recording_association", "recorder_version"):
        value = values.get(key)
        if value is not None and (
            not isinstance(value, str) or not value.strip() or len(value) > 256
        ):
            raise RecordingConfigurationError(
                f"{key} must be nonblank text of at most 256 characters."
            )
    return effective


def validate_production_recording(options: Mapping[str, object] | None = None) -> str:
    """Validate normal recording output without blocking receiver validation runs.

    Recorder readiness is checked by the shared launcher before presentation. This
    validation also protects direct backend construction, but does not claim receiver
    or physical timing qualification. Test/Pilot still resolve to null output.
    """

    return validate_recording_configuration(options)


def recording_backend_label(options: Mapping[str, object] | None = None) -> str:
    """Describe the effective launch transport for operator-facing readiness text."""

    effective = resolve_recording_backend(options)
    if effective == "null":
        return "No marker output (Test/Pilot)"
    if effective == "unicorn_udp":
        return f"Unicorn Recorder UDP — 127.0.0.1:{(options or {}).get('unicorn_udp_port', 1000)}"
    if "serial_port" in (options or {}):
        return f"BioSemi serial — {resolve_serial_port((options or {}).get('serial_port'))}"
    return "BioSemi serial"


def recording_snapshot(options: Mapping[str, object] | None = None) -> RecordingSnapshot:
    """Capture the effective configuration; confirmation stays explicitly human."""

    values = options or {}
    effective = validate_recording_configuration(values)
    selected = values.get("recording_backend") or "serial"
    serial_port = values.get("serial_port")
    return RecordingSnapshot.model_validate({
        "selected_backend": selected,
        "effective_backend": effective,
        "selection_source": (
            "legacy_project" if values.get("recording_backend") is None else "local_settings"
        ),
        "udp_host": "127.0.0.1" if selected == "unicorn_udp" else None,
        "udp_port": values.get("unicorn_udp_port", 1000) if selected == "unicorn_udp" else None,
        "serial_port": (
            resolve_serial_port(serial_port)
            if effective == "serial" else None
        ),
        "serial_baudrate": values.get("serial_baudrate", 115200) if effective == "serial" else None,
        "operator_confirmed_raw_bdf_recording": (
            bool(values.get("recording_operator_confirmed", False))
            if effective == "unicorn_udp" else False
        ),
        "recording_association": values.get("recording_association"),
        "recorder_version": values.get("recorder_version"),
        "receiver_validation": "pending" if selected == "unicorn_udp" else "not_applicable",
    })
