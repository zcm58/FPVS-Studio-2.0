"""Standard-library-only, opt-out reporting for bounded maintenance workflows.

This module can be loaded by filename when Studio's dependencies cannot import.
Only explicitly named facts are accepted; logs, paths and exception text have no
place in the automatic payload. Manual reporting remains a separate workflow.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import stat
import sys
import time
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from http.client import HTTPException
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

SERVICE_ORIGIN = "https://reports.zack-murphy.com"
MAX_REPORT_BYTES = 16 * 1024
MAX_RECORD_BYTES = 32 * 1024
MAX_RECORDS = 10
MAX_AGE_SECONDS = 7 * 86400
Transport = Callable[[str, str, bytes | None, dict[str, str]], bytes]
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_RECORD_NAME = re.compile(r"workflow-([0-9a-f-]{36})\.json\Z")
_SUMMARIES = {
    "success": "Workflow completed successfully.",
    "failure": "Workflow did not complete.",
    "action_required": "Workflow requires user action.",
}
_FAILURES = frozenset({
    "none", "scipy_macho", "missing_dependency", "dependency_mismatch", "python_incompatible",
    "setup_failed",
    "engine_import_failed", "ide_configuration_failed", "cancelled", "unknown",
})
_VERSION_FIELDS = frozenset({
    "python_version", "initial_studio_version", "final_studio_version", "initial_scipy_version",
    "final_scipy_version", "psychopy_version", "helper_version", "numpy_version", "pyside6_version",
})
_CHECK_FIELDS = frozenset({
    "dependency_check", "engine_import", "environment_rebuild", "pycharm_configuration",
})
_DETAIL_FIELDS = _VERSION_FIELDS | _CHECK_FIELDS | {
    "cpu", "python_cpu", "rosetta", "failure_code", "initial_failure_code", "check_only",
    "elapsed_seconds", "macos_build",
}


class WorkflowReportError(Exception):
    """Safe reporting failure: never include a response body or credential."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _uuid(value: Any) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def validate_report(report: Mapping[str, Any]) -> None:
    """Reject unknown fields rather than attempting to redact arbitrary content."""
    if set(report) != {
        "schema_version", "kind", "workflow", "report_id", "created_at", "app_version",
        "os_version", "outcome", "summary", "details",
    }:
        raise ValueError("The workflow report has unexpected fields.")
    if (report["schema_version"] != "1" or report["kind"] != "workflow"
            or report["workflow"] != "macos_repair" or not _uuid(report["report_id"])):
        raise ValueError("The workflow report identity is invalid.")
    outcome = report["outcome"]
    if (not isinstance(outcome, str) or outcome not in _SUMMARIES
            or report["summary"] != _SUMMARIES[outcome]):
        raise ValueError("The workflow report outcome is invalid.")
    stamp = report["created_at"]
    if not isinstance(stamp, str) or len(stamp) > 40:
        raise ValueError("The workflow report timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        raise ValueError("The workflow report timestamp is invalid.") from None
    if not isinstance(report["app_version"], str) or not _VERSION.fullmatch(report["app_version"]):
        raise ValueError("The workflow application version is invalid.")
    os_version = report["os_version"]
    if not isinstance(os_version, str) or not re.fullmatch(
        r"(?:[0-9]{1,4}(?:\.[0-9]{1,4}){0,3}|unknown)", os_version,
    ) or len(os_version) > 64:
        raise ValueError("The workflow OS version is invalid.")
    details = report["details"]
    if not isinstance(details, dict) or set(details) - _DETAIL_FIELDS:
        raise ValueError("The workflow details contain unsupported fields.")
    for name, value in details.items():
        valid = False
        if name in _VERSION_FIELDS:
            valid = isinstance(value, str) and bool(_VERSION.fullmatch(value))
        elif name in _CHECK_FIELDS:
            valid = value in ("passed", "failed", "skipped", "action_required", "unknown")
        elif name in ("cpu", "python_cpu"):
            valid = value in ("arm64", "x86_64", "unknown")
        elif name == "rosetta":
            valid = value in ("native", "translated", "unknown")
        elif name in ("failure_code", "initial_failure_code"):
            valid = isinstance(value, str) and value in _FAILURES
        elif name == "check_only":
            valid = isinstance(value, bool)
        elif name == "elapsed_seconds":
            valid = (type(value) in (int, float) and math.isfinite(value)
                     and 0 <= value <= 86400)
        elif name == "macos_build":
            valid = isinstance(value, str) and bool(re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9.]{0,31}", value,
            ))
        if not valid:
            raise ValueError(f"The workflow detail {name} is invalid.")
    if len(_bytes(report)) > MAX_REPORT_BYTES - 256:
        raise ValueError("The workflow report exceeds its size limit.")


