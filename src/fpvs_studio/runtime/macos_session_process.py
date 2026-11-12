"""Private source-only macOS Test/Pilot process boundary for main-thread presentation."""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from math import isclose, isfinite
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

from fpvs_studio.core.enums import EngineName
from fpvs_studio.core.execution import ParticipantMetadata, SessionExecutionSummary
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.runtime.display_refresh import (
    PSYCHOPY_STABILITY_RELATIVE_TOLERANCE,
    DisplayRefreshVerification,
    DisplayRefreshVerificationError,
    _approved_refresh_for_native_mode,
)
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    _validate_launch_settings,
    _validate_macos_source_launch,
    _validate_participant_number,
)
from fpvs_studio.runtime.preflight import PreflightError

LOGGER = logging.getLogger("fpvs_studio.runtime.macos_session_process")
MAX_PAYLOAD_BYTES = 256 * 1024 * 1024
REFRESH_TIMEOUT_SECONDS = 20.0
_CHILD_MODULE = "fpvs_studio.runtime.macos_session_process"


class MacOSSessionProcessError(RuntimeError):
    """A source-session process could not return a validated execution result."""

    def __init__(self, message: str, *, child_traceback: Sequence[str] = ()) -> None:
        super().__init__(message)
        self.child_traceback = tuple(child_traceback)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    operation: Literal["session"] = "session"
    project_root: StrictStr
    session_plan: SessionPlan
    participant_number: StrictStr
    participant_session_number: StrictInt | None = Field(default=None, ge=1)
    participant_metadata: ParticipantMetadata
    launch_settings: dict[str, object]


class _RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    operation: Literal["refresh"] = "refresh"
    display_device_name: StrictStr | None = None

    @field_validator("display_device_name")
    @classmethod
    def _validate_display_identity(cls, value: str | None) -> str | None:
        if value is not None:
            from fpvs_studio.runtime.display_mode import DisplayModeError
            from fpvs_studio.runtime.macos_display import macos_display_id

            try:
                macos_display_id(value)
            except DisplayModeError as exc:
                raise ValueError("Invalid Mac presentation monitor identity.") from exc
        return value


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    summary: SessionExecutionSummary | None = None
    verification: DisplayRefreshVerification | None = None
    error: Literal[
        "invalid_request", "missing_dependency", "launch_failed", "display_verification",
        "preflight_failed",
    ] | None = None
    guidance: str = Field(default="", max_length=1000)
    child_traceback: list[Annotated[str, Field(max_length=280)]] = Field(
        default_factory=list, max_length=32,
    )


def _stack_locations(error: Exception) -> list[str]:
    """Keep useful stack locations without exception payloads, source text or locals."""
    return [
        f"{Path(frame.filename).name[:160]}:{frame.lineno} in {frame.name[:100]}"
        for frame in traceback.extract_tb(error.__traceback__)[-32:]
    ]


def _launch_failure(error: Exception) -> _Response:
    if isinstance(error, (DisplayRefreshVerificationError, PreflightError)):
        # These owners report display/compiled-asset validation, not participant metadata.
        return _Response(
            error="display_verification" if isinstance(error, DisplayRefreshVerificationError)
            else "preflight_failed",
            guidance=" ".join(str(error).split())[:1000], child_traceback=_stack_locations(error),
        )
    if isinstance(error, (ImportError, ModuleNotFoundError)):
        return _Response(error="missing_dependency", child_traceback=_stack_locations(error))
    if isinstance(error, RuntimeError) and str(error).startswith((
        "macOS display refresh callback", "Mac Test/Pilot requires the foreground-window",
        "PsychoPy could not determine the Mac presentation display size.",
        "Could not select the presentation monitor:", "Mac presentation display ",
    )):
        return _Response(
            error="display_verification", guidance=str(error)[:1000],
            child_traceback=_stack_locations(error),
        )
    if isinstance(error, RuntimeError) and str(error).startswith((
        "Mac presentation uses ", "PsychoPy could not confirm the Mac display's backing pixels.",
    )):
        return _Response(
            error="display_verification",
            guidance="The Mac backing pixels do not match this local test. Check the selected "
            "display and recheck its refresh rate and local calibration before restarting.",
            child_traceback=_stack_locations(error),
        )
    return _Response(error="launch_failed", child_traceback=_stack_locations(error))


