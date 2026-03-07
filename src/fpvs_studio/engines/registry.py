"""Presentation engine registry."""

from __future__ import annotations

from collections.abc import Callable

from fpvs_studio.core.enums import EngineName
from fpvs_studio.engines.base import PresentationEngine

EngineFactory = Callable[[], PresentationEngine]


def _normalize_engine_name(engine_name: str | EngineName) -> str:
    return engine_name.value if isinstance(engine_name, EngineName) else engine_name


def _create_psychopy_engine() -> PresentationEngine:
    from fpvs_studio.engines.psychopy_engine import PsychoPyEngine

    return PsychoPyEngine()


_ENGINE_FACTORIES: dict[str, EngineFactory] = {
    EngineName.PSYCHOPY.value: _create_psychopy_engine,
}


def available_engines() -> list[str]:
    """Return registered engine ids."""

    return list(_ENGINE_FACTORIES)


def register_engine(engine_name: str | EngineName, factory: EngineFactory) -> None:
    """Register a presentation engine factory."""

    _ENGINE_FACTORIES[_normalize_engine_name(engine_name)] = factory


def unregister_engine(engine_name: str | EngineName) -> None:
    """Remove a presentation engine factory if it exists."""

    _ENGINE_FACTORIES.pop(_normalize_engine_name(engine_name), None)


def create_engine(engine_name: str | EngineName) -> PresentationEngine:
    """Instantiate a presentation engine by name."""

    normalized_name = _normalize_engine_name(engine_name)
    try:
        return _ENGINE_FACTORIES[normalized_name]()
    except KeyError as exc:
        raise KeyError(f"Unsupported engine '{normalized_name}'.") from exc
