"""Compare a Unicorn Recorder BDF with a single-run Studio acquisition log."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from itertools import pairwise
from math import isclose, isfinite, sqrt
from pathlib import Path
from statistics import fmean, linear_regression

from pydantic import ValidationError

from fpvs_studio.core.execution import AcquisitionEvidence, TriggerRecord
from fpvs_studio.tools.unicorn_bdf import UnicornBdf, read_unicorn_bdf


def _gaps(values: Sequence[int]) -> str:
    counts = Counter(right - left for left, right in pairwise(values))
    return ", ".join(f"{gap} ({count}x)" for gap, count in sorted(counts.items())) or "unavailable"


def _interval_stats_ms(times: Sequence[float]) -> str:
    intervals_ms = [(right - left) * 1000 for left, right in pairwise(times)]
    if not intervals_ms:
        return "unavailable"
    return f"{min(intervals_ms):.3f} / {fmean(intervals_ms):.3f} / {max(intervals_ms):.3f} ms"


def _callback_times(events: Sequence[TriggerRecord]) -> list[float] | None:
    times: list[float] = []
    for event in events:
        seconds = event.time_s
        if seconds is None or not isfinite(seconds) or (times and seconds <= times[-1]):
            return None
        times.append(seconds)
    return times


def _sample_check(
    label: str, indices: Sequence[int] | None, marker_samples: Sequence[int],
) -> tuple[str, int]:
    if indices is None:
        return f"- {label}: channel unavailable", 0
    count = len(indices)
    if not marker_samples:
        return f"- {label}: {count} in file", 0
    first, last = marker_samples[0], marker_samples[-1]
    in_span = sum(first <= index <= last for index in indices)
    return f"- {label}: {count} in file, {in_span} in saved marker span", in_span


def _drift_lines(
    callback_times: Sequence[float], marker_samples: Sequence[int], sample_rate_hz: float,
) -> list[str]:
    elapsed = [seconds - callback_times[0] for seconds in callback_times]
    samples = [index - marker_samples[0] for index in marker_samples]
    slope, intercept = linear_regression(elapsed, samples)
    residuals_ms = [
        ((sample - intercept) / slope - seconds) * 1000
        for sample, seconds in zip(samples, elapsed, strict=True)
    ]
    bdf_elapsed = samples[-1] / sample_rate_hz
    relative_rate_error = slope / sample_rate_hz - 1
    return [
        f"- Matched markers: {len(samples)}",
        f"- First-to-last Studio callback span: {elapsed[-1]:.6f} s",
        f"- First-to-last nominal BDF span: {bdf_elapsed:.6f} s",
        f"- Endpoint drift (BDF minus Studio): {(bdf_elapsed - elapsed[-1]) * 1000:+.3f} ms",
        f"- Apparent sample rate relative to Studio: {slope:.6f} samples/s",
        f"- Fitted drift per 120 s: {relative_rate_error * 120_000:+.3f} ms "
        f"({relative_rate_error * 1e6:+.1f} ppm)",
        f"- Fit residual RMS: {sqrt(fmean(value**2 for value in residuals_ms)):.3f} ms",
        f"- Fit residual range: {min(residuals_ms):+.3f} to {max(residuals_ms):+.3f} ms",
    ]


def build_timing_report(
    evidence: AcquisitionEvidence,
    bdf: UnicornBdf,
    *,
    bdf_name: str,
    log_name: str,
    refresh_hz: float,
    oddball_hz: float,
    oddball_code: int,
) -> str:
    """Render a read-only reconciliation and software-relative timing report."""
    if evidence.recording.effective_backend != "unicorn_udp" or len(evidence.runs) != 1:
        raise ValueError("Provide a Unicorn UDP Studio acquisition log with exactly one run.")
    run = evidence.runs[0]
    sent = [event for event in run.attempted_events if event.status == "sent"]
    other_attempts = len(run.attempted_events) - len(sent)
    sent_codes = [event.code for event in sent]
    marker_samples = [sample for sample, _ in bdf.markers]
    saved_codes = [code for _, code in bdf.markers]
    codes_match = sent_codes == saved_codes
    callback_times = _callback_times(sent)
    oddball_frames = [event.frame_index for event in sent if event.code == oddball_code]
    oddball_samples = [sample for sample, code in bdf.markers if code == oddball_code]
    oddball_callbacks = []
    if callback_times is not None:
        oddball_callbacks = [
            seconds
            for event, seconds in zip(sent, callback_times, strict=True)
            if event.code == oddball_code
        ]
    frame_gap = refresh_hz / oddball_hz
    observed_frame_gaps = [right - left for left, right in pairwise(oddball_frames)]
    cadence = "unavailable"
    if observed_frame_gaps:
        cadence_matches = all(
            isclose(gap, frame_gap, rel_tol=0, abs_tol=1e-9) for gap in observed_frame_gaps
        )
        cadence = "yes" if cadence_matches else "no"
    counter_line, counter_breaks = _sample_check(
        "Counter discontinuities", bdf.counter_discontinuities, marker_samples,
    )
    validity_line, invalid_samples = _sample_check(
        "Invalid samples", bdf.invalid_samples, marker_samples,
    )
    frame_count = str(run.completed_frames) if run.completed_frames is not None else "unavailable"
    lines = [
        "# Unicorn timing report",
        "",
        f"- Recording: `{bdf_name}`",
        f"- Studio log: `{log_name}`",
        f"- Studio run: `{run.run_id}` ({run.state})",
        f"- BDF sample rate: {bdf.sample_rate_hz:g} Hz nominal, {bdf.sample_count:,} samples",
        "",
        "## Studio playback",
        "",
        f"- Reference refresh: {refresh_hz:g} Hz",
        f"- Target oddball: code `{oddball_code}`, {oddball_hz:g} Hz "
        f"({1000 / oddball_hz:.6f} ms, {frame_gap:g} frames)",
        f"- Completed frames: {frame_count}",
        f"- Oddball frame gaps (count): {_gaps(oddball_frames)}",
        f"- All oddball frame gaps match target: {cadence}",
        f"- Oddball callback intervals (min / mean / max): {_interval_stats_ms(oddball_callbacks)}",
        "- The acquisition log contains marker frame indices and callback times. "
        "Dropped display frames require per-frame timing data.",
    ]
    if callback_times and len(callback_times) >= 2 and sent[0].frame_index >= 0:
        ideal_span = (sent[-1].frame_index - sent[0].frame_index) / refresh_hz
        studio_span = callback_times[-1] - callback_times[0]
        lines += [
            f"- First-to-last marker frame span at reference refresh: {ideal_span:.6f} s",
            f"- Studio callback span minus reference frame span: "
            f"{(studio_span - ideal_span) * 1000:+.3f} ms",
        ]

    lines += [
        "",
        "## Saved markers and continuity",
        "",
        f"- Planned markers: {run.planned_event_count}",
        f"- Studio sent: {len(sent)}",
        f"- Other recorded attempts: {other_attempts}",
        f"- BDF markers: {len(saved_codes)}",
        f"- Ordered marker codes match: {'yes' if codes_match else 'no'}",
        f"- BDF oddball gaps in samples (count): {_gaps(oddball_samples)}",
        "- BDF oddball intervals at nominal rate (min / mean / max): "
        f"{_interval_stats_ms([sample / bdf.sample_rate_hz for sample in oddball_samples])}",
        counter_line,
        validity_line,
        "",
        "| Code | Studio sent | BDF saved |",
        "| ---: | ---: | ---: |",
    ]
    sent_counts, saved_counts = Counter(sent_codes), Counter(saved_codes)
    lines.extend(
        f"| {code} | {sent_counts[code]} | {saved_counts[code]} |"
        for code in sorted(sent_counts.keys() | saved_counts.keys())
    )
    if marker_samples:
        lines += [
            "",
            f"First to last saved marker: samples {marker_samples[0]:,} "
            f"to {marker_samples[-1]:,} (zero-based).",
        ]

    issues = []
    if not codes_match:
        issues.append("saved marker sequence differs from Studio sends")
    if run.state != "completed" or len(sent) != run.planned_event_count or other_attempts:
        issues.append("Studio did not complete all planned sends successfully")
    starts = [event for event in sent if event.label == "condition_start"]
    if len(starts) != 1 or starts[0] is not sent[0] or starts[0].code == oddball_code:
        issues.append("expected one leading condition-start marker distinct from the oddball code")
    if len(oddball_frames) < 2:
        issues.append("at least two oddball callbacks are required")
    if callback_times is None or len(callback_times) < 3:
        issues.append("at least three finite, increasing callback timestamps are required")
    if counter_breaks or invalid_samples:
        issues.append("counter discontinuities or invalid samples in the saved marker span")

    lines += ["", "## Software-relative drift", ""]
    if issues:
        lines.append(f"- Drift fit withheld: {'; '.join(issues)}.")
    elif callback_times is not None:
        lines += _drift_lines(callback_times, marker_samples, bdf.sample_rate_hz)
    lines += [
        "",
        "The fit compares Studio callbacks with Recorder's marker placement. "
        "An apparent rate can reflect both acquisition clock error and marker assignment. "
        "Screen-light timing remains unmeasured.",
    ]
    return "\n".join(lines) + "\n"


def _positive_rate(value: str) -> float:
    rate = float(value)
    if not isfinite(rate) or rate <= 0:
        raise argparse.ArgumentTypeError("rate must be finite and positive")
    return rate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bdf", type=Path, help="raw Unicorn Recorder BDF")
    parser.add_argument("studio_log", type=Path, help="single-run Studio acquisition v1 JSON")
    parser.add_argument("--refresh-hz", type=_positive_rate, default=60.0)
    parser.add_argument("--oddball-hz", type=_positive_rate, default=1.2)
    parser.add_argument("--oddball-code", type=int, default=55)
    parser.add_argument("--output", type=Path, help="new Markdown file (default: stdout)")
    args = parser.parse_args(argv)
    if not 1 <= args.oddball_code <= 255:
        parser.error("oddball code must be between 1 and 255")
    try:
        evidence = AcquisitionEvidence.model_validate_json(args.studio_log.read_bytes())
    except ValidationError:
        parser.error("Studio log does not match the acquisition v1 schema")
    except OSError as error:
        parser.error(str(error))
    try:
        report = build_timing_report(
            evidence, read_unicorn_bdf(args.bdf), bdf_name=args.bdf.name,
            log_name=args.studio_log.name, refresh_hz=args.refresh_hz,
            oddball_hz=args.oddball_hz, oddball_code=args.oddball_code,
        )
        if args.output is None:
            sys.stdout.write(report)
        else:
            with args.output.open("x", encoding="utf-8", newline="\n") as output:
                output.write(report)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