def build_report(
    *, workflow: str, outcome: str, app_version: str, os_version: str,
    details: Mapping[str, Any], report_id: str | None = None, created_at: str | None = None,
) -> dict[str, Any]:
    report = {
        "schema_version": "1", "kind": "workflow", "workflow": workflow,
        "report_id": report_id if report_id is not None else str(uuid4()),
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "app_version": app_version, "os_version": os_version, "outcome": outcome,
        "summary": _SUMMARIES.get(outcome, ""), "details": dict(details),
    }
    validate_report(report)
    return report


def render_report(report: Mapping[str, Any]) -> str:
    """Render one compact screenful; keep wire names out of user-facing copy."""
    validate_report(report)
    detail = report["details"]
    outcome = {
        "success": "Completed", "failure": "Incomplete", "action_required": "Action needed",
    }[report["outcome"]]
    cpu_names = {"arm64": "Apple Silicon", "x86_64": "Intel", "unknown": "unknown"}
    failures = {
        "none": "none", "scipy_macho": "SciPy's compiled library is incompatible with macOS.",
        "missing_dependency": "A required dependency is missing.",
        "dependency_mismatch": "Installed package versions do not match this Studio source.",
        "python_incompatible": "The selected Python version or CPU architecture is unsupported.",
        "setup_failed": "Environment setup did not complete.",
        "engine_import_failed": "The presentation engine could not load its dependencies.",
        "ide_configuration_failed": "PyCharm configuration did not complete.",
        "cancelled": "Repair was canceled.", "unknown": "The cause is not yet classified.",
    }
    lines = [f"FPVS Studio Mac repair: {outcome}", f"Studio source: {report['app_version']}"]
    for label, initial, final in (
        ("Installed Studio", "initial_studio_version", "final_studio_version"),
        ("SciPy", "initial_scipy_version", "final_scipy_version"),
    ):
        before, after = detail.get(initial), detail.get(final)
        if before or after:
            value = (
                f"{before} → {after}" if before and after and before != after else after or before
            )
            lines.append(f"{label}: {value}")
    build = f" (build {detail['macos_build']})" if "macos_build" in detail else ""
    lines.append(f"macOS: {report['os_version']}{build}")
    if "cpu" in detail:
        lines.append(f"Mac processor: {cpu_names[detail['cpu']]}")
    if "python_version" in detail or "python_cpu" in detail or "rosetta" in detail:
        python = [str(detail.get("python_version", "unknown"))]
        if "python_cpu" in detail:
            python.append(cpu_names[detail["python_cpu"]])
        if detail.get("rosetta") == "translated":
            python.append("running through Rosetta")
        elif detail.get("rosetta") == "native":
            python.append("native")
        lines.append("Python: " + ", ".join(python))
    versions = [
        f"{label} {detail[field]}" for field, label in (
            ("psychopy_version", "PsychoPy"), ("numpy_version", "NumPy"),
            ("pyside6_version", "PySide6"),
        ) if field in detail
    ]
    if versions:
        lines.append("; ".join(versions))
    for field, label in (
        ("dependency_check", "Dependency check"), ("engine_import", "Presentation engine"),
        ("environment_rebuild", "Environment rebuild"),
        ("pycharm_configuration", "PyCharm configuration"),
    ):
        if field in detail:
            state = str(detail[field]).replace("_", " ")
            lines.append(f"{label}: {state}")
    initial = detail.get("initial_failure_code", "none")
    final = detail.get("failure_code", "none")
    if initial != "none" and initial != final:
        lines.append(f"Original problem: {failures[initial]}")
    if final != "none":
        lines.append(f"Remaining problem: {failures[final]}")
    run = []
    if "check_only" in detail:
        run.append("Check only" if detail["check_only"] else "Repair")
    if "elapsed_seconds" in detail:
        run.append(f"{detail['elapsed_seconds']:g} seconds")
    if "helper_version" in detail:
        run.append(f"helper {detail['helper_version']}")
    if run:
        lines.append("; ".join(run))
    lines.extend((f"Created: {report['created_at']}", f"Report: {report['report_id']}"))
    return "\n".join(lines) + "\n"


