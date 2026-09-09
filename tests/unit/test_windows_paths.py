"""Windows filesystem namespaces stay out of portable project records."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fpvs_studio.core.paths import (
    filesystem_path,
    resolve_project_relative_path,
    to_project_relative_posix,
)

windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows namespace behavior")


def test_io_path_platform_behavior(tmp_path: Path) -> None:
    result = filesystem_path(tmp_path)
    if os.name == "nt":
        assert str(result).startswith("\\\\?\\")
        assert result.is_dir()
        assert filesystem_path(result) == result
    else:
        assert result is tmp_path


@windows_only
def test_io_path_normalizes_relative(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert filesystem_path(Path("images/../source")) == filesystem_path(tmp_path / "source")


@windows_only
def test_io_path_unc_without_network() -> None:
    ordinary = Path("\\\\research-server\\images\\source.png")
    extended = filesystem_path(ordinary)
    assert str(extended) == "\\\\?\\UNC\\research-server\\images\\source.png"
    assert filesystem_path(extended) == extended


@windows_only
@pytest.mark.parametrize("extended_root", [False, True])
@pytest.mark.parametrize("extended_target", [False, True])
def test_io_path_relative_roundtrip(
    tmp_path: Path, extended_root: bool, extended_target: bool
) -> None:
    root = filesystem_path(tmp_path) if extended_root else tmp_path
    ordinary = tmp_path / "stimuli" / "日本語 image.png"
    target = filesystem_path(ordinary) if extended_target else ordinary
    assert to_project_relative_posix(root, target) == "stimuli/日本語 image.png"
    assert resolve_project_relative_path(root, "stimuli/日本語 image.png") == ordinary


@windows_only
def test_resolver_reads_long_asset(tmp_path: Path) -> None:
    root = tmp_path / "project"
    relative = "stimuli/" + "/".join(["nested-folder-" * 4] * 4) + "/image.png"
    target = filesystem_path(root / relative)
    target.parent.mkdir(parents=True)
    target.write_bytes(b"same image bytes")
    assert len(str(root / relative)) > 260
    resolved = resolve_project_relative_path(root, relative)
    assert resolved.read_bytes() == b"same image bytes"
    assert to_project_relative_posix(root, resolved) == relative


@windows_only
def test_resolver_utf16_path_length(tmp_path: Path) -> None:
    root = tmp_path.parent / "unicode-project"
    # Non-BMP characters occupy two Windows WCHAR units each.
    relative = "stimuli/" + "a" * max(1, 221 - len(str(root))) + "😀" * 10 + ".png"
    ordinary = root / relative
    assert len(str(ordinary)) < 248
    assert len(str(ordinary).encode("utf-16-le")) // 2 >= 248
    assert str(resolve_project_relative_path(root, relative)).startswith("\\\\?\\")


@pytest.mark.parametrize("relative", ["../outside.png", "stimuli/../../outside.png"])
def test_resolver_rejects_escape(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError, match="escape"):
        resolve_project_relative_path(tmp_path, relative)


@windows_only
def test_relative_rejects_outside(tmp_path: Path) -> None:
    root = tmp_path / "project"
    outside = filesystem_path(tmp_path / "other" / "image.png")
    with pytest.raises(ValueError):
        to_project_relative_posix(root, outside)
