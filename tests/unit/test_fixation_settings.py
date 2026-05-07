"""Fixation-task model and validation tests."""

from __future__ import annotations

import pytest

from fpvs_studio.core.models import FixationTaskSettings


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


def test_fixation_settings_defaults_match_current_gui_presets() -> None:
    settings = FixationTaskSettings()

    assert settings.enabled is False
    assert settings.accuracy_task_enabled is False
    assert settings.changes_per_sequence == 0
    assert settings.target_count_mode == "fixed"
    assert settings.base_color == "#0000FF"
    assert settings.target_color == "#FF0000"
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
