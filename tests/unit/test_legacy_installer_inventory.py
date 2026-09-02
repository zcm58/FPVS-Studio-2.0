"""Safe archive-inventory checks; no network, extractor, or installer execution."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts/refresh_legacy_installer_inventory.py"
SPEC = importlib.util.spec_from_file_location("studio_legacy_inventory", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


def _release(
    version: str = "1.3.0", *, tag: str | None = None, digest: str | None = None
) -> dict[str, object]:
    return {
        "tag_name": tag or f"v{version}",
        "draft": False,
        "assets": [{
            "name": f"FPVS-Studio-Setup-{version}.exe",
            "id": 123,
            "size": 100,
            "digest": digest if digest is not None else "sha256:" + "a" * 64,
        }],
    }


def test_published_selection_preserves_historical_tag_filename_mismatch() -> None:
    releases = [
        _release("1.3.0"),
        _release("0.9.10", tag="v0.9.9.10"),
        _release("1.4.0"),
        {"tag_name": "experiments-v1", "assets": []},
    ]
    result = inventory.published_installers(releases, "1.3.0")
    assert [item.tag for item in result] == ["v0.9.9.10", "v1.3.0"]
    assert result[0].asset_name == "FPVS-Studio-Setup-0.9.10.exe"
    assert result[0].provenance()["sha256"] == "a" * 64


@pytest.mark.parametrize("digest", ["", "a" * 64, "md5:" + "a" * 64, "sha256:bad"])
def test_published_selection_requires_git_hub_sha256(digest: str) -> None:
    with pytest.raises(ValueError, match="trusted asset metadata"):
        inventory.published_installers([_release(digest=digest)], "1.3.0")


def test_published_selection_rejects_duplicate_names_and_empty_input() -> None:
    with pytest.raises(ValueError, match="not unique"):
        inventory.published_installers([_release(), _release()], "1.3.0")
    with pytest.raises(ValueError, match="No published installers"):
        inventory.published_installers([], "1.3.0")


@pytest.mark.parametrize("path", [
    "../outside.dll", "/outside.dll", "C:/outside.dll", "C:outside.dll",
    "_internal/../outside.dll", "_internal//file.dll", "_internal/file.dll:stream",
    "_internal/./file.dll", "NUL.dll", "_internal/CON", "file.dll ", "dir./file.dll",
    "{localappdata}/settings.ini", "_internal/*", "_internal/file\nname.dll",
])
def test_archive_paths_reject_windows_aliases_and_escape(path: str) -> None:
    with pytest.raises(ValueError, match="Unsafe installed payload path"):
        inventory.validate_payload_path(path)


def test_listing_only_inventories_app_payload_and_rejects_aliases() -> None:
    assert inventory.parse_payload_listing(
        "Inno Setup version detected: 6.7.0\n"
        "  {app}\\FPVS Studio.exe\n"
        "  {app}\\_internal\\Qt6Core.dll\n"
        "  {tmp}\\embedded-file\n"
    ) == {"FPVS Studio.exe", "_internal/Qt6Core.dll"}
    with pytest.raises(ValueError, match="Duplicate/case-aliased"):
        inventory.parse_payload_listing("{app}\\FPVS Studio.exe\n{app}\\FPVS STUDIO.EXE")
    with pytest.raises(ValueError, match="no FPVS Studio.exe"):
        inventory.parse_payload_listing("{app}\\other.exe")


def test_extracted_tree_must_match_complete_listing(tmp_path: Path) -> None:
    (tmp_path / "FPVS Studio.exe").write_bytes(b"not executed")
    (tmp_path / "_internal").mkdir()
    (tmp_path / "_internal/lib.dll").write_bytes(b"library")
    expected = {"FPVS Studio.exe", "_internal/lib.dll"}
    result = inventory.inventory_extracted_payload(tmp_path, expected)
    assert result["FPVS Studio.exe"] == hashlib.sha256(b"not executed").hexdigest()
    with pytest.raises(ValueError, match="do not match"):
        inventory.inventory_extracted_payload(tmp_path, expected | {"missing.dll"})


def test_same_size_corrupted_installer_fails_authentication(tmp_path: Path) -> None:
    path = tmp_path / "FPVS-Studio-Setup-1.3.0.exe"
    path.write_bytes(b"incorrect")
    asset = inventory.PublishedInstaller(
        "v1.3.0", path.name, 123, hashlib.sha256(b"authentic").hexdigest(), 9
    )
    with pytest.raises(ValueError, match="failed authentication"):
        inventory.authenticate_installer(asset, path)
    path.write_bytes(b"authentic")
    inventory.authenticate_installer(asset, path)


def test_union_is_deterministic_and_excludes_uninstaller_bookkeeping() -> None:
    first = {"FPVS Studio.exe": "a" * 64, "_internal/lib.dll": "b" * 64}
    second = {
        "FPVS Studio.exe": "c" * 64,
        "_internal/LIB.dll": "b" * 64,
        "unins000.exe": "d" * 64,
    }
    result = inventory.merge_payloads([first, second])
    assert result == inventory.merge_payloads([second, first])
    assert result == [
        {"path": "_internal/LIB.dll", "sha256": ["b" * 64]},
        {"path": "FPVS Studio.exe", "sha256": ["a" * 64, "c" * 64]},
    ]


def test_inventory_runs_extractor_not_published_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "FPVS-Studio-Setup-1.3.0.exe"
    archive.write_bytes(b"archive")
    extractor = tmp_path / "portable-innounp.exe"
    asset = inventory.PublishedInstaller(
        "v1.3.0", archive.name, 123, hashlib.sha256(b"archive").hexdigest(), 7
    )
    commands: list[list[str]] = []

    def fake_run(command: list[str]) -> str:
        commands.append(command)
        assert command[0] == str(extractor)
        if "-s" in command:
            return "{app}\\FPVS Studio.exe\n"
        destination = Path(next(part[2:] for part in command if part.startswith("-d")))
        (destination / "{app}").mkdir()
        (destination / "{app}/FPVS Studio.exe").write_bytes(b"payload")
        return ""

    monkeypatch.setattr(inventory, "_run", fake_run)
    result = inventory.collect_inventory([asset], extractor, tmp_path)
    assert len(commands) == 2
    assert result["releases"] == [asset.provenance()]
    assert result["files"] == [{
        "path": "FPVS Studio.exe", "sha256": [hashlib.sha256(b"payload").hexdigest()]
    }]
    assert archive.read_bytes() == b"archive"
    assert not list(tmp_path.glob("payload-*"))


@pytest.mark.parametrize("failure", ["serialization", "flush", "replace"])
def test_inventory_write_failure_preserves_previous_output_and_cleans_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    destination = tmp_path / "published.json"
    destination.write_text("previous reviewed inventory", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("injected inventory write failure")

    if failure == "serialization":
        monkeypatch.setattr(inventory.json, "dump", fail)
    elif failure == "flush":
        monkeypatch.setattr(inventory.os, "fsync", fail)
    else:
        monkeypatch.setattr(Path, "replace", fail)

    with pytest.raises(OSError, match="injected inventory write failure"):
        inventory.write_inventory(destination, {"files": []})
    assert destination.read_text(encoding="utf-8") == "previous reviewed inventory"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["published.json"]
