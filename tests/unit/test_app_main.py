"""Application entry-point tests."""

from __future__ import annotations

import sys
import types

from fpvs_studio.app.main import main


def test_main_lazily_delegates_to_gui_runner(monkeypatch) -> None:
    captures: dict[str, object] = {}
    fake_module = types.ModuleType("fpvs_studio.gui.application")

    def _fake_run_gui_app(argv=None) -> int:
        captures["argv"] = argv
        return 7

    fake_module.run_gui_app = _fake_run_gui_app
    monkeypatch.setitem(sys.modules, "fpvs_studio.gui.application", fake_module)

    exit_code = main(["--demo"])

    assert exit_code == 7
    assert captures["argv"] == ["--demo"]
