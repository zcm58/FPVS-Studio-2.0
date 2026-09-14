"""Versioned reviewed report payloads and local-only delivery state."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import secrets
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from fpvs_studio import __version__

MAX_LOG_BYTES = 96 * 1024
MAX_DESCRIPTION_BYTES = 16 * 1024
MAX_PAYLOAD_BYTES = 128 * 1024
MAX_FEATURE_CHARACTERS = 4000
MAX_FEATURE_PAYLOAD_BYTES = 32 * 1024
ReportKind = Literal["bug", "feature"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Report(BaseModel):
    """Only these fields may leave the machine; no paths or project metadata."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"
    kind: ReportKind = "bug"
    report_id: UUID = Field(default_factory=uuid4)
    created_at: str = Field(default_factory=utc_now)
    title: str = ""
    happened: str = ""
    steps: str = ""
    expected: str = ""
    email: str = ""
    app_version: str = Field(default_factory=lambda: str(__version__))
    os_version: str = Field(default_factory=lambda: f"{platform.system()} {platform.release()}")
    diagnostics: str = ""

    def problems(self, *, include_logs: bool = True) -> dict[str, str]:
        errors: dict[str, str] = {}
        if self.kind == "feature":
            if not self.happened.strip() or len(self.happened) > MAX_FEATURE_CHARACTERS:
                errors["happened"] = "Describe your feature in 1–4,000 characters."
            if len(self.payload()) > MAX_FEATURE_PAYLOAD_BYTES:
                errors["happened"] = "The complete feature request must fit within 32 KiB."
            return errors
        if not self.title.strip() or len(self.title) > 160:
            errors["title"] = "Enter a summary of 1–160 characters."
        if not self.happened.strip():
            errors["happened"] = "Describe what happened."
        description = self.happened + self.steps + self.expected
        if len(description.encode("utf-8")) > MAX_DESCRIPTION_BYTES:
            errors["happened"] = "Description fields together must fit within 16 KiB of text."
        if self.email and (
            len(self.email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", self.email)
        ):
            errors["email"] = "Enter a valid reply email or leave it blank."
        if include_logs and len(self.diagnostics.encode("utf-8")) > MAX_LOG_BYTES:
            errors["diagnostics"] = "Error logs must fit within 96 KiB; edit or exclude them."
        if len(self.payload(include_logs=include_logs)) > MAX_PAYLOAD_BYTES:
            errors["happened"] = "The complete report must fit within 128 KiB."
        return errors

    def payload(self, *, include_logs: bool = True) -> bytes:
        data = self.model_dump(mode="json")
        if self.kind == "feature":
            data = {key: data[key] for key in (
                "schema_version", "kind", "report_id", "created_at", "app_version"
            )}
            data["description"] = self.happened
        else:
            # Preserve existing bug payload bytes and outstanding receipt hashes.
            data.pop("kind")
        if not include_logs:
            if self.kind == "bug":
                data["diagnostics"] = ""
        return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )

    def digest(self, *, include_logs: bool = True) -> str:
        return hashlib.sha256(self.payload(include_logs=include_logs)).hexdigest()

    def as_text(self, *, include_logs: bool = True) -> str:
        if self.kind == "feature":
            return (
                f"FPVS Studio feature request\n{self.report_id}\n\n"
                f"Requested feature\n{self.happened}\n\nApplication\n{self.app_version}\n"
            )
        sections = [
            ("FPVS Studio bug report", str(self.report_id)),
            ("Summary", self.title),
            ("What happened", self.happened),
            ("Steps to reproduce", self.steps),
            ("Expected behavior", self.expected),
            ("Reply email (optional)", self.email),
            ("Application", self.app_version),
            ("Operating system", self.os_version),
            ("Error logs", self.diagnostics if include_logs else "Excluded by the reporter."),
        ]
        return "\n\n".join(f"{heading}\n{value}" for heading, value in sections) + "\n"


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent_id: str = Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")
    browser_token: str = Field(pattern=r"^[A-Za-z0-9_-]{32,256}$", repr=False)
    desktop_token: str = Field(pattern=r"^[A-Za-z0-9_-]{32,256}$", repr=False)


Delivery = Literal["editing", "uncertain", "received", "submitted"]


class Draft(BaseModel):
    """Receipt secrets stay local and never enter copy/save-as-text exports."""

    model_config = ConfigDict(extra="forbid")
    report: Report = Field(default_factory=Report)
    include_logs: bool = True
    updated_at: str = Field(default_factory=utc_now)
    delivery: Delivery = "editing"
    receipt_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        pattern=r"^[A-Za-z0-9_-]{43}$",
        repr=False,
    )
    service_url: str = ""

    @property
    def locked(self) -> bool:
        return self.delivery != "editing"
