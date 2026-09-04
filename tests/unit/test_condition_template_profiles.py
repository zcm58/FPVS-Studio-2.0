"""Condition-template profile storage and snapshot tests."""

from __future__ import annotations

import json

import pytest

from fpvs_studio.core.condition_template_profiles import (
    SINUSOIDAL_CONTRAST_PROFILE_ID,
    SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
    STUDIO_DEFAULT_PROFILE_ID,
    apply_condition_template_profile_to_settings,
    built_in_condition_template_profiles,
    delete_condition_template_profile,
    get_condition_template_profile,
    list_condition_template_profiles,
    load_condition_template_profile_library,
    save_condition_template_profile_library,
    upsert_condition_template_profile,
)
from fpvs_studio.core.enums import DutyCycleMode, ImageGeometryMode, StimulusTransform
from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    ConditionTemplateProfileLibrary,
    FixationTaskSettings,
    ProjectPresentationSettings,
    ProjectSettings,
    StimulusPresentationDefaults,
)
from fpvs_studio.core.paths import (
    APP_DATA_DIRNAME,
    CONDITION_TEMPLATE_LIBRARY_FILENAME,
    TEMPLATES_DIRNAME,
    condition_template_library_path,
)
from fpvs_studio.core.serialization import write_json_file


def test_condition_template_library_is_seeded_with_built_ins(tmp_path) -> None:
    profiles = list_condition_template_profiles(tmp_path)
    profile_ids = {profile.profile_id for profile in profiles}
    profiles_by_id = {profile.profile_id: profile for profile in profiles}

    assert STUDIO_DEFAULT_PROFILE_ID in profile_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in profile_ids
    assert SINUSOIDAL_CONTRAST_PROFILE_ID in profile_ids
    assert profiles_by_id[STUDIO_DEFAULT_PROFILE_ID].display_name == "Continuous Images"
    assert (
        profiles_by_id[SIXTY_HZ_BLANK_FIXATION_PROFILE_ID].display_name
        == "50% Blank Between Images"
    )
    assert profiles_by_id[SINUSOIDAL_CONTRAST_PROFILE_ID].display_name == "Contrast Modulation"
    assert condition_template_library_path(tmp_path).is_file()
    assert condition_template_library_path(tmp_path).parent == (
        tmp_path / APP_DATA_DIRNAME / TEMPLATES_DIRNAME
    )
    assert not (tmp_path / TEMPLATES_DIRNAME).exists()
    assert all(profile.built_in for profile in profiles)


def test_condition_template_library_migrates_legacy_root_file_idempotently(tmp_path) -> None:
    legacy_path = tmp_path / CONDITION_TEMPLATE_LIBRARY_FILENAME
    write_json_file(legacy_path, ConditionTemplateProfileLibrary())

    migrated_once = load_condition_template_profile_library(tmp_path)
    migrated_twice = load_condition_template_profile_library(tmp_path)

    assert condition_template_library_path(tmp_path).is_file()
    assert not legacy_path.exists()
    assert not (tmp_path / TEMPLATES_DIRNAME).exists()
    assert migrated_once == migrated_twice
    migrated_ids = {profile.profile_id for profile in migrated_once.profiles}
    assert STUDIO_DEFAULT_PROFILE_ID in migrated_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in migrated_ids


def test_condition_template_library_migrates_legacy_top_level_templates_dir(
    tmp_path,
) -> None:
    legacy_templates_dir = tmp_path / TEMPLATES_DIRNAME
    legacy_templates_dir.mkdir()
    legacy_path = legacy_templates_dir / CONDITION_TEMPLATE_LIBRARY_FILENAME
    write_json_file(legacy_path, ConditionTemplateProfileLibrary())

    migrated = load_condition_template_profile_library(tmp_path)

    assert condition_template_library_path(tmp_path).is_file()
    assert not legacy_path.exists()
    assert not legacy_templates_dir.exists()
    migrated_ids = {profile.profile_id for profile in migrated.profiles}
    assert STUDIO_DEFAULT_PROFILE_ID in migrated_ids
    assert SIXTY_HZ_BLANK_FIXATION_PROFILE_ID in migrated_ids


def test_condition_template_library_migrates_legacy_user_presentation_defaults(
    tmp_path,
) -> None:
    user_profile = ConditionTemplateProfile(
        profile_id="legacy-user-profile",
        display_name="Legacy User Profile",
        built_in=False,
    )
    payload = ConditionTemplateProfileLibrary(profiles=[user_profile]).model_dump(mode="json")
    payload["schema_version"] = "1.0.0"
    payload["profiles"][0]["defaults"].pop("presentation")
    library_path = condition_template_library_path(tmp_path)
    library_path.parent.mkdir(parents=True)
    library_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_condition_template_profile_library(tmp_path)

    legacy = next(
        profile for profile in loaded.profiles if profile.profile_id == "legacy-user-profile"
    )
    presentation = legacy.defaults.presentation
    assert loaded.schema_version.value == "1.1.0"
    assert presentation.pre_stream_fixation_seconds == 0.0
    assert presentation.defaults.image_geometry.mode == ImageGeometryMode.NATURAL_ASPECT
    assert presentation.defaults.image_geometry.width_degrees == 5.0
    assert presentation.defaults.text_height.legacy_stimulus_width_fraction == 0.25
    rewritten = json.loads(library_path.read_text(encoding="utf-8"))
    assert rewritten["schema_version"] == "1.1.0"
    assert (
        rewritten["profiles"][-1]["defaults"]["presentation"]["pre_stream_fixation_seconds"] == 0.0
    )


