"""Model serialization tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpvs_studio.core.enums import DutyCycleMode, InterConditionMode
from fpvs_studio.core.models import Condition, ProjectFile, SessionSettings, TriggerSettings
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

    assert session.block_count == 2
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
    assert loaded.settings.condition_defaults.target_repeats_per_image == 7


def test_trigger_settings_default_and_validate_oddball_marker_code() -> None:
    settings = TriggerSettings()

    assert settings.oddball_trigger_code == 55
    assert settings.reset_code is None

    with pytest.raises(ValidationError, match="less than or equal to 255"):
        TriggerSettings(oddball_trigger_code=300)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        TriggerSettings(oddball_trigger_code=0)

    with pytest.raises(ValidationError):
        TriggerSettings(oddball_trigger_code="55")


def test_project_model_backfills_oddball_trigger_for_legacy_payload(sample_project) -> None:
    payload = sample_project.model_dump(mode="python")
    payload["settings"]["triggers"].pop("oddball_trigger_code", None)

    loaded = ProjectFile.model_validate(payload)

    assert loaded.settings.triggers.oddball_trigger_code == 55


def test_custom_oddball_trigger_code_persists(tmp_path, sample_project) -> None:
    sample_project.settings.triggers.oddball_trigger_code = 88
    project_path = tmp_path / "project.json"

    save_project_file(sample_project, project_path)
    loaded = load_project_file(project_path)

    assert loaded.settings.triggers.oddball_trigger_code == 88
