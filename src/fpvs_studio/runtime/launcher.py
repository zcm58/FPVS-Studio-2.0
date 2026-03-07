"""Runtime launch entry points for single runs and multi-run sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from fpvs_studio.core.enums import EngineName
from fpvs_studio.core.execution import RunExecutionSummary, SessionExecutionSummary
from fpvs_studio.core.paths import runs_dir, to_project_relative_posix
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.engines.registry import create_engine
from fpvs_studio.runtime.preflight import preflight_run_spec, preflight_session_plan
from fpvs_studio.runtime.run_worker import RuntimeWorker


class LaunchSettingsError(ValueError):
    """Raised when runtime-only launch settings are invalid for the current v1 runtime."""


@dataclass(frozen=True)
class LaunchSettings:
    """Runtime-only machine/launch options that do not belong in core models."""

    engine_name: str | EngineName = EngineName.PSYCHOPY
    test_mode: bool = True
    display_index: int | None = None
    serial_port: str | None = None

    def as_runtime_options(self) -> dict[str, object]:
        """Return a generic engine-facing runtime options mapping."""

        options = asdict(self)
        engine_name = options["engine_name"]
        if isinstance(engine_name, EngineName):
            options["engine_name"] = engine_name.value
        return options


def _validate_launch_settings(settings: LaunchSettings) -> None:
    if not settings.test_mode:
        raise LaunchSettingsError(
            "FPVS Studio Phase 4 currently requires test_mode=True. "
            "Fullscreen/runtime-only launches remain deferred."
        )
    if settings.display_index is not None:
        if not isinstance(settings.display_index, int) or settings.display_index < 0:
            raise LaunchSettingsError("display_index must be None or a non-negative integer.")
    if settings.serial_port is not None and not settings.serial_port.strip():
        raise LaunchSettingsError("serial_port may not be blank when provided.")


def launch_run(
    project_root: Path,
    run_spec: RunSpec,
    launch_settings: LaunchSettings | None = None,
) -> RunExecutionSummary:
    """Launch one compiled RunSpec into the selected presentation engine."""

    settings = launch_settings or LaunchSettings()
    _validate_launch_settings(settings)
    output_dir = runs_dir(project_root) / run_spec.run_id
    relative_output_dir = to_project_relative_posix(project_root, output_dir)
    engine = create_engine(settings.engine_name)
    preflight_run_spec(project_root, run_spec, engine=engine)
    worker = RuntimeWorker(engine)
    return worker.execute(
        project_root,
        run_spec,
        output_dir,
        runtime_options=settings.as_runtime_options(),
        relative_output_dir=relative_output_dir,
    )


def launch_session(
    project_root: Path,
    session_plan: SessionPlan,
    launch_settings: LaunchSettings | None = None,
) -> SessionExecutionSummary:
    """Launch an ordered session plan into the selected presentation engine."""

    settings = launch_settings or LaunchSettings()
    _validate_launch_settings(settings)
    output_dir = runs_dir(project_root) / session_plan.session_id
    relative_output_dir = to_project_relative_posix(project_root, output_dir)
    engine = create_engine(settings.engine_name)
    preflight_session_plan(project_root, session_plan, engine=engine)
    worker = RuntimeWorker(engine)
    return worker.execute_session(
        project_root,
        session_plan,
        output_dir,
        runtime_options=settings.as_runtime_options(),
        relative_output_dir=relative_output_dir,
    )
