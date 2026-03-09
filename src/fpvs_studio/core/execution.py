"""Engine-neutral execution-result contracts for runtime and exporters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from fpvs_studio.core.enums import RunMode, SchemaVersion
from fpvs_studio.core.models import FPVSBaseModel, validate_project_relative_path

FixationOutcome = Literal["hit", "miss"]
ResponseOutcome = Literal["hit", "false_alarm"]
TriggerStatus = Literal["sent", "failed", "skipped"]


def _validate_participant_number(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("participant_number may not be blank.")
    if not cleaned.isdigit():
        raise ValueError("participant_number must contain digits only.")
    return cleaned


class RuntimeMetadata(FPVSBaseModel):
    """Measured runtime/display metadata captured while executing a session."""

    engine_name: str
    engine_version: str | None = None
    python_version: str | None = None
    display_index: int | None = Field(default=None, ge=0)
    monitor_name: str | None = None
    screen_width_px: int | None = Field(default=None, gt=0)
    screen_height_px: int | None = Field(default=None, gt=0)
    fullscreen: bool | None = None
    requested_refresh_hz: float | None = Field(default=None, gt=0)
    actual_refresh_hz: float | None = Field(default=None, gt=0)
    frame_interval_recording: bool = False
    test_mode: bool = False


class FrameIntervalRecord(FPVSBaseModel):
    """One measured display frame interval."""

    frame_index: int = Field(ge=0)
    interval_s: float = Field(gt=0)


class ResponseRecord(FPVSBaseModel):
    """One captured participant response during a run."""

    response_index: int = Field(ge=0)
    key: str
    frame_index: int = Field(ge=0)
    time_s: float | None = Field(default=None, ge=0)
    matched_event_index: int | None = Field(default=None, ge=0)
    rt_frames: int | None = Field(default=None, ge=0)
    correct: bool | None = None
    outcome: ResponseOutcome | None = None

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Response key may not be blank.")
        return cleaned


class FixationResponseRecord(FPVSBaseModel):
    """Outcome for one scheduled fixation-color target event."""

    event_index: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    responded: bool
    first_response_key: str | None = None
    response_frame: int | None = Field(default=None, ge=0)
    response_time_s: float | None = Field(default=None, ge=0)
    rt_frames: int | None = Field(default=None, ge=0)
    outcome: FixationOutcome

    @model_validator(mode="after")
    def validate_response_fields(self) -> "FixationResponseRecord":
        if self.responded:
            if self.first_response_key is None or self.response_frame is None or self.rt_frames is None:
                raise ValueError(
                    "Responded fixation events must include the first response key, frame, and RT."
                )
            if self.outcome != "hit":
                raise ValueError("Responded fixation events must use the 'hit' outcome.")
        else:
            if (
                self.first_response_key is not None
                or self.response_frame is not None
                or self.response_time_s is not None
                or self.rt_frames is not None
            ):
                raise ValueError("Missed fixation events may not include response metadata.")
            if self.outcome != "miss":
                raise ValueError("Unanswered fixation events must use the 'miss' outcome.")
        return self


class FixationTaskSummary(FPVSBaseModel):
    """Condition-level fixation accuracy metrics for participant feedback and export."""

    total_targets: int = Field(ge=0)
    hit_count: int = Field(ge=0)
    miss_count: int = Field(ge=0)
    false_alarm_count: int = Field(ge=0)
    accuracy_percent: float = Field(ge=0)
    mean_rt_ms: float | None = Field(default=None, ge=0)


class TriggerRecord(FPVSBaseModel):
    """One attempted trigger emission observed during execution."""

    trigger_index: int = Field(ge=0)
    frame_index: int = Field(ge=0)
    time_s: float | None = Field(default=None, ge=0)
    code: int
    label: str
    backend_name: str
    status: TriggerStatus = "sent"
    message: str | None = None

    @field_validator("label", "backend_name")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Trigger labels and backend names may not be blank.")
        return cleaned


class RunExecutionSummary(FPVSBaseModel):
    """Execution result for one `RunSpec` playback."""

    schema_version: str = SchemaVersion.V1.value
    project_id: str
    session_id: str | None = None
    run_id: str
    condition_id: str
    condition_name: str
    engine_name: str
    run_mode: RunMode
    participant_number: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    completed_frames: int = Field(default=0, ge=0)
    aborted: bool = False
    abort_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    runtime_metadata: RuntimeMetadata | None = None
    frame_intervals: list[FrameIntervalRecord] = Field(default_factory=list)
    fixation_responses: list[FixationResponseRecord] = Field(default_factory=list)
    fixation_task_summary: FixationTaskSummary | None = None
    response_log: list[ResponseRecord] = Field(default_factory=list)
    trigger_log: list[TriggerRecord] = Field(default_factory=list)
    output_dir: str | None = None

    @field_validator("participant_number")
    @classmethod
    def validate_participant_number(cls, value: str | None) -> str | None:
        return _validate_participant_number(value)

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_project_relative_path(value)


class SessionExecutionSummary(FPVSBaseModel):
    """Session-level aggregate result built by the runtime."""

    schema_version: str = SchemaVersion.V1.value
    project_id: str
    session_id: str
    engine_name: str
    run_mode: RunMode
    participant_number: str | None = None
    random_seed: int | None = Field(default=None, ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_condition_count: int = Field(default=0, ge=0)
    completed_condition_count: int = Field(default=0, ge=0)
    aborted: bool = False
    abort_reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    runtime_metadata: RuntimeMetadata | None = None
    realized_block_orders: list[list[str]] = Field(default_factory=list)
    run_results: list[RunExecutionSummary] = Field(default_factory=list)
    output_dir: str | None = None

    @field_validator("participant_number")
    @classmethod
    def validate_participant_number(cls, value: str | None) -> str | None:
        return _validate_participant_number(value)

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_project_relative_path(value)
