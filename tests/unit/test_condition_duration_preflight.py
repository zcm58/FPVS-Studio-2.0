"""Runtime independently checks the compiled requested-duration contract."""

from __future__ import annotations

import pytest

from fpvs_studio.core.compiler import compile_run_spec
from fpvs_studio.core.condition_timing import propose_condition_timing
from fpvs_studio.runtime.preflight import PreflightError, _validate_display_refresh_timing


def test_preflight_rejects_mutated_duration_or_old_schema(sample_project, sample_project_root):
    condition_id = sample_project.conditions[0].condition_id
    project = propose_condition_timing(
        sample_project, durations={condition_id: 120}, refresh_hz=60,
    )
    run = compile_run_spec(project, refresh_hz=60, project_root=sample_project_root)
    _validate_display_refresh_timing(run)
    changed_duration = run.model_copy(deep=True)
    changed_duration.condition.requested_duration_seconds = 121
    with pytest.raises(PreflightError, match="requested stream duration"):
        _validate_display_refresh_timing(changed_duration)
    changed_schema = run.model_copy(deep=True)
    changed_schema.schema_version = "1.1.0"
    with pytest.raises(PreflightError, match="requested stream duration"):
        _validate_display_refresh_timing(changed_schema)