def support_directory() -> Path:
    """Match support.storage without importing its optional application dependencies."""
    if sys.platform == "win32":
        value = os.environ.get("LOCALAPPDATA")
        if not value or not Path(value).is_absolute():
            raise OSError("Windows local application-data storage is unavailable.")
        return Path(value) / "FPVS Studio" / "support"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FPVS Studio" / "support"
    value = os.environ.get("XDG_STATE_HOME")
    if value and not Path(value).is_absolute():
        raise OSError("XDG_STATE_HOME must be an absolute directory.")
    return (Path(value) if value else Path.home() / ".local" / "state") / "fpvs-studio/support"


def _ordinary(path: Path, *, directory: bool = False) -> None:
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise OSError("Automatic reporting storage cannot contain links or special files.")


def _folder(root: Path, name: str) -> Path:
    for path in (root, root / name):
        if path.exists() or path.is_symlink():
            _ordinary(path, directory=True)
        else:
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
            _ordinary(path, directory=True)
    return root / name


def _read(path: Path) -> dict[str, Any]:
    _ordinary(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_RECORD_BYTES + 1)
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("Automatic reporting storage exceeds its size limit.")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Automatic reporting storage has an invalid record.")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        _ordinary(path)
    data = _bytes(value)
    if len(data) > MAX_RECORD_BYTES:
        raise ValueError("Automatic reporting storage exceeds its size limit.")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str,
    ) -> None:
        return None


def http_transport(method: str, url: str, data: bytes | None, headers: dict[str, str]) -> bytes:
    request = Request(url, data=data, method=method, headers={
        "User-Agent": "FPVS-Studio/1.0", "Accept-Encoding": "identity", **headers,
    })
    started = time.monotonic()
    try:
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            if (response.headers.get_content_type() != "application/json"
                    or response.headers.get("Content-Encoding", "identity") != "identity"):
                raise WorkflowReportError("The reporting service returned an unexpected response.")
            result = bytearray()
            while True:
                chunk = response.read1(min(4096, MAX_REPORT_BYTES + 1 - len(result)))
                if time.monotonic() - started > 30:
                    raise WorkflowReportError("The reporting request timed out.")
                if not chunk:
                    break
                result.extend(chunk)
                if len(result) > MAX_REPORT_BYTES:
                    raise WorkflowReportError("The reporting response exceeded its size limit.")
    except HTTPError as error:
        status = error.code
        error.close()
        raise WorkflowReportError("The reporting service did not accept the request.",
                                  status=status) from None
    except (URLError, TimeoutError, OSError, HTTPException):
        raise WorkflowReportError("The reporting service could not be reached.") from None
    return bytes(result)


