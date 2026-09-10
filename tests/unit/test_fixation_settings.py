"""Fixation-task model and validation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.models import FixationTaskSettings


def test_fixation_visibility_defaults_preserve_existing_projects() -> None:
    assert FixationTaskSettings.model_validate({}).show_cross
    hidden = FixationTaskSettings(
        show_cross=False, enabled=False, accuracy_task_enabled=False,
        participant_tutorial_enabled=False,
    )
    assert not FixationTaskSettings.model_validate_json(hidden.model_dump_json()).show_cross


@pytest.mark.parametrize(
    "task_flag", ["enabled", "accuracy_task_enabled", "participant_tutorial_enabled"]
)
def test_hidden_cross_rejects_active_fixation_tasks(task_flag: str) -> None:
    values = dict(show_cross=False, enabled=False, accuracy_task_enabled=False,
                  participant_tutorial_enabled=False)
    values[task_flag] = True
    with pytest.raises(ValueError, match="Hidden fixation crosses"):
        FixationTaskSettings.model_validate(values)


def test_fixation_settings_reject_randomized_no_repeat_when_range_is_degenerate() -> None:
    with pytest.raises(
        ValueError,
        match="Randomized color changes per condition",
    ):
        FixationTaskSettings(
            enabled=True,
            target_count_mode="randomized",
            target_count_min=4,
            target_count_max=4,
            no_immediate_repeat_count=True,
        )


def test_fixation_settings_fixed_mode_remains_valid() -> None:
    settings = FixationTaskSettings(
        enabled=True,
        target_count_mode="fixed",
        changes_per_sequence=3,
    )

    assert settings.target_count_mode == "fixed"
    assert settings.changes_per_sequence == 3


def test_fixation_settings_keeps_legacy_max_gap_without_range_contract() -> None:
    settings = FixationTaskSettings(
        enabled=True,
        target_count_mode="fixed",
        changes_per_sequence=3,
        min_gap_ms=2000,
        max_gap_ms=1000,
    )

    assert settings.min_gap_ms == 2000
    assert settings.max_gap_ms == 1000


def test_fixation_settings_defaults_match_current_gui_presets() -> None:
    settings = FixationTaskSettings()

    assert settings.enabled is True
    assert settings.accuracy_task_enabled is True
    assert settings.participant_tutorial_enabled is True
    assert settings.changes_per_sequence == 0
    assert settings.target_count_mode == "fixed"
    assert settings.target_count_min == 8
    assert settings.target_count_max == 13
    assert settings.base_color == "#0000FF"
    assert settings.target_color == "#FF0000"
    assert settings.target_duration_ms == 300
    assert settings.response_key == "space"
    assert settings.response_window_seconds == 1.0


def test_fixation_settings_accept_new_alias_for_color_changes_per_condition() -> None:
    settings = FixationTaskSettings.model_validate(
        {
            "enabled": True,
            "target_count_mode": "fixed",
            "color_changes_per_condition": 5,
        }
    )

    assert settings.changes_per_sequence == 5
    assert settings.color_changes_per_condition == 5
    assert settings.model_dump()["changes_per_sequence"] == 5
