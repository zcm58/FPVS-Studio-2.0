"""Opt-in, fixed-origin report-service client. No GitHub credentials live here."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPException
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fpvs_studio.support.models import Draft, Intent

SERVICE_ORIGIN = "https://reports.zack-murphy.com"
MAX_RESPONSE_BYTES = 16 * 1024
REQUEST_DEADLINE_SECONDS = 30
Transport = Callable[[str, str, bytes | None, dict[str, str]], bytes]


class ReportServiceError(Exception):
    """Safe user-facing network/protocol failure, without echoing secrets or bodies."""


class ReportCancelled(ReportServiceError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def http_transport(method: str, url: str, data: bytes | None, headers: dict[str, str]) -> bytes:
    request = Request(
        url, data=data,
        headers={"User-Agent": "FPVS-Studio/1.0", "Accept-Encoding": "identity", **headers},
        method=method,
    )
    started = time.monotonic()
    try:
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            if response.headers.get_content_type() != "application/json":
                raise ReportServiceError("The reporting service returned an unexpected response.")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise ReportServiceError("The reporting service returned compressed transport.")
            content = bytearray()
            while True:
                if time.monotonic() - started > REQUEST_DEADLINE_SECONDS:
                    raise ReportServiceError(
                        "The reporting request timed out. Your draft is preserved."
                    )
                chunk = response.read1(min(4096, MAX_RESPONSE_BYTES + 1 - len(content)))
                if time.monotonic() - started > REQUEST_DEADLINE_SECONDS:
                    raise ReportServiceError(
                        "The reporting request timed out. Your draft is preserved."
                    )
                if not chunk:
                    break
                content.extend(chunk)
                if len(content) > MAX_RESPONSE_BYTES:
                    raise ReportServiceError(
                        "The reporting service response exceeded its size limit."
                    )
    except HTTPError as error:
        status = error.code
        error.close()
        if status == 429:
            raise ReportServiceError("The reporting service is busy. Try again later.") from None
        if status in (401, 403, 410):
            raise ReportServiceError(
                "Verification or receipt access expired. Keep your saved report."
            ) from None
        raise ReportServiceError(
            f"The reporting service could not complete the request ({status})."
        ) from None
    except (URLError, TimeoutError, OSError, HTTPException):
        raise ReportServiceError(
            "Could not reach the reporting service. Your draft is preserved."
        ) from None
    return bytes(content)


@dataclass(frozen=True)
class Receipt:
    report_id: str
    state: str


class ReportClient:
    def __init__(self, origin: str = "", *, transport: Transport = http_transport) -> None:
        if origin and origin != SERVICE_ORIGIN:
            raise ValueError("The report endpoint must be the approved HTTPS reporting service.")
        self.origin = origin
        self.transport = transport

    @classmethod
    def configured(cls) -> ReportClient:
        return cls(os.environ.get("FPVS_REPORT_SERVICE_URL", SERVICE_ORIGIN).strip())

    @property
    def enabled(self) -> bool:
        return bool(self.origin)

    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        token: str = "",
        cancel: Event | None = None,
    ) -> dict[str, object]:
        if not self.enabled:
            raise ReportServiceError(
                "Online reporting is not connected yet. Save or copy the report."
            )
        if cancel is not None and cancel.is_set():
            raise ReportCancelled("Submission canceled. Your draft is preserved.")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        raw = self.transport(method, self.origin + path, data, headers)
        if cancel is not None and cancel.is_set():
            raise ReportCancelled("Submission canceled. Your draft is preserved.")
        try:
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("large response")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("not an object")
        except (ValueError, UnicodeError, RecursionError):
            raise ReportServiceError(
                "The reporting service returned an invalid response."
            ) from None
        return result

    def create_intent(self, draft: Draft, cancel: Event) -> Intent:
        if draft.locked or draft.report.problems(include_logs=draft.include_logs):
            raise ReportServiceError("Review the report before requesting verification.")
        body = json.dumps(
            {
                "schema_version": "1",
                "report_id": str(draft.report.report_id),
                "payload_sha256": draft.report.digest(include_logs=draft.include_logs),
                "receipt_token_sha256": hashlib.sha256(draft.receipt_token.encode()).hexdigest(),
            }
        ).encode()
        response = self._request("POST", "/v1/intents", data=body, cancel=cancel)
        try:
            return Intent.model_validate(response)
        except ValueError:
            raise ReportServiceError(
                "The reporting service returned invalid verification data."
            ) from None

    def verification_url(self, intent: Intent) -> str:
        return (
            self.origin
            + "/verify#"
            + urlencode(
                {
                    "intent_id": intent.intent_id,
                    "token": intent.browser_token,
                }
            )
        )

    def intent_status(self, intent: Intent, cancel: Event) -> str:
        response = self._request(
            "GET",
            f"/v1/intents/{quote(intent.intent_id, safe='')}/status",
            token=intent.desktop_token,
            cancel=cancel,
        )
        state = response.get("state")
        if state not in ("pending", "verified", "expired"):
            raise ReportServiceError("The verification response was not understood.")
        return str(state)

    def submit(self, draft: Draft, intent: Intent, cancel: Event) -> Receipt:
        # The caller MUST durably save delivery='uncertain' before this method.
        if draft.delivery != "uncertain" or draft.service_url != self.origin:
            raise ReportServiceError("Save the delivery receipt before sending this report.")
        if draft.report.problems(include_logs=draft.include_logs):
            raise ReportServiceError("The report exceeds its permitted fields or limits.")
        body = draft.report.payload(include_logs=draft.include_logs)
        response = self._request(
            "POST",
            f"/v1/reports?intent_id={quote(intent.intent_id, safe='')}",
            data=body,
            token=intent.desktop_token,
            cancel=cancel,
        )
        return self._receipt(response, draft)

    def check_receipt(self, draft: Draft, cancel: Event) -> Receipt:
        if draft.service_url != self.origin:
            raise ReportServiceError("This receipt belongs to a different reporting configuration.")
        response = self._request(
            "GET",
            f"/v1/reports/{draft.report.report_id}/status",
            token=draft.receipt_token,
            cancel=cancel,
        )
        return self._receipt(response, draft)

    @staticmethod
    def _receipt(response: dict[str, object], draft: Draft) -> Receipt:
        state = response.get("state")
        if response.get("report_id") != str(draft.report.report_id) or state not in (
            "received",
            "submitted",
            "uncertain",
            "not_received",
        ):
            raise ReportServiceError("The reporting service returned an invalid receipt.")
        return Receipt(str(draft.report.report_id), str(state))
