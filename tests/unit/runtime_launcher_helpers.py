"""Shared helpers for runtime launcher boundary tests."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from fpvs_studio.core.enums import RunMode
from fpvs_studio.core.execution import (
    FrameIntervalRecord,
    ResponseRecord,
    RunExecutionSummary,
    RuntimeMetadata,
)
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.engines.base import PresentationEngine
from fpvs_studio.triggers.base import TriggerBackend

PARTICIPANT_NUMBER = "0007"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class StubEngine(PresentationEngine):
    """Engine stub used to exercise the runtime launcher boundary."""

    def __init__(self, captures: dict[str, object]) -> None:
        self._captures = captures

    @property
    def engine_id(self) -> str:
        return "stub"

    def probe_displays(self) -> list[dict[str, object]]:
        return []

    def open_session(
        self,
        *,
        runtime_options: Mapping[str, object] | None = None,
    ) -> None:
        self._captures["open_count"] = int(self._captures.get("open_count", 0)) + 1
        self._captures["runtime_options"] = dict(runtime_options or {})

    def show_transition_screen(
        self,
        *,
        heading: str,
        body: str | None = None,
        countdown_seconds: float | None = None,
        continue_key: str | None = None,
        continue_prompt: str | None = None,
    ) -> bool:
        self._captures.setdefault("transitions", []).append(
            {
                "heading": heading,
                "body": body,
                "countdown_seconds": countdown_seconds,
                "continue_key": continue_key,
                "continue_prompt": continue_prompt,
            }
        )
        return bool(self._captures.get("abort_on_transition", False))

    def show_block_break_screen(
        self,
        *,
        completed_block_index: int,
        total_block_count: int,
        next_block_index: int,
    ) -> bool:
        self._captures.setdefault("block_breaks", []).append(
            {
                "completed_block_index": completed_block_index,
                "total_block_count": total_block_count,
                "next_block_index": next_block_index,
            }
        )
        return bool(self._captures.get("abort_on_block_break", False))

    def show_condition_feedback_screen(
        self,
        *,
        heading: str,
        body: str,
        continue_key: str,
    ) -> bool:
        self._captures.setdefault("condition_feedback", []).append(
            {
                "heading": heading,
                "body": body,
                "continue_key": continue_key,
            }
        )
        return False

    def run_condition(
        self,
        run_spec: RunSpec,
        project_root: Path,
        *,
        runtime_options: Mapping[str, object] | None = None,
        trigger_backend: TriggerBackend | None = None,
    ) -> RunExecutionSummary:
        self._captures.setdefault("run_ids", []).append(run_spec.run_id)
        self._captures.setdefault("project_roots", []).append(project_root)
        self._captures.setdefault("condition_instructions", []).append(
            run_spec.condition.instructions_text
        )

        if trigger_backend is not None:
            for trigger_event in run_spec.trigger_events:
                trigger_backend.send_trigger(
                    trigger_event.code,
                    frame_index=trigger_event.frame_index,
                    label=trigger_event.label,
                    time_s=0.0,
                )

        response_log = []
        if run_spec.fixation_events:
            first_event = run_spec.fixation_events[0]
            response_log.append(
                ResponseRecord(
                    response_index=0,
                    key=run_spec.fixation.response_key,
                    frame_index=first_event.start_frame,
                    time_s=0.25,
                )
            )

        if bool(self._captures.get("timing_abort_on_first_run", False)) and not bool(
            self._captures.get("timing_abort_emitted", False)
        ):
            self._captures["timing_abort_emitted"] = True
            return RunExecutionSummary(
                project_id=run_spec.project_id,
                session_id=None,
                run_id=run_spec.run_id,
                condition_id=run_spec.condition.condition_id,
                condition_name=run_spec.condition.name,
                engine_name="stub",
                run_mode=(
                    RunMode.TEST
                    if bool((runtime_options or {}).get("test_mode"))
                    else RunMode.SESSION
                ),
                started_at=datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 3, 7, 12, 0, 1, tzinfo=timezone.utc),
                completed_frames=3,
                aborted=True,
                abort_reason=(
                    "Strict timing aborted run during run: frame interval at index 1 was "
                    "0.040000 s, exceeding 1.50x expected 0.016667 s."
                ),
                runtime_metadata=RuntimeMetadata(
                    engine_name="stub",
                    requested_refresh_hz=run_spec.display.refresh_hz,
                    actual_refresh_hz=59.0,
                    frame_interval_recording=True,
                    test_mode=bool((runtime_options or {}).get("test_mode")),
                    timing_qc_expected_interval_s=1.0 / run_spec.display.refresh_hz,
                    timing_qc_threshold_interval_s=1.5 / run_spec.display.refresh_hz,
                    timing_qc_warmup_frames=240,
                    timing_qc_measured_refresh_hz=59.0,
                    timing_qc_max_interval_s=0.04,
                    timing_qc_first_bad_frame_index=1,
                    timing_qc_strict_abort=True,
                ),
                frame_intervals=[
                    FrameIntervalRecord(
                        frame_index=0, interval_s=1.0 / run_spec.display.refresh_hz
                    ),
                    FrameIntervalRecord(frame_index=1, interval_s=0.04),
                ],
                response_log=response_log,
            )

        return RunExecutionSummary(
            project_id=run_spec.project_id,
            session_id=None,
            run_id=run_spec.run_id,
            condition_id=run_spec.condition.condition_id,
            condition_name=run_spec.condition.name,
            engine_name="stub",
            run_mode=(
                RunMode.TEST if bool((runtime_options or {}).get("test_mode")) else RunMode.SESSION
            ),
            started_at=datetime(2026, 3, 7, 12, 0, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 3, 7, 12, 0, 5, tzinfo=timezone.utc),
            completed_frames=run_spec.display.total_frames,
            aborted=False,
            runtime_metadata=RuntimeMetadata(
                engine_name="stub",
                requested_refresh_hz=run_spec.display.refresh_hz,
                actual_refresh_hz=run_spec.display.refresh_hz,
                frame_interval_recording=True,
                test_mode=bool((runtime_options or {}).get("test_mode")),
            ),
            frame_intervals=[
                FrameIntervalRecord(
                    frame_index=0,
                    interval_s=1.0 / run_spec.display.refresh_hz,
                )
            ],
            response_log=response_log,
        )

    def show_completion_screen(
        self,
        *,
        completed_condition_count: int,
        total_condition_count: int,
        was_aborted: bool,
    ) -> bool:
        self._captures.setdefault("completion_screens", []).append(
            {
                "completed_condition_count": completed_condition_count,
                "total_condition_count": total_condition_count,
                "was_aborted": was_aborted,
            }
        )
        return False

    def close_session(self) -> None:
        self._captures["close_count"] = int(self._captures.get("close_count", 0)) + 1

    def abort(self) -> None:
        self._captures["abort_called"] = True


