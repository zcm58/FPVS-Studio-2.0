"""Model serialization tests."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode
from fpvs_studio.core.models import Condition, ProjectFile, SessionSettings
from fpvs_studio.core.serialization import load_project_file, save_project_file


def test_project_model_round_trip(tmp_path, sample_project) -> None:
    project_path = tmp_path / "project.json"

    save_project_file(sample_project, project_path)
    loaded = load_project_file(project_path)

    assert loaded == sample_project
    assert loaded.schema_version.value == "1.0.0"


def test_condition_instructions_strip_bidi_control_characters() -> None:
    condition = Condition(
        condition_id="faces",
        name="Faces",
        instructions="\u202eRead the instructions.\u202c",
        base_stimulus_set_id="base-set",
        oddball_stimulus_set_id="oddball-set",
        sequence_count=1,
    )

    assert condition.instructions == "Read the instructions."


def test_session_settings_default_to_space_gated_condition_starts() -> None:
    session = SessionSettings()

    assert session.inter_condition_mode == InterConditionMode.MANUAL_CONTINUE
    assert session.inter_condition_break_seconds == 0.0
    assert session.continue_key == "space"


def test_project_model_backfills_condition_profile_defaults_for_legacy_payload(
    sample_project,
) -> None:
    payload = sample_project.model_dump(mode="python")
    payload["settings"].pop("condition_profile_id", None)
    payload["settings"].pop("condition_defaults", None)

    loaded = ProjectFile.model_validate(payload)

    assert loaded.settings.condition_profile_id is None
    assert loaded.settings.condition_defaults.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert loaded.settings.condition_defaults.sequence_count == 1
    assert loaded.settings.condition_defaults.oddball_cycle_repeats_per_sequence == 146
