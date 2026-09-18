"""JSON serialization helpers for persisted core contracts. It reads and writes ProjectFile
data and related models using stable engine-neutral schemas that other layers can trust.
The module owns file-format translation only, not business rules, compilation, or
runtime export policy."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import TypeVar
from uuid import uuid4

from pydantic import BaseModel

from fpvs_studio.core.experiment_categories import require_valid_experiment_category
from fpvs_studio.core.migrations import migrate_project_payload
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import filesystem_path

ModelT = TypeVar("ModelT", bound=BaseModel)
logger = logging.getLogger(__name__)


def model_to_json(model: BaseModel, *, indent: int = 2) -> str:
    """Serialize a Pydantic model to formatted JSON."""

    if isinstance(model, ProjectFile):
        require_valid_experiment_category(model)
        if not model.condition_modifiers:
            return model.model_dump_json(
                indent=indent, exclude_none=True, exclude={"condition_modifiers"},
            )
    return model.model_dump_json(indent=indent, exclude_none=True)


def write_json_file(path: Path, model: BaseModel, *, indent: int = 2) -> None:
    """Write a model as UTF-8 JSON."""

    payload = model_to_json(model, indent=indent)
    atomic_text_write(path, payload)


def atomic_text_write(path: Path, text: str, *, newline: str | None = None) -> None:
    """Replace one UTF-8 file only after a complete, flushed sibling write."""

    path = filesystem_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline=newline) as handle:
            created = True
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        replace_file_atomically(temporary, path)
    finally:
        if created:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove incomplete save %s", temporary, exc_info=True)


def replace_file_atomically(source: Path, destination: Path) -> None:
    """Commit a closed sibling file, tolerating only brief Windows replacement locks.

    The same atomic operation is retried for at most 150 ms. Persistent access errors
    still propagate; the destination is never truncated or removed as a fallback.
    """

    for delay in (0.01, 0.02, 0.04, 0.08, None):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in {5, 32, 33} or delay is None:
                raise
            logger.debug("Windows replacement lock for %s; retrying in %.2f s", destination, delay)
            time.sleep(delay)


def read_json_file(path: Path, model_type: type[ModelT]) -> ModelT:
    """Read a UTF-8 JSON file into a Pydantic model."""

    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def save_project_file(project: ProjectFile, path: Path) -> None:
    """Write a project JSON file."""

    write_json_file(path, project)


def load_project_file(path: Path) -> ProjectFile:
    """Load a project JSON file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Project file must contain a JSON object.")
    return migrate_project_payload(payload)