def _settings(values: dict[str, object]) -> LaunchSettings:
    payload = dict(values)
    dimensions = payload.get("windowed_size_px")
    if isinstance(dimensions, list):
        payload["windowed_size_px"] = tuple(dimensions)
    try:
        settings = LaunchSettings(**payload)  # type: ignore[arg-type]
        _validate_launch_settings(settings)
        if settings.engine_name != EngineName.PSYCHOPY:
            raise ValueError("unsupported engine")
    except Exception:
        raise MacOSSessionProcessError("Invalid macOS source Test/Pilot launch settings.") from None
    return settings


def _require_source_macos() -> None:
    if sys.platform != "darwin" or getattr(sys, "frozen", False):
        raise MacOSSessionProcessError("This presentation boundary requires the macOS source app.")


def _private_owner(info: os.stat_result) -> bool:
    if os.name != "posix":
        return True
    get_uid = getattr(os, "getuid", None)
    return bool(get_uid is not None and info.st_uid == get_uid() and not info.st_mode & 0o077)


def _private_file(path: Path, *, write: bytes | None = None) -> bytes:
    if write is not None:
        if len(write) > MAX_PAYLOAD_BYTES:
            raise MacOSSessionProcessError("The macOS session payload exceeds its transfer limit.")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(write)
        return b""
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_PAYLOAD_BYTES:
            raise MacOSSessionProcessError("Invalid macOS session result file.")
        if not _private_owner(info):
            raise MacOSSessionProcessError("The macOS session file is not private.")
        value = stream.read(MAX_PAYLOAD_BYTES + 1)
        if len(value) > MAX_PAYLOAD_BYTES:
            raise MacOSSessionProcessError("The macOS session payload exceeds its transfer limit.")
        return value


def _request_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or path.name != "request.json":
        raise MacOSSessionProcessError("Invalid macOS session request location.")
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or path.parent.is_symlink():
        raise MacOSSessionProcessError("Invalid macOS session request directory.")
    if not _private_owner(info):
        raise MacOSSessionProcessError("The macOS session request directory is not private.")
    return path


def launch_macos_test_session(
    project_root: Path,
    session_plan: SessionPlan,
    *,
    participant_number: str,
    participant_session_number: int | None = None,
    participant_metadata: ParticipantMetadata | Mapping[str, object] | None = None,
    launch_settings: LaunchSettings | None = None,
) -> SessionExecutionSummary:
    """Wait in the GUI worker while the child process presents on its main thread.

    The existing launch lifecycle retains the worker until completion; participants
    use Escape in the presentation window to abort normally. No forced kill discards
    runtime finalization or acquired evidence.
    """
    _require_source_macos()
    try:
        settings = _settings(asdict(launch_settings or LaunchSettings()))
        metadata = ParticipantMetadata.model_validate(
            participant_metadata.model_dump()
            if isinstance(participant_metadata, ParticipantMetadata)
            else dict(participant_metadata or {}),
        )
        request = _Request(
            project_root=str(Path(project_root).resolve(strict=True)),
            session_plan=SessionPlan.model_validate_json(session_plan.model_dump_json()),
            participant_number=_validate_participant_number(participant_number),
            participant_session_number=participant_session_number,
            participant_metadata=metadata, launch_settings=asdict(settings),
        )
    except Exception:
        raise MacOSSessionProcessError("Invalid macOS source Test/Pilot session request.") from None
    response = _exchange(request)
    if response.summary is None or response.verification is not None:
        raise MacOSSessionProcessError("The macOS test session returned an invalid result.")
    summary = response.summary
    if (summary.project_id != request.session_plan.project_id
            or summary.session_id != request.session_plan.session_id
            or summary.participant_number != request.participant_number
            or request.participant_session_number is not None
            and summary.participant_session_number != request.participant_session_number):
        raise MacOSSessionProcessError("The macOS test session returned a mismatched result.")
    return summary


