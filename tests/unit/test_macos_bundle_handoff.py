"""Exercise the CI handoff tool locally without claiming a native Mac run."""

from __future__ import annotations

import json

import pytest
from tests.integration.macos_bundle_handoff import main


def _roundtrip(work, source, output):
    return main([
        "roundtrip", "--input", str(source / "project.fpvsbundle"),
        "--baseline", str(source / "baseline.json"), "--work-root", str(work),
        "--output", str(output),
    ])


def test_handoff_cli_preserves_baseline_through_two_relocations(tmp_path):
    first, second, final = (tmp_path / name for name in ("first", "second", "final"))
    work = tmp_path / "owned work"
    assert main(["create", "--work-root", str(work), "--output", str(first)]) == 0
    assert _roundtrip(work, first, second) == 0
    assert _roundtrip(work, second, final) == 0
    assert (first / "baseline.json").read_bytes() == (final / "baseline.json").read_bytes()
    baseline = json.loads((final / "baseline.json").read_bytes())
    assert baseline["compiled_plan"]["total_runs"] == 7
    assert baseline["compiled_plan"]["ordering_policy"] == "saved_randomized_blocks"
    assert baseline["project"]["settings"]["recording"]["brainproducts_serial_port"] == "COM47"
    assert json.loads((first / "evidence.json").read_bytes())["source_relocated"]
    assert all(not (folder / "source-project").exists() for folder in work.iterdir())


def test_handoff_cli_detects_schedule_mismatch(tmp_path):
    source = tmp_path / "first"
    work = tmp_path / "work"
    assert main(["create", "--work-root", str(work), "--output", str(source)]) == 0
    baseline_path = source / "baseline.json"
    baseline = json.loads(baseline_path.read_bytes())
    baseline["compiled_plan"]["total_runs"] += 1
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch: compiled_plan"):
        _roundtrip(work, source, tmp_path / "returned")


def test_handoff_cli_preserves_existing_output(tmp_path):
    output = tmp_path / "artifacts"
    output.mkdir()
    bundle = output / "project.fpvsbundle"
    bundle.write_bytes(b"previous artifact")
    with pytest.raises(ValueError, match="already contains artifacts"):
        main(["create", "--work-root", str(tmp_path / "work"), "--output", str(output)])
    assert bundle.read_bytes() == b"previous artifact"