def test_condition_template_library_save_load_stays_under_app_templates_dir(
    tmp_path,
) -> None:
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
    assert condition_template_library_path(tmp_path).parent == (
        tmp_path / APP_DATA_DIRNAME / TEMPLATES_DIRNAME
    )
    assert not (tmp_path / CONDITION_TEMPLATE_LIBRARY_FILENAME).exists()
    assert not (tmp_path / TEMPLATES_DIRNAME).exists()
    loaded_ids = {profile.profile_id for profile in loaded.profiles}
    assert "custom-profile" in loaded_ids


def test_built_in_templates_share_protocol_and_fixation_defaults() -> None:
    profiles_by_id = {
        profile.profile_id: profile for profile in built_in_condition_template_profiles()
    }
    template_one = profiles_by_id[STUDIO_DEFAULT_PROFILE_ID]
    template_two = profiles_by_id[SIXTY_HZ_BLANK_FIXATION_PROFILE_ID]
    template_three = profiles_by_id[SINUSOIDAL_CONTRAST_PROFILE_ID]

    assert template_one.defaults.condition.duty_cycle_mode == DutyCycleMode.CONTINUOUS
    assert template_two.defaults.condition.duty_cycle_mode == DutyCycleMode.BLANK_50
    assert template_three.defaults.condition.duty_cycle_mode == DutyCycleMode.SINUSOIDAL
    assert template_one.defaults.condition.sequence_count == 1
    assert template_two.defaults.condition.sequence_count == 1
    assert template_three.defaults.condition.sequence_count == 1
    assert template_one.defaults.condition.oddball_cycle_repeats_per_sequence == 146
    assert template_two.defaults.condition.oddball_cycle_repeats_per_sequence == 146
    assert template_three.defaults.condition.oddball_cycle_repeats_per_sequence == 146
    assert template_one.defaults.condition.target_repeats_per_image == 7
    assert template_two.defaults.condition.target_repeats_per_image == 7
    assert template_three.defaults.condition.target_repeats_per_image == 7
    assert template_one.defaults.display.preferred_refresh_hz is None
    assert template_two.defaults.display.preferred_refresh_hz is None
    assert template_three.defaults.display.preferred_refresh_hz is None
    assert template_one.defaults.display.background_color is None
    assert template_two.defaults.display.background_color is None
    assert template_three.defaults.display.background_color == "#808080"

    fixation_one = template_one.defaults.fixation_task
    fixation_two = template_two.defaults.fixation_task
    fixation_three = template_three.defaults.fixation_task
    assert fixation_one == fixation_two
    assert fixation_one == fixation_three
    assert fixation_one.enabled is True
    assert fixation_one.accuracy_task_enabled is True
    assert fixation_one.target_count_mode == "randomized"
    assert fixation_one.target_count_min == 8
    assert fixation_one.target_count_max == 13
    assert fixation_one.no_immediate_repeat_count is True
    assert fixation_one.changes_per_sequence == 7
    assert fixation_one.target_duration_ms == 300
    assert fixation_one.min_gap_ms == 1000
    assert fixation_one.max_gap_ms == 3000
    assert template_one.defaults.presentation.pre_stream_fixation_seconds == 2.0
    assert template_two.defaults.presentation == template_one.defaults.presentation
    assert template_three.defaults.presentation == template_one.defaults.presentation


def test_condition_template_profile_applies_optional_background_snapshot() -> None:
    original = ProjectSettings()
    original.display.background_color = "#123456"
    continuous = next(
        profile
        for profile in built_in_condition_template_profiles()
        if profile.profile_id == STUDIO_DEFAULT_PROFILE_ID
    )
    sinusoidal = next(
        profile
        for profile in built_in_condition_template_profiles()
        if profile.profile_id == SINUSOIDAL_CONTRAST_PROFILE_ID
    )

    unchanged = apply_condition_template_profile_to_settings(original, continuous)
    applied = apply_condition_template_profile_to_settings(original, sinusoidal)

    assert unchanged.display.background_color == "#123456"
    assert applied.display.background_color == "#808080"
    assert applied.condition_defaults.duty_cycle_mode == DutyCycleMode.SINUSOIDAL


def test_legacy_current_schema_profile_without_background_loads_unchanged(tmp_path) -> None:
    user_profile = ConditionTemplateProfile(
        profile_id="legacy-no-background",
        display_name="Legacy No Background",
    )
    payload = ConditionTemplateProfileLibrary(profiles=[user_profile]).model_dump(mode="json")
    payload["profiles"][0]["defaults"]["display"].pop("background_color")
    library_path = condition_template_library_path(tmp_path)
    library_path.parent.mkdir(parents=True)
    library_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_condition_template_profile_library(tmp_path)
    profile = next(item for item in loaded.profiles if item.profile_id == "legacy-no-background")

    assert profile.defaults.display.background_color is None


def test_condition_template_profile_applies_presentation_snapshot() -> None:
    profile = ConditionTemplateProfile(
        profile_id="presentation-profile",
        display_name="Presentation Profile",
        defaults=ConditionTemplateDefaults(
            presentation=ProjectPresentationSettings(
                pre_stream_fixation_seconds=1.25,
                defaults=StimulusPresentationDefaults(
                    transform=StimulusTransform.MIRROR_VERTICAL,
                ),
            )
        ),
    )

    applied = apply_condition_template_profile_to_settings(ProjectSettings(), profile)

    assert applied.presentation == profile.defaults.presentation
    assert applied.presentation is not profile.defaults.presentation


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
