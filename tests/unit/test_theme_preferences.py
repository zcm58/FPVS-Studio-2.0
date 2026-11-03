"""Execute appearance preference logic without importing or starting Qt."""

from __future__ import annotations

import ast
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

KEY = "appearance/theme_mode"


class Settings:
    def __init__(self, values=None, *, failure=False):
        self.values = dict(values or {})
        self.failure = failure
        self.writes = []

    def value(self, key, default=None, **_kwargs):
        return self.values.get(key, default)

    def setValue(self, key, value):  # noqa: N802
        self.writes.append((key, value))
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        pass

    def status(self):
        return int(self.failure)


def controller(settings=None):
    source = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui/controller.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "StudioController")
    names = {"load_theme_mode", "set_theme_mode", "_apply_theme_mode"}
    methods = [node for node in owner.body if isinstance(node, ast.FunctionDef)
               and node.name in names]
    assert len(methods) == len(names)
    namespace = {
        "_THEME_MODE_KEY": KEY, "_THEME_MODES": {"light", "dark", "auto"},
        "QSettings": SimpleNamespace(Status=SimpleNamespace(NoError=0)),
        "Qt": SimpleNamespace(ColorScheme=SimpleNamespace(Light=1, Dark=2, Unknown=0)),
    }
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    hints = SimpleNamespace(setColorScheme=Mock())
    app = SimpleNamespace(setProperty=Mock(), styleHints=lambda: hints)
    result = SimpleNamespace(_settings=settings or Settings(), _app=app)
    for name in names:
        setattr(result, name, MethodType(namespace[name], result))
    return result, hints


@pytest.mark.parametrize("value", [None, "", "invalid", "LIGHT", 1, []])
def test_invalid_or_missing_appearance_reads_auto_without_rewriting(value):
    settings = Settings({KEY: value})
    control, _ = controller(settings)
    assert control.load_theme_mode() == "auto"
    assert settings.writes == []


@pytest.mark.parametrize(("mode", "scheme"), [("light", 1), ("dark", 2), ("auto", 0)])
def test_theme_is_saved_and_applied_with_auto_removing_native_override(mode, scheme):
    settings = Settings({"unrelated": "retained"})
    control, hints = controller(settings)
    control.set_theme_mode(mode)
    assert settings.values == {"unrelated": "retained", KEY: mode}
    hints.setColorScheme.assert_called_once_with(scheme)
    control._app.setProperty.assert_called_once_with("studioThemeMode", mode)
    reopened, _ = controller(settings)
    assert reopened.load_theme_mode() == mode


@pytest.mark.parametrize("value", ["invalid", None, []])
def test_invalid_theme_does_not_change_saved_or_applied_choice(value):
    settings = Settings({KEY: "dark"})
    control, hints = controller(settings)
    with pytest.raises(ValueError, match="Light, Dark or Auto"):
        control.set_theme_mode(value)
    assert settings.values == {KEY: "dark"}
    hints.setColorScheme.assert_not_called()


@pytest.mark.parametrize("original", [None, "dark"])
def test_failed_settings_write_restores_preference_without_changing_theme(original):
    values = {} if original is None else {KEY: original}
    settings = Settings(values, failure=True)
    control, hints = controller(settings)
    with pytest.raises(OSError, match="Could not save appearance"):
        control.set_theme_mode("light")
    assert settings.values == values
    hints.setColorScheme.assert_not_called()
