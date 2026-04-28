"""Runtime launcher boundary tests."""

from __future__ import annotations

import pytest
from tests.unit.runtime_launcher_helpers import (
    PARTICIPANT_NUMBER,
    StubEngine,
)

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.engines.registry import register_engine, unregister_engine
from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_session,
)
from fpvs_studio.runtime.preflight import PreflightError


def test_launch_settings_default_to_strict_timing_fail_fast() -> None:
    settings = LaunchSettings()

    assert settings.strict_timing is True
    assert settings.strict_timing_warmup is True
    assert settings.timing_miss_threshold_multiplier == 1.5
    assert settings.timing_warmup_frames == 240




def test_launch_session_preflight_rejects_windowed_mode_when_strict_timing_enabled(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-strict-fullscreen", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=35,
        )

        with pytest.raises(PreflightError, match="strict timing requires fullscreen"):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-strict-fullscreen",
                    test_mode=True,
                    fullscreen=False,
                    strict_timing=True,
                ),
            )
    finally:
        unregister_engine("stub-strict-fullscreen")

    assert captures == {}




def test_launch_session_allows_windowed_mode_when_strict_timing_disabled(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-windowed-allowed", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=36,
        )

        summary = launch_session(
            sample_project_root,
            session_plan,
            participant_number=PARTICIPANT_NUMBER,
            launch_settings=LaunchSettings(
                engine_name="stub-windowed-allowed",
                test_mode=True,
                fullscreen=False,
                strict_timing=False,
            ),
        )
    finally:
        unregister_engine("stub-windowed-allowed")

    assert summary.aborted is False
    assert captures["runtime_options"]["fullscreen"] is False
    assert captures["runtime_options"]["strict_timing"] is False




def test_launch_session_rejects_invalid_display_index_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid-display", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=31,
        )

        with pytest.raises(
            LaunchSettingsError,
            match="display_index must be None or a non-negative integer",
        ):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-invalid-display",
                    test_mode=True,
                    display_index=-1,
                ),
            )
    finally:
        unregister_engine("stub-invalid-display")

    assert captures == {}




def test_launch_session_rejects_invalid_serial_baudrate_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid-baud", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=31,
        )

        with pytest.raises(
            LaunchSettingsError,
            match="serial_baudrate must be a positive integer",
        ):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-invalid-baud",
                    test_mode=True,
                    serial_baudrate=0,
                ),
            )
    finally:
        unregister_engine("stub-invalid-baud")

    assert captures == {}




def test_launch_session_rejects_non_boolean_fullscreen_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid-fullscreen", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=32,
        )

        with pytest.raises(
            LaunchSettingsError,
            match="fullscreen must be a boolean",
        ):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-invalid-fullscreen",
                    test_mode=True,
                    fullscreen="yes",  # type: ignore[arg-type]
                ),
            )
    finally:
        unregister_engine("stub-invalid-fullscreen")

    assert captures == {}




def test_launch_session_rejects_non_boolean_strict_timing_warmup_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-invalid-strict-warmup", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=38,
        )

        with pytest.raises(
            LaunchSettingsError,
            match="strict_timing_warmup must be a boolean",
        ):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number=PARTICIPANT_NUMBER,
                launch_settings=LaunchSettings(
                    engine_name="stub-invalid-strict-warmup",
                    test_mode=True,
                    strict_timing_warmup="yes",  # type: ignore[arg-type]
                ),
            )
    finally:
        unregister_engine("stub-invalid-strict-warmup")

    assert captures == {}




def test_launch_session_rejects_blank_participant_number_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-empty-participant", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=33,
        )

        with pytest.raises(LaunchSettingsError, match="participant_number is required"):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number="   ",
                launch_settings=LaunchSettings(
                    engine_name="stub-empty-participant",
                    test_mode=True,
                ),
            )
    finally:
        unregister_engine("stub-empty-participant")

    assert captures == {}




def test_launch_session_rejects_non_digit_participant_number_before_engine_creation(
    sample_project,
    sample_project_root,
) -> None:
    captures: dict[str, object] = {}
    register_engine("stub-bad-participant", lambda: StubEngine(captures))
    try:
        session_plan = compile_session_plan(
            sample_project,
            refresh_hz=60.0,
            project_root=sample_project_root,
            random_seed=34,
        )

        with pytest.raises(
            LaunchSettingsError, match="participant_number must contain digits only"
        ):
            launch_session(
                sample_project_root,
                session_plan,
                participant_number="AB12",
                launch_settings=LaunchSettings(
                    engine_name="stub-bad-participant",
                    test_mode=True,
                ),
            )
    finally:
        unregister_engine("stub-bad-participant")

    assert captures == {}
