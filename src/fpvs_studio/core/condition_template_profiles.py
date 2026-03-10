"""App-level condition-template profile storage and project snapshot helpers."""

from __future__ import annotations

from pathlib import Path

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import (
    Condition,
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateDisplayDefaults,
    ConditionTemplateProfile,
    ConditionTemplateProfileLibrary,
    FixationTaskSettings,
    ProjectSettings,
)
from fpvs_studio.core.paths import condition_template_library_path
from fpvs_studio.core.serialization import read_json_file, write_json_file

STUDIO_DEFAULT_PROFILE_ID = "studio-default-v1"
SIXTY_HZ_BLANK_FIXATION_PROFILE_ID = "sixty-hz-blank50-fixation-v1"


def _shared_fixation_defaults() -> FixationTaskSettings:
    return FixationTaskSettings(
        enabled=True,
        accuracy_task_enabled=True,
        target_count_mode="randomized",
        target_count_min=6,
        target_count_max=8,
        no_immediate_repeat_count=True,
        changes_per_sequence=7,
        target_duration_ms=250,
        min_gap_ms=1000,
        max_gap_ms=3000,
    )


def _built_in_profile(
    *,
    profile_id: str,
    display_name: str,
    description: str,
    duty_cycle_mode: DutyCycleMode,
) -> ConditionTemplateProfile:
    return ConditionTemplateProfile(
        profile_id=profile_id,
        display_name=display_name,
        description=description,
        built_in=True,
        defaults=ConditionTemplateDefaults(
            condition=ConditionDefaults(
                duty_cycle_mode=duty_cycle_mode,
                sequence_count=1,
                oddball_cycle_repeats_per_sequence=146,
            ),
            display=ConditionTemplateDisplayDefaults(preferred_refresh_hz=None),
            fixation_task=_shared_fixation_defaults(),
        ),
    )


def built_in_condition_template_profiles() -> list[ConditionTemplateProfile]:
    """Return built-in condition-template profiles shipped with the app."""

    return [
        _built_in_profile(
            profile_id=STUDIO_DEFAULT_PROFILE_ID,
            display_name="Default Template 1: Continuous Images",
            description=(
                "Continuous-image duty cycle template with fullscreen display defaults and "
                "fixation cross accuracy task defaults."
            ),
            duty_cycle_mode=DutyCycleMode.CONTINUOUS,
        ),
        _built_in_profile(
            profile_id=SIXTY_HZ_BLANK_FIXATION_PROFILE_ID,
            display_name="Default Template 2: 83ms blank",
            description=(
                "83 ms blank (50% blank duty cycle) template with fullscreen display defaults "
                "and fixation cross accuracy task defaults."
            ),
            duty_cycle_mode=DutyCycleMode.BLANK_50,
        ),
    ]


def _normalize_library(
    library: ConditionTemplateProfileLibrary,
) -> ConditionTemplateProfileLibrary:
    built_in_profiles = {
        profile.profile_id: profile for profile in built_in_condition_template_profiles()
    }
    user_profiles: dict[str, ConditionTemplateProfile] = {}
    for profile in library.profiles:
        if profile.profile_id in built_in_profiles:
            continue
        user_profiles[profile.profile_id] = profile.model_copy(update={"built_in": False})
    ordered_profiles = [
        *built_in_profiles.values(),
        *sorted(user_profiles.values(), key=lambda item: item.profile_id),
    ]
    return ConditionTemplateProfileLibrary(profiles=ordered_profiles)


def load_condition_template_profile_library(root_dir: Path) -> ConditionTemplateProfileLibrary:
    """Load the app-level condition-template library and seed built-ins when needed."""

    library_path = condition_template_library_path(Path(root_dir))
    if library_path.is_file():
        library = read_json_file(library_path, ConditionTemplateProfileLibrary)
    else:
        library = ConditionTemplateProfileLibrary()
    normalized = _normalize_library(library)
    if normalized != library or not library_path.is_file():
        write_json_file(library_path, normalized)
    return normalized


def save_condition_template_profile_library(
    root_dir: Path,
    library: ConditionTemplateProfileLibrary,
) -> ConditionTemplateProfileLibrary:
    """Persist a normalized app-level condition-template library."""

    normalized = _normalize_library(library)
    write_json_file(condition_template_library_path(Path(root_dir)), normalized)
    return normalized


def list_condition_template_profiles(root_dir: Path) -> list[ConditionTemplateProfile]:
    """Return all condition-template profiles from the app-level library."""

    return load_condition_template_profile_library(root_dir).profiles


def get_condition_template_profile(root_dir: Path, profile_id: str) -> ConditionTemplateProfile:
    """Return one condition-template profile by id."""

    for profile in list_condition_template_profiles(root_dir):
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(f"Unknown condition profile '{profile_id}'.")


def upsert_condition_template_profile(
    root_dir: Path,
    profile: ConditionTemplateProfile,
) -> ConditionTemplateProfileLibrary:
    """Create or update one user-defined condition-template profile."""

    normalized_profile = profile.model_copy(update={"built_in": False})
    library = load_condition_template_profile_library(root_dir)
    if any(
        item.profile_id == normalized_profile.profile_id and item.built_in
        for item in library.profiles
    ):
        raise ValueError("Built-in condition templates are read-only.")

    updated_profiles: list[ConditionTemplateProfile] = []
    replaced = False
    for item in library.profiles:
        if item.profile_id == normalized_profile.profile_id:
            updated_profiles.append(normalized_profile)
            replaced = True
            continue
        updated_profiles.append(item)
    if not replaced:
        updated_profiles.append(normalized_profile)
    return save_condition_template_profile_library(
        root_dir,
        ConditionTemplateProfileLibrary(profiles=updated_profiles),
    )


def delete_condition_template_profile(
    root_dir: Path,
    profile_id: str,
) -> ConditionTemplateProfileLibrary:
    """Delete one user-defined condition-template profile."""

    library = load_condition_template_profile_library(root_dir)
    target = next((item for item in library.profiles if item.profile_id == profile_id), None)
    if target is None:
        return library
    if target.built_in:
        raise ValueError("Built-in condition templates cannot be deleted.")
    return save_condition_template_profile_library(
        root_dir,
        ConditionTemplateProfileLibrary(
            profiles=[item for item in library.profiles if item.profile_id != profile_id],
        ),
    )


def apply_condition_template_profile_to_settings(
    settings: ProjectSettings,
    profile: ConditionTemplateProfile,
) -> ProjectSettings:
    """Apply one profile snapshot to project settings."""

    display = settings.display.model_copy(
        update={"preferred_refresh_hz": profile.defaults.display.preferred_refresh_hz}
    )
    return settings.model_copy(
        update={
            "condition_profile_id": profile.profile_id,
            "condition_defaults": profile.defaults.condition.model_copy(deep=True),
            "display": display,
            "fixation_task": profile.defaults.fixation_task.model_copy(deep=True),
        }
    )


def apply_condition_defaults_to_condition(
    condition: Condition,
    defaults: ConditionDefaults,
) -> Condition:
    """Apply project condition-default values to one condition."""

    return condition.model_copy(
        update={
            "duty_cycle_mode": defaults.duty_cycle_mode,
            "sequence_count": defaults.sequence_count,
            "oddball_cycle_repeats_per_sequence": defaults.oddball_cycle_repeats_per_sequence,
        }
    )
