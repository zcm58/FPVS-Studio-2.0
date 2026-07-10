"""Harness documentation consistency checks."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = PROJECT_ROOT / "src" / "fpvs_studio"


def _read_repo_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_repo_guidance_references_existing_harness_files() -> None:
    required_paths = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        "docs/FPVS_Studio_v1_Architecture_Spec.md",
        "docs/GUI_WORKFLOW.md",
        "docs/RUNSPEC.md",
        "docs/SESSION_PLAN.md",
        "docs/RUNTIME_EXECUTION.md",
        ".agents/skills/legacy-boundary-review/SKILL.md",
        ".agents/skills/project-path-audit/SKILL.md",
        ".agents/skills/fpvs-psychopy-migration/SKILL.md",
        ".agents/skills/pyside6-gui-cleanup/SKILL.md",
        ".agents/skills/pytest-qt-smoke/SKILL.md",
    ]

    missing_paths = [
        path for path in required_paths if not (PROJECT_ROOT / path).exists()
    ]

    assert missing_paths == []


def test_architecture_package_map_matches_source_packages() -> None:
    architecture = _read_repo_file("ARCHITECTURE.md")
    documented_packages = set(
        re.findall(r"`src/fpvs_studio/([^/`]+)/`", architecture)
    )
    source_packages = {
        path.name
        for path in PACKAGE_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert documented_packages == source_packages


def test_source_packages_have_scoped_agent_guidance() -> None:
    missing_agent_guides = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PACKAGE_ROOT.iterdir()
        if path.is_dir()
        and path.name != "__pycache__"
        and not (path / "AGENTS.md").exists()
    ]

    assert missing_agent_guides == []


def test_harness_update_policy_is_documented() -> None:
    root_agents = _read_repo_file("AGENTS.md")
    architecture = _read_repo_file("ARCHITECTURE.md")

    assert "Update `ARCHITECTURE.md`" in root_agents
    assert "Fast path before broad reads" in root_agents
    assert "Documentation Freshness" in architecture
    assert "Task Context Recipes" in architecture


def test_gui_no_clipping_policy_is_documented() -> None:
    documents = [
        _read_repo_file("AGENTS.md"),
        _read_repo_file("src/fpvs_studio/gui/AGENTS.md"),
        _read_repo_file(".agents/skills/pyside6-gui-cleanup/SKILL.md"),
        _read_repo_file(".agents/skills/pytest-qt-smoke/SKILL.md"),
        _read_repo_file("docs/FRONTEND.md"),
    ]

    for document in documents:
        assert "clipping" in document.casefold()
        assert "minimum/default size" in document.casefold()


def test_active_agent_docs_use_repo_python_environment() -> None:
    active_docs = [
        "AGENTS.md",
        "ARCHITECTURE.md",
        ".agents/skills/fpvs-psychopy-migration/references/migration-guide.md",
        ".agents/skills/pytest-qt-smoke/SKILL.md",
        "docs/ENVIRONMENT.md",
        "docs/GUI_WORKFLOW.md",
        "docs/QUALITY_SCORE.md",
        "docs/TECH_DEBT.md",
        "docs/exec-plans/plan-review-workflow.md",
    ]

    stale_references: list[str] = []
    for relative_path in active_docs:
        text = _read_repo_file(relative_path)
        if r".\.venv\Scripts\python" in text:
            stale_references.append(relative_path)
        for line in text.splitlines():
            if (
                re.search(r"python -m (pytest|ruff|mypy)", line)
                and r".\.venv3.10\Scripts\python" not in line
            ):
                stale_references.append(relative_path)

    assert sorted(set(stale_references)) == []


def test_locked_oddball_trigger_code_policy_is_documented() -> None:
    architecture = _read_repo_file("ARCHITECTURE.md")
    runspec = _read_repo_file("docs/RUNSPEC.md")
    runtime = _read_repo_file("docs/RUNTIME_EXECUTION.md")
    spec = _read_repo_file("docs/FPVS_Studio_v1_Architecture_Spec.md")
    core_agents = _read_repo_file("src/fpvs_studio/core/AGENTS.md")
    migration_skill = _read_repo_file(".agents/skills/fpvs-psychopy-migration/SKILL.md")
    migration_guide = _read_repo_file(
        ".agents/skills/fpvs-psychopy-migration/references/migration-guide.md"
    )

    for document in [
        architecture,
        runspec,
        runtime,
        spec,
        core_agents,
        migration_skill,
        migration_guide,
    ]:
        assert "oddball" in document
        assert "`55`" in document
        assert "allow_nonstandard_oddball_trigger_code" in document


def test_architecture_task_recipe_paths_exist() -> None:
    architecture = _read_repo_file("ARCHITECTURE.md")
    path_pattern = re.compile(
        r"`((?:AGENTS|ARCHITECTURE|docs|src|tests|packaging)/[^`]+|(?:AGENTS|ARCHITECTURE)\.md)`"
    )
    ignored_suffixes = ("/", "/*")
    referenced_paths = {
        match.group(1)
        for match in path_pattern.finditer(architecture.replace("\\", "/"))
        if "*" not in match.group(1) and not match.group(1).endswith(ignored_suffixes)
    }

    missing_paths = sorted(
        path for path in referenced_paths if not (PROJECT_ROOT / path).exists()
    )

    assert missing_paths == []
