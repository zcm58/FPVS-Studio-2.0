"""Model serialization tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpvs_studio.core.display_geometry import visual_angle_width_cm, visual_angle_width_px
from fpvs_studio.core.enums import (
    DutyCycleMode,
    InterConditionMode,
    StimulusModality,
    TriggerBackendKind,
)
from fpvs_studio.core.models import (
    MAX_WORD_STIMULUS_CHARS,
    Condition,
    DisplaySettings,
    FixationTaskSettings,
    ProjectFile,
    SessionSettings,
    StimulusSet,
    TriggerSettings,
)
from fpvs_studio.core.run_spec import FixationStyleSpec
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.trigger_codes import LOCKED_ODDBALL_TRIGGER_CODE


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


def test_condition_trigger_code_rejects_biosemi_reset_code() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        Condition(
            condition_id="faces",
            name="Faces",
            base_stimulus_set_id="base-set",
            oddball_stimulus_set_id="oddball-set",
            sequence_count=1,
            trigger_code=0,
        )


def test_fixation_response_key_rejects_escape_abort_key() -> None:
    with pytest.raises(ValidationError, match="reserved for abort"):
        FixationTaskSettings(response_key="escape")

    with pytest.raises(ValidationError, match="reserved for abort"):
        FixationTaskSettings(response_keys=["space", "escape"])

    with pytest.raises(ValidationError, match="reserved for abort"):
        FixationStyleSpec(
            default_color="#0000FF",
            target_color="#FF0000",
            response_key="escape",
            response_keys=["escape"],
            cross_size_px=27,
            line_width_px=2,
            target_duration_frames=15,
        )


def test_session_settings_default_to_space_gated_condition_starts() -> None:
    session = SessionSettings()

    assert session.block_count == 2
    assert session.inter_condition_mode == InterConditionMode.MANUAL_CONTINUE
    assert session.inter_condition_break_seconds == 0.0
    assert session.continue_key == "space"
    assert session.show_condition_title_on_screen is False


def test_display_settings_default_and_validate_image_display_geometry() -> None:
    display = DisplaySettings()

    assert display.stimulus_width_degrees == 5.0
    assert display.viewing_distance_cm == 57.0
    assert display.screen_width_cm == 56.25
    assert display.screen_width_px == 1920
    assert display.screen_height_px == 1080
    assert display.use_current_screen_resolution is False

    with pytest.raises(ValidationError, match="greater than 0"):
        DisplaySettings(stimulus_width_degrees=0)

    with pytest.raises(ValidationError, match="greater than 0"):
        DisplaySettings(viewing_distance_cm=0)

    with pytest.raises(ValidationError, match="greater than 0"):
        DisplaySettings(screen_width_cm=0)

    with pytest.raises(ValidationError, match="greater than 0"):
        DisplaySettings(screen_width_px=0)

    with pytest.raises(ValidationError, match="greater than 0"):
        DisplaySettings(screen_height_px=0)


def test_visual_angle_geometry_scales_with_degrees_and_viewing_distance() -> None:
    eight_deg_at_80_cm = visual_angle_width_cm(degrees=8.0, viewing_distance_cm=80.0)
    ten_deg_at_80_cm = visual_angle_width_cm(degrees=10.0, viewing_distance_cm=80.0)
    eight_deg_at_100_cm = visual_angle_width_cm(degrees=8.0, viewing_distance_cm=100.0)

    assert eight_deg_at_80_cm == pytest.approx(11.2, abs=0.1)
    assert ten_deg_at_80_cm > eight_deg_at_80_cm
    assert eight_deg_at_100_cm > eight_deg_at_80_cm
    assert visual_angle_width_px(
        degrees=8.0,
        viewing_distance_cm=80.0,
        screen_width_cm=53.0,
        screen_width_px=1920,
    ) == pytest.approx(406, abs=1)


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


def test_stimulus_set_defaults_existing_image_payload_to_image_modality(sample_project) -> None:
    payload = sample_project.stimulus_sets[0].model_dump(mode="python")
    payload.pop("modality", None)

    stimulus_set = StimulusSet.model_validate(payload)

    assert stimulus_set.modality == StimulusModality.IMAGE
    assert stimulus_set.source_dir == "stimuli/original-images/base-set"


def test_word_stimulus_set_trims_and_preserves_duplicate_words() -> None:
    stimulus_set = StimulusSet(
        set_id="word-set",
        name="Word Set",
        modality=StimulusModality.WORD,
        source_dir=None,
        words=[" cat ", "dog", "cat"],
    )

    assert stimulus_set.words == ["cat", "dog", "cat"]
    assert stimulus_set.word_count == 3


def test_word_stimulus_set_rejects_blank_and_overlength_words() -> None:
    with pytest.raises(ValidationError, match="blank entries"):
        StimulusSet(
            set_id="word-set",
            name="Word Set",
            modality=StimulusModality.WORD,
            source_dir=None,
            words=["cat", " "],
        )

    with pytest.raises(ValidationError, match="may not exceed"):
        StimulusSet(
            set_id="word-set",
            name="Word Set",
            modality=StimulusModality.WORD,
            source_dir=None,
            words=["x" * (MAX_WORD_STIMULUS_CHARS + 1)],
        )


def test_word_stimulus_set_rejects_image_payload_fields() -> None:
    with pytest.raises(ValidationError, match="source_dir=None"):
        StimulusSet(
            set_id="word-set",
            name="Word Set",
            modality=StimulusModality.WORD,
            source_dir="stimuli/original-images/word-set",
            words=["cat"],
        )


def test_trigger_settings_default_and_validate_oddball_marker_code() -> None:
    settings = TriggerSettings()

    assert LOCKED_ODDBALL_TRIGGER_CODE == 55
    assert settings.backend == TriggerBackendKind.SERIAL
    assert settings.enabled is True
    assert settings.serial_port == "COM3"
    assert settings.baudrate == 115200
    assert settings.oddball_trigger_code == LOCKED_ODDBALL_TRIGGER_CODE
    assert settings.allow_nonstandard_oddball_trigger_code is False
    assert settings.reset_code is None

    with pytest.raises(ValidationError, match="less than or equal to 255"):
        TriggerSettings(oddball_trigger_code=300)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        TriggerSettings(oddball_trigger_code=0)

    with pytest.raises(ValidationError):
        TriggerSettings(oddball_trigger_code="55")


def test_trigger_settings_reject_nonstandard_oddball_code_without_explicit_override() -> None:
    with pytest.raises(ValidationError, match="locked to 55"):
        TriggerSettings(oddball_trigger_code=88)

    settings = TriggerSettings(
        oddball_trigger_code=88,
        allow_nonstandard_oddball_trigger_code=True,
    )

    assert settings.oddball_trigger_code == 88
    assert settings.allow_nonstandard_oddball_trigger_code is True


def test_project_model_backfills_oddball_trigger_for_legacy_payload(sample_project) -> None:
    payload = sample_project.model_dump(mode="python")
    triggers = payload["settings"]["triggers"]
    triggers.pop("backend", None)
    triggers.pop("enabled", None)
    triggers.pop("serial_port", None)
    triggers.pop("oddball_trigger_code", None)

    loaded = ProjectFile.model_validate(payload)

    assert loaded.settings.triggers.backend == TriggerBackendKind.SERIAL
    assert loaded.settings.triggers.enabled is True
    assert loaded.settings.triggers.serial_port == "COM3"
    assert loaded.settings.triggers.allow_nonstandard_oddball_trigger_code is False
    assert loaded.settings.triggers.oddball_trigger_code == 55


def test_custom_oddball_trigger_code_persists(tmp_path, sample_project) -> None:
    sample_project.settings.triggers.oddball_trigger_code = 88
    sample_project.settings.triggers.allow_nonstandard_oddball_trigger_code = True
    project_path = tmp_path / "project.json"

    save_project_file(sample_project, project_path)
    loaded = load_project_file(project_path)

    assert loaded.settings.triggers.oddball_trigger_code == 88
    assert loaded.settings.triggers.allow_nonstandard_oddball_trigger_code is True
