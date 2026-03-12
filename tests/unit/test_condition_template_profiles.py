"""Condition-template profile storage and snapshot tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.condition_template_profiles import (
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    built_in_condition_template_profiles,
    delete_condition_template_profile,
    get_condition_template_profile,
    load_condition_template_profile_library,
    list_condition_template_profiles,
    save_condition_template_profile_library,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    ConditionTemplateProfileLibrary,
    FixationTaskSettings,
)
from fpvs_studio.core.paths import (
    CONDITION_TEMPLATE_LIBRARY_FILENAME,
    condition_template_library_path,
)
from fpvs_studio.core.serialization import write_json_file


def test_condition_template_library_is_seeded_with_built_ins(tmp_path) -> None:
    profiles = list_condition_template_profiles(tmp_path)
    profile_ids = {profile.profile_id for profile in profiles}
    profiles_by_id = {profile.profile_id: profile for profile in profiles}

    assert STUDIO_DEFAULT_PROFILE_ID in profile_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in profile_ids
    assert (
        profiles_by_id[STUDIO_DEFAULT_PROFILE_ID].display_name
        == "Default Template 1: Continuous Images"
    )
    assert (
        profiles_by_id[SIXTY_HZ_BLANK_FIXATION_PROFILE_ID].display_name
        == "Default Template 2: 83ms blank"
    )
    assert condition_template_library_path(tmp_path).is_file()
    assert all(profile.built_in for profile in profiles)


def test_condition_template_library_migrates_legacy_root_file_idempotently(tmp_path) -> None:
    legacy_path = tmp_path / CONDITION_TEMPLATE_LIBRARY_FILENAME
    write_json_file(legacy_path, ConditionTemplateProfileLibrary())

    migrated_once = load_condition_template_profile_library(tmp_path)
    migrated_twice = load_condition_template_profile_library(tmp_path)

    assert condition_template_library_path(tmp_path).is_file()
    assert not legacy_path.exists()
    assert migrated_once == migrated_twice
    migrated_ids = {profile.profile_id for profile in migrated_once.profiles}
    assert STUDIO_DEFAULT_PROFILE_ID in migrated_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in migrated_ids


def test_condition_template_library_save_load_stays_under_templates_dir(tmp_path) -> None:
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

    save_condition_template_profile_library(
        tmp_path,
        ConditionTemplateProfileLibrary(profiles=[user_profile]),
    )
    loaded = load_condition_template_profile_library(tmp_path)

    assert condition_template_library_path(tmp_path).is_file()
    assert not (tmp_path / CONDITION_TEMPLATE_LIBRARY_FILENAME).exists()
    loaded_ids = {profile.profile_id for profile in loaded.profiles}
    assert "custom-profile" in loaded_ids


def test_built_in_templates_share_defaults_except_duty_cycle() -> None:
    profiles_by_id = {
        profile.profile_id: profile for profile in built_in_condition_template_profiles()
    }
    template_one = profiles_by_id[STUDIO_DEFAULT_PROFILE_ID]
    template_two = profiles_by_id[SIXTY_HZ_BLANK_FIXATION_PROFILE_ID]

    assert template_one.defaults.condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert template_two.defaults.condition.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert template_one.defaults.condition.sequence_count == 1
    assert template_two.defaults.condition.sequence_count == 1
    assert template_one.defaults.condition.oddball_cycle_repeats_per_sequence == 146
    assert template_two.defaults.condition.oddball_cycle_repeats_per_sequence == 146
    assert template_one.defaults.display.preferred_refresh_hz is None
    assert template_two.defaults.display.preferred_refresh_hz is None

    fixation_one = template_one.defaults.fixation_task
    fixation_two = template_two.defaults.fixation_task
    assert fixation_one == fixation_two
    assert fixation_one.enabled is True
    assert fixation_one.accuracy_task_enabled is True
    assert fixation_one.target_count_mode == "randomized"
    assert fixation_one.target_count_min == 6
    assert fixation_one.target_count_max == 8
    assert fixation_one.no_immediate_repeat_count is True
    assert fixation_one.changes_per_sequence == 7
    assert fixation_one.target_duration_ms == 250
    assert fixation_one.min_gap_ms == 1000
    assert fixation_one.max_gap_ms == 3000


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
