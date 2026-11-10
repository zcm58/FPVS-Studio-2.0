"""The independent helper's diagnostic mode must work without importing the GUI."""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from fpvs_studio import updater_main
from fpvs_studio.updates import helper_client, helper_runtime


def test_packaging_check_is_headless_and_reports_protocol(tmp_path):
    report = tmp_path / "updater-report.json"
    process = subprocess.run(
        [sys.executable, "-m", "fpvs_studio.updater_main", "--packaging-check", str(report)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    result = json.loads(report.read_text(encoding="utf-8"))
    assert result["protocol_version"] == 1
    assert result["gui_loaded"] is False
    assert result["frozen"] is False
    assert result["version"]


@pytest.mark.parametrize("platform,frozen", [("win32", False), ("darwin", False), ("darwin", True)])
def test_source_entry_opens_source_gui_without_windows_helper_staging(
    monkeypatch, platform, frozen,
):
    monkeypatch.setattr(helper_client, "sys", SimpleNamespace(platform=platform, frozen=frozen))
    monkeypatch.setattr(helper_runtime, "is_staged_helper", lambda: pytest.fail(
        "Source mode must not inspect Windows helper staging",
    ))
    calls = []
    fake_gui = SimpleNamespace(run_updater_gui=lambda **kwargs: calls.append(kwargs) or 0)
    monkeypatch.setitem(sys.modules, "fpvs_studio.gui.updater_window", fake_gui)
    assert updater_main.main([]) == 0
    assert calls == [{"apply_mode": False, "smoke_report": None, "startup_error": None}]
