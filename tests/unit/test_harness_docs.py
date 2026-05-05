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
    assert "Documentation Freshness" in architecture