def verify_macos_primary_display_refresh(
    *, cancel_event: threading.Event | None = None, display_device_name: str | None = None,
) -> DisplayRefreshVerification:
    """Measure the chosen display on a child main thread with bounded cancellation."""
    _require_source_macos()
    try:
        request = _RefreshRequest(display_device_name=display_device_name)
    except ValueError as exc:
        raise MacOSSessionProcessError("Select a valid Mac presentation monitor.") from exc
    response = _exchange(request, cancel_event=cancel_event)
    result = response.verification
    if (result is None or response.summary is not None
            or not isfinite(result.psychopy_measured_hz) or result.psychopy_measured_hz <= 0
            or result.approved_hz != _approved_refresh_for_native_mode(result.display_mode)
            or result.display_mode.variable_refresh_enabled
            or not isclose(result.display_mode.hz, result.psychopy_measured_hz,
                           rel_tol=PSYCHOPY_STABILITY_RELATIVE_TOLERANCE, abs_tol=0.0)):
        raise MacOSSessionProcessError("The macOS refresh check returned an invalid result.")
    if display_device_name is not None and result.display_mode.display_device_name != (
        display_device_name
    ):
        raise MacOSSessionProcessError(
            "The macOS refresh check returned a different display. Select the monitor again."
        )
    return result


def _run_refresh_child(
    command: list[str], environment: dict[str, str], cancel_event: threading.Event | None,
) -> int:
    """Bound imports, display capture, flips and cleanup; never kill a session process."""
    if cancel_event is not None and cancel_event.is_set():
        raise MacOSSessionProcessError("Display refresh check canceled.")
    deadline = time.monotonic() + REFRESH_TIMEOUT_SECONDS
    child = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, env=environment,
    )
    LOGGER.info("Mac display refresh probe started (pid=%d)", child.pid)
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise MacOSSessionProcessError("Display refresh check canceled.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MacOSSessionProcessError(
                    "Display refresh check timed out after 20 seconds. The fullscreen probe "
                    "was stopped. Check macOS System Settings > Displays for a fixed refresh "
                    "rate before retrying. No refresh rate was verified."
                )
            try:
                return child.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
            LOGGER.warning("Stopped unresponsive or canceled Mac refresh probe (pid=%d)", child.pid)


def _exchange(
    request: _Request | _RefreshRequest, *, cancel_event: threading.Event | None = None,
) -> _Response:
    with tempfile.TemporaryDirectory(prefix="fpvs-macos-session-") as directory:
        folder = Path(directory)
        os.chmod(folder, 0o700)
        request_path = folder / "request.json"
        _private_file(
            request_path,
            write=request.model_dump_json(exclude_none=isinstance(request, _RefreshRequest)).encode(
                "utf-8",
            ),
        )
        environment = os.environ.copy()
        source_root = str(Path(__file__).resolve().parents[2])
        environment["PYTHONPATH"] = os.pathsep.join(
            item for item in (source_root, environment.get("PYTHONPATH", "")) if item
        )
        try:
            command = [sys.executable, "-m", _CHILD_MODULE, str(request_path)]
            if isinstance(request, _RefreshRequest):
                returncode = _run_refresh_child(command, environment, cancel_event)
                if cancel_event is not None and cancel_event.is_set():
                    raise MacOSSessionProcessError("Display refresh check canceled.")
            else:
                process = subprocess.run(
                    command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, env=environment, check=False,
                )
                returncode = process.returncode
            response = _Response.model_validate_json(_private_file(folder / "response.json"))
        except MacOSSessionProcessError:
            raise
        except Exception:
            raise MacOSSessionProcessError(
                "The macOS test session did not return a result. Check saved project output "
                "before retrying."
            ) from None
        if (returncode != 0 or response.error is not None
                or (response.summary is None and response.verification is None)):
            message = ("The macOS source environment is missing a presentation dependency."
                       if response.error == "missing_dependency" else
                       "The macOS test session failed. Check the source environment and "
                       "saved project output before retrying.")
            LOGGER.error("macOS presentation child failed (%s); stack locations: %s",
                         response.error or "child_exit", " | ".join(response.child_traceback))
            raise MacOSSessionProcessError(
                response.guidance or message, child_traceback=response.child_traceback,
            )
        return response


