"""Focused tests for the scope-aware repository verification driver."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = PROJECT_ROOT / ".agents" / "scripts" / "verify.py"
VERIFY_SPEC = importlib.util.spec_from_file_location("studio_agent_verify", VERIFY_PATH)
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
verify = importlib.util.module_from_spec(VERIFY_SPEC)
sys.modules[VERIFY_SPEC.name] = verify
VERIFY_SPEC.loader.exec_module(verify)


def _scope(
    *,
    name: str = "repo",
    tests: tuple[str, ...] = (),
    full_tests: tuple[str, ...] = (),
    include: tuple[str, ...] = ("**/*.py",),
) -> object:
    return verify.VerificationScope(
        name=name,
        checks=(),
        tests=tests,
        full_tests=full_tests,
        include=include,
        manual_smoke=(),
    )


def test_resolve_repo_python_prefers_venv310_then_venv(tmp_path: Path) -> None:
    venv_python = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.touch()
    assert verify.resolve_repo_python(tmp_path) == venv_python.resolve()

    preferred_python = tmp_path / ".venv3.10" / "Scripts" / "python.exe"
    preferred_python.parent.mkdir(parents=True)
    preferred_python.touch()
    assert verify.resolve_repo_python(tmp_path) == preferred_python.resolve()


def test_validate_config_rejects_qt_test_only_from_local_bundle(tmp_path: Path) -> None:
    qt_test = tmp_path / "tests" / "gui" / "test_window.py"
    qt_test.parent.mkdir(parents=True)
    qt_test.write_text("def test_placeholder(): pass\n", encoding="utf-8")
    registry = tmp_path / "tests" / "qt_test_files.txt"
    registry.write_text("tests/gui/test_window.py\n", encoding="utf-8")

    local_scope = _scope(
        name="gui",
        tests=("tests/gui/test_window.py",),
        include=("tests/gui/**",),
    )
    assert verify.validate_config(
        {"gui": local_scope}, registry, repo_root=tmp_path
    ) == ["gui: focused local bundle includes Qt test: tests/gui/test_window.py"]

    full_only_scope = _scope(
        name="gui",
        full_tests=("tests/gui/test_window.py",),
        include=("tests/gui/**",),
    )
    assert verify.validate_config(
        {"gui": full_only_scope}, registry, repo_root=tmp_path
    ) == []


def test_precommit_lints_changed_python_and_runs_only_safe_unit_tests() -> None:
    plugin_name = "pytest" + "qt.plugin"
    commands = verify.build_commands(
        _scope(),
        tier="precommit",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=("src/fpvs_studio/core/models.py", "docs/README.md"),
    )

    assert [
        "python.exe",
        "-m",
        "ruff",
        "check",
        "src/fpvs_studio/core/models.py",
    ] in commands
    pytest_command = next(command for command in commands if "pytest" in command)
    assert pytest_command[-1] == "tests/unit"
    assert "--allow-qt-tests" not in pytest_command
    assert plugin_name not in pytest_command


def test_safe_commands_do_not_inherit_qt_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_environments: list[dict[str, str]] = []

    class _Result:
        returncode = 0

    def _record_run(
        _command: object, *, cwd: Path, check: bool, env: dict[str, str]
    ) -> _Result:
        assert cwd == verify.REPO_ROOT
        assert check is False
        observed_environments.append(env)
        return _Result()

    monkeypatch.setenv(verify.QT_OPT_IN_ENV, "1")
    monkeypatch.setattr(verify.subprocess, "run", _record_run)

    assert verify.run_commands(
        [["python.exe", "-m", "pytest", "tests/unit"]], list_only=False
    ) == 0
    assert verify.QT_OPT_IN_ENV not in observed_environments[0]

    assert verify.run_commands(
        [["python.exe", "-m", "pytest", "--allow-qt-tests", "tests/gui"]],
        list_only=False,
    ) == 0
    assert observed_environments[1][verify.QT_OPT_IN_ENV] == "1"


def test_repo_full_runs_one_qt_enabled_pytest_command() -> None:
    plugin_name = "pytest" + "qt.plugin"
    commands = verify.build_commands(
        _scope(),
        tier="full",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=(),
    )

    pytest_commands = [command for command in commands if "pytest" in command]
    assert len(pytest_commands) == 1
    assert "--allow-qt-tests" in pytest_commands[0]
    assert plugin_name in pytest_commands[0]
    assert ["python.exe", "-m", "ruff", "check", "."] in commands
    assert ["python.exe", "-m", "mypy", "src"] in commands


def test_gui_focused_skips_qt_while_gui_full_uses_registered_tree() -> None:
    gui_scope = _scope(
        name="gui",
        full_tests=("tests/gui",),
        include=("src/fpvs_studio/gui/**", "tests/gui/**"),
    )

    focused = verify.build_commands(
        gui_scope,
        tier="focused",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=(),
    )
    full = verify.build_commands(
        gui_scope,
        tier="full",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=(),
    )

    assert focused == []
    assert len(full) == 1
    assert full[0][-1] == "tests/gui"
    assert "--allow-qt-tests" in full[0]


def test_scoped_full_adds_full_tests_once_in_configured_order() -> None:
    scope = _scope(
        name="gui",
        tests=("tests/shared.py", "tests/focused.py"),
        full_tests=("tests/focused.py", "tests/gui"),
    )

    focused = verify.build_commands(
        scope,
        tier="focused",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=(),
    )
    full = verify.build_commands(
        scope,
        tier="full",
        python=Path("python.exe"),
        powershell="pwsh",
        changed=(),
    )

    assert focused[0][-2:] == ["tests/shared.py", "tests/focused.py"]
    assert full[0][-3:] == [
        "tests/shared.py",
        "tests/focused.py",
        "tests/gui",
    ]


def test_parser_accepts_full_and_rejects_legacy_full_ci() -> None:
    scopes = {"repo": _scope()}

    assert verify.parse_args(
        scopes, ["--scope", "repo", "--tier", "full"]
    ).tier == "full"
    with pytest.raises(SystemExit):
        verify.parse_args(scopes, ["--scope", "repo", "--tier", "full-ci"])


def test_full_requires_explicit_visible_qt_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(verify.QT_OPT_IN_ENV, raising=False)
    monkeypatch.delenv(verify.QT_PLATFORM_ENV, raising=False)

    assert verify.main(["--scope", "repo", "--tier", "full"]) == 2
    assert f"full requires {verify.QT_OPT_IN_ENV}=1" in capsys.readouterr().err

    monkeypatch.setenv(verify.QT_OPT_IN_ENV, "1")
    monkeypatch.setenv(verify.QT_PLATFORM_ENV, "offscreen")

    assert verify.main(["--scope", "repo", "--tier", "full"]) == 2
    assert "full requires a visible Qt environment" in capsys.readouterr().err


def test_full_runs_after_visible_qt_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    monkeypatch.setenv(verify.QT_OPT_IN_ENV, "1")
    monkeypatch.delenv(verify.QT_PLATFORM_ENV, raising=False)
    monkeypatch.setattr(verify, "resolve_repo_python", lambda: Path("python.exe"))
    monkeypatch.setattr(verify, "resolve_powershell", lambda: "pwsh")
    monkeypatch.setattr(verify, "changed_files", lambda: ())

    def _record_commands(commands: object, *, list_only: bool) -> int:
        observed["commands"] = commands
        observed["list_only"] = list_only
        return 0

    monkeypatch.setattr(verify, "run_commands", _record_commands)

    assert verify.main(["--scope", "repo", "--tier", "full"]) == 0
    assert observed["list_only"] is False
    assert observed["commands"]


def test_full_list_is_safe_without_environment_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    monkeypatch.delenv(verify.QT_OPT_IN_ENV, raising=False)
    monkeypatch.setenv(verify.QT_PLATFORM_ENV, "offscreen")
    monkeypatch.setattr(verify, "resolve_repo_python", lambda: Path("python.exe"))
    monkeypatch.setattr(verify, "resolve_powershell", lambda: "pwsh")
    monkeypatch.setattr(verify, "changed_files", lambda: ())

    def _record_commands(commands: object, *, list_only: bool) -> int:
        observed["commands"] = commands
        observed["list_only"] = list_only
        return 0

    monkeypatch.setattr(verify, "run_commands", _record_commands)

    assert verify.main(["--scope", "repo", "--tier", "full", "--list"]) == 0
    assert observed["list_only"] is True
    assert observed["commands"]


def test_checked_in_verification_config_is_valid() -> None:
    scopes, registry = verify.load_scopes()

    assert set(scopes) == {
        "compiler",
        "core",
        "docs",
        "engine",
        "gui",
        "packaging",
        "preprocessing",
        "project-io",
        "repo",
        "runtime",
        "triggers",
        "updates",
    }
    assert "tests/unit/test_qt_test_registry.py" in scopes["repo"].tests
    assert scopes["gui"].full_tests == ("tests/gui",)
    assert scopes["engine"].full_tests == (
        "tests/integration/test_psychopy_engine.py",
    )
    assert verify.validate_config(scopes, registry) == []


def test_list_without_scope_reports_available_routes(capsys) -> None:
    assert verify.main(["--list"]) == 0

    output = capsys.readouterr().out
    assert "Available verification scopes:" in output
    assert "- repo" in output
    assert "- gui" in output
