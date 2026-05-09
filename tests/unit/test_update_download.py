"""Installer download backend tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from fpvs_studio.updates.downloader import download_installer
from fpvs_studio.updates.installer import launch_installer
from fpvs_studio.updates.models import InstallerAsset, UpdateError


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0
        self.headers = {"Content-Length": str(len(payload))}

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if self._offset >= len(self._payload):
            return b""
        if size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def test_download_installer_writes_to_destination_and_reports_progress(
    monkeypatch,
    tmp_path: Path,
) -> None:
    payload = b"installer"
    progress: list[tuple[int, int | None]] = []

    monkeypatch.setattr(
        "fpvs_studio.updates.downloader.urlopen",
        lambda *_args, **_kwargs: _FakeResponse(payload),
    )

    result = download_installer(
        InstallerAsset(
            name="FPVS-Studio-Setup-0.9.0b2.exe",
            download_url="https://github.com/downloads/FPVS-Studio-Setup-0.9.0b2.exe",
            size_bytes=len(payload),
        ),
        destination_dir=tmp_path,
        progress_callback=lambda downloaded, total: progress.append((downloaded, total)),
    )

    assert result.path == tmp_path / "FPVS-Studio-Setup-0.9.0b2.exe"
    assert result.path.read_bytes() == payload
    assert result.size_bytes == len(payload)
    assert progress[-1] == (len(payload), len(payload))


def test_download_installer_reuses_complete_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "FPVS-Studio-Setup-0.9.0b2.exe"
    target.write_bytes(b"installer")
    progress: list[tuple[int, int | None]] = []

    result = download_installer(
        InstallerAsset(
            name=target.name,
            download_url="https://github.com/downloads/FPVS-Studio-Setup-0.9.0b2.exe",
            size_bytes=target.stat().st_size,
        ),
        destination_dir=tmp_path,
        progress_callback=lambda downloaded, total: progress.append((downloaded, total)),
    )

    assert result.path == target
    assert progress == [(len(b"installer"), len(b"installer"))]


def test_download_installer_rejects_non_https_urls(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="HTTPS"):
        download_installer(
            InstallerAsset(
                name="FPVS-Studio-Setup-0.9.0b2.exe",
                download_url="http://example.com/FPVS-Studio-Setup-0.9.0b2.exe",
                size_bytes=1,
            ),
            destination_dir=tmp_path,
        )


def test_launch_installer_requires_existing_exe(tmp_path: Path) -> None:
    with pytest.raises(UpdateError, match="does not exist"):
        launch_installer(tmp_path / "missing.exe")

    not_exe = tmp_path / "installer.txt"
    not_exe.write_text("not an exe", encoding="utf-8")
    with pytest.raises(UpdateError, match="Windows .exe"):
        launch_installer(not_exe)


def test_launch_installer_requests_relaunch(monkeypatch, tmp_path: Path) -> None:
    installer = tmp_path / "FPVS-Studio-Setup-0.9.0b2.exe"
    installer.write_bytes(b"installer")
    commands: list[list[str]] = []

    monkeypatch.setattr(
        "fpvs_studio.updates.installer.subprocess.Popen",
        lambda command, **_kwargs: commands.append(command),
    )

    launch_installer(installer)

    assert commands == [[str(installer), "/RELAUNCH=1"]]