class WorkflowReporter:
    """Persistent exact-payload retries sharing Studio's automatic-report opt-out."""

    def __init__(
        self, root: Path | None = None, *, origin: str | None = None,
        transport: Transport = http_transport,
    ) -> None:
        self.root = root if root is not None else support_directory()
        self.origin = (os.environ.get("FPVS_REPORT_SERVICE_URL", SERVICE_ORIGIN).strip()
                       if origin is None else origin)
        if self.origin not in ("", SERVICE_ORIGIN):
            raise ValueError("The reporting endpoint must be the approved HTTPS origin.")
        self.transport = transport

    def _preference(self) -> tuple[bool, str]:
        """Read the GUI-owned preference without creating or changing it."""
        _folder(self.root, "automatic-workflows")
        folder = self.root / "automatic-crashes"
        if not folder.exists() and not folder.is_symlink():
            return True, "default"
        _ordinary(folder, directory=True)
        path = folder / "consent.json"
        if not path.exists() and not path.is_symlink():
            return True, "default"
        preference = _read(path)
        generation = preference.get("workflow_generation", preference.get("installation_id"))
        if type(preference.get("enabled")) is not bool or not _uuid(generation):
            raise ValueError("The saved automatic-report preference is invalid.")
        return preference["enabled"], str(generation)

    def _state_path(self) -> Path:
        return _folder(self.root, "automatic-workflows") / "installation.json"

    def _state(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.exists() and not path.is_symlink():
            return {"current": None, "retired": []}
        state = _read(path)
        if (set(state) != {"current", "retired"} or not isinstance(state["retired"], list)
                or state["current"] is not None and not isinstance(state["current"], dict)
                or len(state["retired"]) > MAX_RECORDS):
            raise ValueError("The workflow installation record is invalid.")
        capabilities = state["retired"] + ([state["current"]] if state["current"] else [])
        for capability in capabilities:
            if (not isinstance(capability, dict)
                    or set(capability) != {"installation_id", "token", "generation"}
                    or not _uuid(capability["installation_id"])
                    or not isinstance(capability["token"], str)
                    or not _TOKEN.fullmatch(capability["token"])
                    or capability["generation"] != "default"
                    and not _uuid(capability["generation"])):
                raise ValueError("The workflow installation capability is invalid.")
        return state

    def _enabled(self, installation_id: str | None = None) -> dict[str, Any] | None:
        enabled, generation = self._preference()
        state = self._state()
        current = state["current"]
        changed = False
        if current is not None and (not enabled or current["generation"] != generation):
            if len(state["retired"]) >= MAX_RECORDS:
                raise ValueError("Workflow revocation is pending; retry reporting when connected.")
            state["retired"].append(current)
            state["current"] = None
            changed = True
            for record in self._records():
                if (record["installation_id"] == current["installation_id"]
                        and record["state"] != "submitted"):
                    self._path(record["report"]["report_id"]).unlink()
        if enabled and state["current"] is None:
            state["current"] = {
                "installation_id": str(uuid4()), "token": secrets.token_urlsafe(32),
                "generation": generation,
            }
            changed = True
        if changed:
            _write(self._state_path(), state)
        current = state["current"]
        if (not enabled or current is None
                or installation_id is not None and current["installation_id"] != installation_id):
            return None
        return dict(current)

    def _path(self, report_id: str) -> Path:
        if not _uuid(report_id):
            raise ValueError("The workflow report identity is invalid.")
        return _folder(self.root, "automatic-workflows") / f"workflow-{report_id}.json"

    def _records(self) -> list[dict[str, Any]]:
        records = []
        for path in _folder(self.root, "automatic-workflows").iterdir():
            match = _RECORD_NAME.fullmatch(path.name)
            if not match:
                continue
            record = _read(path)
            validate_report(record["report"])
            if (record["report"]["report_id"] != match[1]
                    or not _uuid(record.get("installation_id"))
                    or not isinstance(record.get("receipt_token"), str)
                    or not _TOKEN.fullmatch(record["receipt_token"])
                    or record.get("state") not in ("queued", "submitted", "rejected")
                    or type(record.get("attempts")) is not int or record["attempts"] < 0
                    or type(record.get("next_attempt")) not in (float, int)
                    or not math.isfinite(record["next_attempt"])
                    or type(record.get("created_epoch")) not in (float, int)
                    or not math.isfinite(record["created_epoch"])):
                raise ValueError("The saved workflow receipt is invalid.")
            if record["created_epoch"] < time.time() - MAX_AGE_SECONDS:
                path.unlink()
            else:
                records.append(record)
        records.sort(key=lambda value: value["created_epoch"], reverse=True)
        for record in records[MAX_RECORDS:]:
            self._path(record["report"]["report_id"]).unlink()
        return records[:MAX_RECORDS]

    def queue(self, report: Mapping[str, Any]) -> bool:
        validate_report(report)
        consent = self._enabled()
        if consent is None:
            return False
        self._records()
        path = self._path(report["report_id"])
        if path.exists():
            saved = _read(path)
            if saved["report"] != report:
                raise ValueError("The workflow report identity already has different contents.")
            return True
        _write(path, {
            "report": dict(report), "installation_id": consent["installation_id"],
            "receipt_token": secrets.token_urlsafe(32), "state": "queued",
            "created_epoch": time.time(), "attempts": 0, "next_attempt": 0,
        })
        self._records()
        return True

    def status(self, report_id: str) -> str:
        if not self.origin or self._enabled() is None:
            return "disabled"
        path = self._path(report_id)
        self._records()
        if not path.exists():
            return "missing"
        record = _read(path)
        if self._enabled(record["installation_id"]) is None:
            return "disabled"
        return str(record["state"])

    def _request(
        self, path: str, payload: Mapping[str, Any], consent: Mapping[str, Any],
        *, revocation: bool = False,
    ) -> dict[str, Any]:
        if (not self.origin
                or not revocation and self._enabled(consent["installation_id"]) is None):
            raise WorkflowReportError("Automatic workflow reporting is disabled.")
        raw = self.transport("POST", self.origin + path, _bytes(payload), {
            "Content-Type": "application/json", "Accept": "application/json",
            "Authorization": f"Bearer {consent['token']}",
            "X-Installation-ID": consent["installation_id"],
        })
        if len(raw) > MAX_REPORT_BYTES:
            raise WorkflowReportError("The reporting response exceeded its size limit.")
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise WorkflowReportError(
                "The reporting service returned an invalid receipt.",
            ) from None
        if not isinstance(value, dict):
            raise WorkflowReportError("The reporting service returned an invalid receipt.")
        return value

    def _revoke_retired(self) -> None:
        for capability in self._state()["retired"][:3]:
            response = self._request(
                f"/v1/workflow-installations/{capability['installation_id']}/revoke",
                {}, capability, revocation=True,
            )
            if (response.get("installation_id") != capability["installation_id"]
                    or response.get("state") != "revoked"):
                raise WorkflowReportError("The reporting revocation receipt is invalid.")
            state = self._state()
            state["retired"] = [
                item for item in state["retired"]
                if item["installation_id"] != capability["installation_id"]
            ]
            _write(self._state_path(), state)

    def deliver(self) -> int:
        """Attempt at most three due records; preserve receipts after ambiguous delivery."""
        if not self.origin:
            return 0
        self._preference()  # Malformed saved preferences never trigger background HTTP.
        self._revoke_retired()
        enabled = self._enabled()
        self._revoke_retired()
        if enabled is None:
            return 0
        sent = attempted = 0
        registered = ""
        for record in self._records():
            if (record["state"] != "queued" or record["next_attempt"] > time.time()
                    or attempted >= 3):
                continue
            consent = self._enabled(record["installation_id"])
            if consent is None:
                continue
            attempted += 1
            record["attempts"] += 1
            record["next_attempt"] = time.time() + min(
                86400, 900 * 2 ** min(record["attempts"] - 1, 7),
            )
            path = self._path(record["report"]["report_id"])
            _write(path, record)  # Identity, exact payload and retry backoff precede HTTP.
            try:
                if registered != consent["installation_id"]:
                    response = self._request("/v1/workflow-installations", {
                        "schema_version": "1", "installation_id": consent["installation_id"],
                    }, consent)
                    if (response.get("installation_id") != consent["installation_id"]
                            or response.get("state") != "registered"):
                        raise WorkflowReportError("The reporting registration receipt is invalid.")
                    registered = consent["installation_id"]
                # Re-read the GUI-owned preference immediately before transmitting content.
                consent = self._enabled(record["installation_id"])
                if consent is None:
                    break
                response = self._request("/v1/workflow-reports", {
                    "report": record["report"], "receipt_token_sha256": hashlib.sha256(
                        record["receipt_token"].encode("ascii"),
                    ).hexdigest(),
                }, consent)
                if (response.get("report_id") != record["report"]["report_id"]
                        or response.get("state") not in ("received", "submitted")):
                    raise WorkflowReportError("The reporting service returned an invalid receipt.")
            except WorkflowReportError as error:
                if error.status in (400, 409, 413, 422):
                    record["state"] = "rejected"
                    _write(path, record)
                raise
            record["state"] = "submitted"
            _write(path, record)
            sent += 1
        return sent
