"""Condition-template profile storage and snapshot tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    built_in_condition_template_profiles,
    delete_condition_template_profile,
    get_condition_template_profile,
    list_condition_template_profiles,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    FixationTaskSettings,
)
from fpvs_studio.core.paths import condition_template_library_path


def test_condition_template_library_is_seeded_with_built_ins(tmp_path) -> None:
    profiles = list_condition_template_profiles(tmp_path)
    profile_ids = {profile.profile_id for profile in profiles}

    assert STUDIO_DEFAULT_PROFILE_ID in profile_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in profile_ids
    assert condition_template_library_path(tmp_path).is_file()
    assert all(profile.built_in for profile in profiles)


def test_condition_template_profile_upsert_and_delete_round_trip(tmp_path) -> None:
    user_profile = ConditionTemplateProfile(
        profile_id="custom-profile",
        display_name="Custom Profile",
        description="User profile",
        built_in=False,
        defaults=ConditionTemplateDefaults(
            condition=ConditionDefaults(
                duty_cycle_mode=DutyCycleMode.BLANK_50,
                sequence_count=3,
                oddball_cycle_repeats_per_sequence=101,
            ),
            display=ConditionTemplateDisplayDefaults(preferred_refresh_hz=120.0),
            fixation_task=FixationTaskSettings(
                enabled=True,
                accuracy_task_enabled=True,
                changes_per_sequence=4,
                target_duration_ms=350,
                min_gap_ms=900,
                max_gap_ms=2500,
            ),
        ),
    )

    upsert_condition_template_profile(tmp_path, user_profile)
    loaded = get_condition_template_profile(tmp_path, "custom-profile")
    assert loaded.profile_id == "custom-profile"
    assert loaded.built_in is False
    assert loaded.defaults.condition.sequence_count == 3
    assert loaded.defaults.display.preferred_refresh_hz == 120.0

    delete_condition_template_profile(tmp_path, "custom-profile")
    remaining_ids = {profile.profile_id for profile in list_condition_template_profiles(tmp_path)}
    assert "custom-profile" not in remaining_ids


def test_condition_template_built_ins_are_read_only(tmp_path) -> None:
    built_in_profile = built_in_condition_template_profiles()[0]
    edited_built_in = built_in_profile.model_copy(
        update={"display_name": "Edited Built-in", "built_in": False}
    )

    with pytest.raises(ValueError, match="read-only"):
        upsert_condition_template_profile(tmp_path, edited_built_in)

    with pytest.raises(ValueError, match="cannot be deleted"):
        delete_condition_template_profile(tmp_path, built_in_profile.profile_id)
