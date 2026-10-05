"""Allowlisted remote fixation reports and local experiment sharing preferences."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from fpvs_studio.core.compiler_assets import load_manifest, resolve_image_paths
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import resolve_project_relative_path

MAX_REPORT_BYTES = 128 * 1024
Identifier = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
]
VersionText = Annotated[
    str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Count = Annotated[StrictInt, Field(ge=0, le=1_000_000)]
AggregateCount = Annotated[StrictInt, Field(ge=0, le=9_007_199_254_740_991)]


class SharingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


def _utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if value.tzinfo is None or offset is None:
        raise ValueError("Sharing timestamps require an explicit UTC offset.")
    if offset.total_seconds() != 0:
        raise ValueError("Sharing timestamps must be UTC.")
    return value.astimezone(timezone.utc)


def _uuid(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("Report IDs must be canonical lowercase UUIDs.")
    return value


class SharingProfile(SharingModel):
    """Service-reviewed version and protocol, without its secure-store credential."""

    schema_version: Literal["1.0"] = "1.0"
    experiment_id: Identifier
    experiment_version: VersionText
    protocol_sha256: Sha256
    title: str = Field(min_length=1, max_length=160)
    device_id: Identifier


class SharingSettings(SharingModel):
    """Machine-local opt-in; never part of ProjectFile or a compiled contract."""

    schema_version: Literal["1.0"] = "1.0"
    enabled: bool = False
    profile: SharingProfile | None = None

    @model_validator(mode="after")
    def require_profile(self) -> SharingSettings:
        if self.enabled and self.profile is None:
            raise ValueError("Enabling sharing requires enrollment in an experiment.")
        return self


class FixationOccurrence(SharingModel):
    condition_id: Identifier
    occurrence_index: StrictInt = Field(ge=1, le=4096)
    total_targets: Count
    hit_count: Count
    miss_count: Count
    false_alarm_count: Count
    accuracy_percent: float | None = Field(ge=0, le=100)
    mean_rt_ms: float | None = Field(ge=0, le=600_000)
    rt_count: Count
    scoring_source: Literal["timestamps", "frames"]
    refresh_hz: float = Field(ge=1, le=1000)
    response_window_ms: float = Field(ge=0, le=600_000)

    @model_validator(mode="after")
    def conserve_counts(self) -> FixationOccurrence:
        if self.hit_count + self.miss_count != self.total_targets:
            raise ValueError("Hits and misses must equal the target count.")
        expected = 100 * self.hit_count / self.total_targets if self.total_targets else None
        if expected is None:
            if self.accuracy_percent is not None:
                raise ValueError("Zero targets require null accuracy.")
        elif self.accuracy_percent is None or abs(self.accuracy_percent - expected) > 1e-6:
            raise ValueError("Accuracy must match the hit and target counts.")
        if self.rt_count > self.hit_count:
            raise ValueError("RT observations cannot exceed hits.")
        if (self.mean_rt_ms is None) != (self.rt_count == 0):
            raise ValueError("Mean RT is present only with RT observations.")
        return self


class SessionReport(SharingModel):
    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    experiment_id: Identifier
    experiment_version: VersionText
    protocol_sha256: Sha256
    completed_at: datetime
    studio_version: VersionText
    occurrences: tuple[FixationOccurrence, ...] = Field(min_length=1, max_length=4096)

    _validate_id = field_validator("report_id")(_uuid)
    _validate_time = field_validator("completed_at")(_utc)

    @model_validator(mode="after")
    def validate_occurrences(self) -> SessionReport:
        indices = [item.occurrence_index for item in self.occurrences]
        if len(set(indices)) != len(indices):
            raise ValueError("Report occurrence indices must be unique.")
        if len({item.condition_id for item in self.occurrences}) > 512:
            raise ValueError("Report exceeds the 512 distinct condition limit.")
        if len(self.model_dump_json().encode("utf-8")) > MAX_REPORT_BYTES:
            raise ValueError("Report exceeds the 128 KiB limit.")
        return self


class DeliveryReceipt(SharingModel):
    schema_version: Literal["1.0"] = "1.0"
    report_id: str
    experiment_id: Identifier
    experiment_version: VersionText
    protocol_sha256: Sha256
    sha256: Sha256
    received_at: datetime

    _validate_id = field_validator("report_id")(_uuid)
    _validate_time = field_validator("received_at")(_utc)


class ComparisonCondition(SharingModel):
    condition_id: Identifier
    session_count: AggregateCount
    device_count: AggregateCount
    eligible: bool
    total_targets: AggregateCount | None
    hit_count: AggregateCount | None
    accuracy_percent: float | None = Field(ge=0, le=100)
    mean_rt_ms: float | None = Field(ge=0, le=600_000)
    rt_count: AggregateCount | None
    scoring_source: Literal["timestamps", "frames"] | None
    response_window_ms: float | None = Field(ge=0, le=600_000)

    @model_validator(mode="after")
    def validate_metrics(self) -> ComparisonCondition:
        metrics = (
            self.total_targets,
            self.hit_count,
            self.accuracy_percent,
            self.mean_rt_ms,
            self.rt_count,
            self.scoring_source,
            self.response_window_ms,
        )
        if not self.eligible:
            if any(value is not None for value in metrics):
                raise ValueError("Insufficient cohorts must suppress all metrics.")
        else:
            if self.scoring_source is None or self.response_window_ms is None:
                raise ValueError("Eligible cohorts require a uniform scoring definition.")
            if self.total_targets is None or self.hit_count is None or self.rt_count is None:
                raise ValueError("Eligible cohorts require counts.")
            if self.hit_count > self.total_targets or self.rt_count > self.hit_count:
                raise ValueError("Invalid comparison counts.")
            expected = 100 * self.hit_count / self.total_targets if self.total_targets else None
            if expected is None:
                if self.accuracy_percent is not None:
                    raise ValueError("Zero targets require null accuracy.")
            elif self.accuracy_percent is None or abs(self.accuracy_percent - expected) > 1e-6:
                raise ValueError("Comparison accuracy must match counts.")
            if (self.mean_rt_ms is None) != (self.rt_count == 0):
                raise ValueError("Comparison RT requires RT observations.")
        return self


class ComparisonSnapshot(SharingModel):
    schema_version: Literal["1.0"] = "1.0"
    experiment_id: Identifier
    experiment_version: VersionText
    protocol_sha256: Sha256
    minimum_sessions: Literal[10] = 10
    minimum_devices: Literal[3] = 3
    conditions: tuple[ComparisonCondition, ...] = Field(max_length=512)
    generated_at: datetime

    _validate_time = field_validator("generated_at")(_utc)

    @model_validator(mode="after")
    def validate_thresholds(self) -> ComparisonSnapshot:
        if len({item.condition_id for item in self.conditions}) != len(self.conditions):
            raise ValueError("Comparison conditions must be unique.")
        for item in self.conditions:
            if item.eligible and (item.session_count < 10 or item.device_count < 3):
                raise ValueError(
                    "Eligible comparison cohorts require ten sessions and three devices."
                )
        return self


def protocol_fingerprint(
    project: ProjectFile,
    project_root: Path,
    *,
    cancelled: Callable[[], bool] | None = None,
) -> str:
    """Hash authored protocol and actual stimulus bytes, excluding identity and machine state.

    This is a read-only worker operation. Image provenance is rehashed so editing an
    image without updating its manifest cannot silently retain a registered protocol.
    """

    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise InterruptedError("Protocol verification cancelled.")

    check_cancelled()
    payload = project.model_dump(mode="json", exclude={"meta", "manual_removed_electrodes"})
    payload["template_id"] = project.meta.template_id
    settings = payload["settings"]
    for field in ("recording", "allow_repeated_participant_sessions", "condition_profile_id"):
        settings.pop(field, None)
    for field in (
        "fullscreen",
        "monitor_name",
        "screen_width_cm",
        "viewing_distance_cm",
        "screen_width_px",
        "screen_height_px",
        "use_current_screen_resolution",
    ):
        settings["display"].pop(field, None)
    for field in ("serial_port", "baudrate", "pulse_width_ms", "reset_code", "reset_delay_ms"):
        settings["triggers"].pop(field, None)
    settings["session"].pop("session_seed", None)
    asset_paths: set[str] = set()
    image_set_ids = {item.set_id for item in project.stimulus_sets if item.source_dir is not None}
    requested = {
        (set_id, condition.stimulus_variant)
        for condition in project.conditions
        for set_id in (
            condition.base_stimulus_set_id,
            condition.oddball_stimulus_set_id,
            condition.t2_stimulus_set_id,
            condition.isi_stimulus_set_id,
        )
        if set_id in image_set_ids
    }
    if requested:
        manifest = load_manifest(project_root, None)
        sets = {item.set_id: item for item in project.stimulus_sets}
        for set_id, variant in requested:
            check_cancelled()
            asset_paths.update(
                resolve_image_paths(
                    sets[set_id],
                    variant=variant,
                    project_root=project_root,
                    manifest=manifest,
                )
            )

    def inspect(value: object) -> None:
        check_cancelled()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"seed", "random_seed", "session_seed"}:
                    value[key] = None
                else:
                    inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
        elif isinstance(value, str) and value.startswith("stimuli/task-assets/"):
            asset_paths.add(value)

    inspect(payload)
    provenance: list[tuple[str, str]] = []
    for relative_path in sorted(asset_paths):
        check_cancelled()
        path = resolve_project_relative_path(project_root, relative_path)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while True:
                check_cancelled()
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        provenance.append((relative_path, digest.hexdigest()))
    check_cancelled()
    encoded = json.dumps(
        {"project": payload, "assets": provenance},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
