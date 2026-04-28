"""JSON serialization helpers for persisted core contracts. It reads and writes ProjectFile
data and related models using stable engine-neutral schemas that other layers can trust.
The module owns file-format translation only, not business rules, compilation, or
runtime export policy."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from fpvs_studio.core.models import ProjectFile

ModelT = TypeVar("ModelT", bound=BaseModel)


def model_to_json(model: BaseModel, *, indent: int = 2) -> str:
    """Serialize a Pydantic model to formatted JSON."""

    return model.model_dump_json(indent=indent, exclude_none=True)


def write_json_file(path: Path, model: BaseModel, *, indent: int = 2) -> None:
    """Write a model as UTF-8 JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model_to_json(model, indent=indent), encoding="utf-8")


def read_json_file(path: Path, model_type: type[ModelT]) -> ModelT:
    """Read a UTF-8 JSON file into a Pydantic model."""

    return model_type.model_validate_json(path.read_text(encoding="utf-8"))


def save_project_file(project: ProjectFile, path: Path) -> None:
    """Write a project JSON file."""

    write_json_file(path, project)


def load_project_file(path: Path) -> ProjectFile:
    """Load a project JSON file."""

    return read_json_file(path, ProjectFile)
