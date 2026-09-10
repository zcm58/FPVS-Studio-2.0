"""Previously compiled image-pair artifacts cannot bypass retirement checks."""

import pytest

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.run_spec import AttentionalBlinkRunSpec
from fpvs_studio.engines.psychopy_engine import PsychoPyEngine
from fpvs_studio.runtime.preflight import PreflightError, preflight_run_spec


@pytest.fixture
def retired_run(sample_project, sample_project_root):
    ordinary = compile_run_spec(sample_project, refresh_hz=60, project_root=sample_project_root)
    # Reject the loaded legacy layout before accessing assets or hardware.
    return ordinary.model_copy(update={"attentional_blink": AttentionalBlinkRunSpec(
        requested_t1_duration_ms=50, requested_isi_ms=50,
        t1_frames=3, isi_frames=3, t2_frames=9, t2_trigger_code=56,
        t2_presentation=ordinary.presentation.oddball,
    )})


@pytest.mark.parametrize("verify", [False, True])
def test_retired_run_preflight_stops_before_engine_or_asset_access(retired_run, tmp_path, verify):
    with pytest.raises(PreflightError, match="Image-pair.*no longer supported"):
        preflight_run_spec(
            tmp_path / "absent", retired_run, engine=None,
            runtime_options={"verify_refresh_rate": verify, "strict_timing": verify},
        )


def test_direct_engine_call_cannot_open_a_window_for_image_pairs(
    retired_run, tmp_path, monkeypatch,
):
    engine = PsychoPyEngine()
    monkeypatch.setattr(engine, "open_session", lambda **kwargs: pytest.fail("Window opened"))
    with pytest.raises(ValueError, match="Image-pair.*no longer supported"):
        engine.run_condition(retired_run, tmp_path)
