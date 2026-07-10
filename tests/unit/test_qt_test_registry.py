"""Tests for the explicit Qt-test collection boundary."""

from __future__ import annotations

import sys
from pathlib import Path

from tests.qt_test_registry import (
    find_qt_test_files,
    load_qt_test_registry,
    qt_tests_requested,
    registry_mismatches,
    requested_registered_qt_files,
)


def test_checked_in_registry_exactly_matches_qt_test_candidates() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    registry = load_qt_test_registry(repo_root)

    assert registry_mismatches(repo_root, registry) == (frozenset(), frozenset())


def test_candidate_scan_detects_gui_directory_and_fixture_usage(tmp_path: Path) -> None:
    gui_test = tmp_path / "tests" / "gui" / "test_plain.py"
    gui_test.parent.mkdir(parents=True)
    gui_test.write_text("def test_plain():\n    pass\n", encoding="utf-8")
    fixture_test = tmp_path / "tests" / "unit" / "test_widget.py"
    fixture_test.parent.mkdir(parents=True)
    fixture_name = "qt" + "bot"
    fixture_test.write_text(f"def test_widget({fixture_name}):\n    pass\n", encoding="utf-8")

    assert find_qt_test_files(tmp_path) == frozenset(
        {"tests/gui/test_plain.py", "tests/unit/test_widget.py"}
    )


def test_qt_opt_in_requires_explicit_truthy_value() -> None:
    variable_name = "FPVS_ALLOW_" + "QT_TESTS"

    assert qt_tests_requested(cli_opt_in=True, environ={})
    assert qt_tests_requested(cli_opt_in=False, environ={variable_name: "yes"})
    assert not qt_tests_requested(cli_opt_in=False, environ={variable_name: "0"})


def test_explicit_registered_file_and_directory_are_detected(tmp_path: Path) -> None:
    test_file = tmp_path / "tests" / "gui" / "test_widget.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    registry = frozenset({"tests/gui/test_widget.py"})

    assert requested_registered_qt_files(
        [f"{test_file}::test_widget"],
        repo_root=tmp_path,
        registry=registry,
    ) == registry
    assert requested_registered_qt_files(
        ["tests/gui"],
        repo_root=tmp_path,
        registry=registry,
    ) == registry


def test_default_pytest_config_blocks_qt_autoload_and_cache_writes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "-p no:" + "pytest-qt" in source
    assert "-p no:" + "cacheprovider" in source


def test_root_conftest_does_not_force_a_qt_platform() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "tests" / "conftest.py").read_text(encoding="utf-8")
    platform_variable = "QT_QPA_" + "PLATFORM"
    headless_platform = "off" + "screen"

    assert platform_variable not in source
    assert headless_platform not in source


def test_default_pytest_session_does_not_import_pyside6() -> None:
    root_module = "PySide6"

    assert all(
        module_name != root_module and not module_name.startswith(f"{root_module}.")
        for module_name in sys.modules
    )
