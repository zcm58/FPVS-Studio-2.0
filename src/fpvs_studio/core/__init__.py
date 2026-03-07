"""Engine-neutral core models, validation, and compilation helpers."""

from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.execution import (
    FixationResponseRecord,
    FrameIntervalRecord,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
    SessionExecutionSummary,
    TriggerRecord,
)
from fpvs_studio.core.models import ProjectFile, SessionSettings, TemplateSpec
from fpvs_studio.core.project_service import ProjectScaffold, build_starter_project, create_project
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.session_plan import SessionPlan
from fpvs_studio.core.template_library import default_template, get_template, list_templates

__all__ = [
    "CompileError",
    "FixationResponseRecord",
    "FrameIntervalRecord",
    "ProjectFile",
    "ProjectScaffold",
    "ResponseRecord",
    "RunSpec",
    "RunExecutionSummary",
    "RuntimeMetadata",
    "SessionPlan",
    "SessionExecutionSummary",
    "SessionSettings",
    "TemplateSpec",
    "TriggerRecord",
    "build_starter_project",
    "compile_run_spec",
    "compile_session_plan",
    "create_project",
    "default_template",
    "get_template",
    "list_templates",
]
