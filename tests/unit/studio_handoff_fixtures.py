"""Portable, synthetic exports shared with Toolbox's consumer regression suite."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fpvs_studio import __version__
from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.execution import (
    AcquisitionCodeMapEntry,
    AcquisitionEvidence,
    AcquisitionRunEvidence,
    RecordingSnapshot,
    TriggerRecord,
)
from fpvs_studio.core.models import (
    Condition,
    FixationTaskSettings,
    ProjectFile,
    ProjectMeta,
    ProjectRecordingSettings,
    ProjectSettings,
    SessionSettings,
    StimulusSet,
)
from fpvs_studio.core.project_config import (
    ProjectConfigFile,
    completed_toolbox_config,
    export_project_config,
    read_project_config,
)
from fpvs_studio.core.recording_hardware import acquisition_profile_for_recording

FIXTURE_TIME = datetime(2000, 1, 1, tzinfo=timezone.utc)


def legacy_config_payload(config: ProjectConfigFile, version: str) -> dict[str, Any]:
    """Build a historical envelope for immutable-reader regression tests only."""

    payload = config.model_dump(mode="json")
    for field in ("format", "format_version", "kind", "metadata"):
        payload.pop(field)
    payload["schema_version"] = version
    return payload


def read_legacy_config(
    config: ProjectConfigFile, version: str, directory: Path,
) -> ProjectConfigFile:
    path = directory / "legacy.fpvsconfig"
    path.write_text(json.dumps(legacy_config_payload(config, version)), encoding="utf-8")
    return read_project_config(path)


def build_handoff_fixtures(project_root: Path) -> dict[str, ProjectConfigFile]:
    """Compile synthetic words without real recordings, images, Qt or hardware."""

    project = ProjectFile(
        meta=ProjectMeta(
            project_id="handoff-fixture", name="Shared handoff fixture",
            template_id="fpvs_6hz_every5_v1",
        ),
        settings=ProjectSettings(
            fixation_task=FixationTaskSettings(enabled=False, accuracy_task_enabled=False),
            session=SessionSettings(block_count=1, session_seed=42),
            recording=ProjectRecordingSettings(recording_backend="serial"),
        ),
        stimulus_sets=[
            StimulusSet(set_id="base", name="Base", modality=StimulusModality.WORD,
                        words=["one", "two", "three"]),
            StimulusSet(set_id="oddball", name="Oddball", modality=StimulusModality.WORD,
                        words=["four", "five", "six"]),
        ],
        conditions=[Condition(
            condition_id="words", name="Words", trigger_code=1,
            base_stimulus_set_id="base", oddball_stimulus_set_id="oddball",
            sequence_count=1, oddball_cycle_repeats_per_sequence=146, order_index=0,
        )],
    )
    result = {"v2-setup.fpvsconfig": export_project_config(project, None)}
    for backend, label in (("serial", "biosemi"), ("unicorn_udp", "unicorn")):
        selected = project.model_copy(deep=True)
        selected.settings.recording = ProjectRecordingSettings(recording_backend=backend)
        config = export_project_config(selected, None)
        plan = compile_session_plan(
            selected, project_root=project_root, refresh_hz=60, random_seed=42,
            session_id="fixture-session",
        )
        profile = acquisition_profile_for_recording(backend)
        evidence = AcquisitionEvidence(
            studio_version=__version__, execution_id=f"fixture-{label}-execution",
            project_id=plan.project_id, participant_number="007", participant_session_number=2,
            session_id=plan.session_id, acquisition_profile=profile,
            recording=RecordingSnapshot(
                selected_backend=backend, effective_backend=backend,
                selection_source="project_settings", receiver_validation="pending",
                acquisition_profile=profile,
            ),
            created_at_utc=FIXTURE_TIME, updated_at_utc=FIXTURE_TIME, state="completed",
            runs=[AcquisitionRunEvidence(
                run_id=entry.run_id, condition_id=entry.condition_id,
                condition_name=entry.condition_name,
                planned_event_count=len(entry.run_spec.trigger_events), state="completed",
                code_map=[AcquisitionCodeMapEntry(code=1, label="condition_start"),
                          AcquisitionCodeMapEntry(code=55, label="oddball")],
                attempted_events=[TriggerRecord(
                    trigger_index=index, frame_index=event.frame_index,
                    time_s=event.frame_index / 60, code=event.code, label=event.label,
                    backend_name=backend,
                ) for index, event in enumerate(entry.run_spec.trigger_events)],
            ) for entry in plan.ordered_entries()],
        )
        result[f"v2-completed-{label}.fpvsconfig"] = completed_toolbox_config(
            config, project_root, plan, evidence, manual_removed_electrodes=("P9", "P10"),
        )
    frequencies = project.model_copy(deep=True)
    frequencies.schema_version = ProjectSchemaVersion.V1_11
    frequencies.conditions.append(frequencies.conditions[0].model_copy(update={
        "condition_id": "slow-words", "name": "Slow words", "trigger_code": 2,
        "base_hz": 3.0, "order_index": 1,
    }))
    result["v2-condition-frequency.fpvsconfig"] = export_project_config(frequencies, None)
    for config in result.values():
        config.producer.exported_at = FIXTURE_TIME
        config.metadata["fixture"] = "Synthetic compatibility evidence; no EEG was acquired."
    return result
