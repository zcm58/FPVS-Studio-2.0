"""Small project-local Library receipts, separate from authored experiment contracts."""

from __future__ import annotations

import stat
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from fpvs_studio.core.paths import filesystem_path, validate_project_id
from fpvs_studio.core.serialization import atomic_text_write

ORIGIN_DIRECTORY = ".fpvs-library"
ORIGIN_FILENAME = "project-origin.json"
MAX_ORIGIN_BYTES = 16 * 1024


class LibraryOriginError(ValueError):
    """A local Library receipt could not be read or saved safely."""


class LibraryProjectOrigin(BaseModel):
    """An explicit Library association; unknown legacy versions are never guessed."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    service_url: str = Field(min_length=1, max_length=2048)
    item_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: Literal["experiment"] = "experiment"
    installed_version: str | None = Field(default=None, min_length=1, max_length=64)
    bundle_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    local_project_id: str = Field(
        min_length=1, max_length=255, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    auto_check: bool = True

    @field_validator("service_url")
    @classmethod
    def validate_service_url(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError:
            raise ValueError("Library service must be a valid HTTPS origin.") from None
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or any(ord(char) <= 32 for char in value)
        ):
            raise ValueError("Library service must be one HTTPS origin without credentials.")
        return value.rstrip("/")

    @field_validator("installed_version")
    @classmethod
    def validate_version(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                Version(value)
            except InvalidVersion:
                raise ValueError("Invalid installed Library version.") from None
        return value

    @field_validator("local_project_id")
    @classmethod
    def validate_local_id(cls, value: str) -> str:
        validate_project_id(value)
        return value


def _origin_path(project_root: Path) -> Path:
    root = filesystem_path(Path(project_root))
    if not root.is_dir():
        raise LibraryOriginError("Library origin requires an existing project directory.")
    path = root / ORIGIN_DIRECTORY / ORIGIN_FILENAME
    for candidate, directory in ((root, True), (path.parent, True), (path, False)):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise LibraryOriginError("Library origin paths cannot contain links or reparse points.")
        expected_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if not expected_type or (not directory and info.st_nlink != 1):
            raise LibraryOriginError("Library origin is not a private regular project file.")
    if not path.resolve().is_relative_to(root.resolve()):
        raise LibraryOriginError("Library origin path escapes the project directory.")
    return path


def load_library_origin(project_root: Path) -> LibraryProjectOrigin | None:
    """Read a bounded receipt; absence means unlinked, malformed metadata is an error."""
    try:
        path = _origin_path(project_root)
        if not path.exists():
            return None
        with path.open("rb") as stream:
            payload = stream.read(MAX_ORIGIN_BYTES + 1)
        if len(payload) > MAX_ORIGIN_BYTES:
            raise LibraryOriginError("Library origin exceeds its size limit.")
        return LibraryProjectOrigin.model_validate_json(payload)
    except (ValidationError, UnicodeError) as error:
        raise LibraryOriginError("Library project origin is invalid or unsupported.") from error
    except OSError as error:
        raise LibraryOriginError("Library project origin could not be read.") from error


def save_library_origin(project_root: Path, origin: LibraryProjectOrigin) -> None:
    """Atomically persist an explicit association without changing project.json."""
    origin = LibraryProjectOrigin.model_validate(origin.model_dump())
    try:
        path = _origin_path(project_root)
        path.parent.mkdir(exist_ok=True)
        _origin_path(project_root)
        atomic_text_write(path, origin.model_dump_json(indent=2))
    except OSError as error:
        raise LibraryOriginError("Library project origin could not be saved.") from error


def origin_for_import(
    origin: LibraryProjectOrigin, local_project_id: str,
) -> LibraryProjectOrigin:
    """Bind verified import metadata to the collision-safe local project identity."""
    return LibraryProjectOrigin.model_validate({
        **origin.model_dump(), "local_project_id": local_project_id,
    })