def main(argv: Sequence[str] | None = None) -> int:
    """Fixed child entry point: parse one private request and launch on the main thread."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        _require_source_macos()
        if threading.current_thread() is not threading.main_thread() or len(arguments) != 1:
            raise ValueError("invalid child context")
        path = _request_path(arguments[0])
    except Exception:
        return 2
    request: _Request | _RefreshRequest
    try:
        payload = json.loads(_private_file(path))
        if not isinstance(payload, dict):
            raise ValueError("invalid request")
        if payload.get("operation") == "refresh":
            request = _RefreshRequest.model_validate(payload)
            settings = None
            root = None
        else:
            request = _Request.model_validate(payload)
            settings = _settings(request.launch_settings)
            _validate_macos_source_launch(settings, require_main_thread=True)
            root = Path(request.project_root).resolve(strict=True)
            if not root.is_dir():
                raise ValueError("missing project")
            _validate_participant_number(request.participant_number)
    except Exception as error:
        response = _Response(error="invalid_request", child_traceback=_stack_locations(error))
    else:
        try:
            LOGGER.info("Mac presentation child started (operation=%s pid=%d)",
                        request.operation, os.getpid())
            if isinstance(request, _RefreshRequest):
                from fpvs_studio.engines.registry import create_engine
                from fpvs_studio.runtime.display_refresh import (
                    _verify_primary_display_refresh_in_process,
                )

                verification = _verify_primary_display_refresh_in_process(
                    create_engine(EngineName.PSYCHOPY),
                    runtime_options={
                        "fullscreen": True, "display_index": None,
                        **({"display_device_name": request.display_device_name}
                           if request.display_device_name is not None else {}),
                    },
                )
                response = _Response(verification=verification)
            else:
                from fpvs_studio.runtime.launcher import launch_session

                assert root is not None and settings is not None
                summary = launch_session(
                    root, request.session_plan, participant_number=request.participant_number,
                    participant_session_number=request.participant_session_number,
                    participant_metadata=request.participant_metadata, launch_settings=settings,
                )
                response = _Response(summary=summary)
        except Exception as error:
            response = _launch_failure(error)
            LOGGER.error("Mac presentation child failed (%s); stack locations: %s",
                         response.error, " | ".join(response.child_traceback))
        else:
            LOGGER.info("Mac presentation child completed (operation=%s)", request.operation)
    try:
        _private_file(
            path.parent / "response.json", write=response.model_dump_json().encode("utf-8"),
        )
    except Exception:
        return 2
    return 0 if response.error is None else 1


def _main_with_diagnostics() -> int:
    # Reuse bounded, redacted local support logs without creating an automatic
    # crash-report session for each disposable child. No participant payloads.
    from fpvs_studio.support.diagnostics import DiagnosticLogging
    from fpvs_studio.support.storage import support_directory

    diagnostics = DiagnosticLogging(support_directory())
    diagnostics.start()
    try:
        return main()
    finally:
        diagnostics.close()


if __name__ == "__main__":
    raise SystemExit(_main_with_diagnostics())
