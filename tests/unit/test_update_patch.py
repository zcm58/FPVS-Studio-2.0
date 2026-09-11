"""Patch checks use temporary installed trees, fake GitHub assets and mocked Popen."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
from contextlib import nullcontext
from dataclasses import asdict, replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from fpvs_studio.updates import downloader, github_releases, installer, patches
from fpvs_studio.updates.cache import cleanup_update_cache, receipt_name, recognized_cache_entry
from fpvs_studio.updates.downloader import download_installer
from fpvs_studio.updates.github_releases import select_update_from_releases
from fpvs_studio.updates.installer import launch_installer
from fpvs_studio.updates.models import (
    InstallerAsset,
    UpdateCancelled,
    UpdateError,
    UpdateIntegrityError,
)
from fpvs_studio.updates.validation import validate_asset_identity

BASE = "1.5.0"
TARGET = "1.5.1"
PATCH_BYTES = b"patch"


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _github_asset(name: str, payload: bytes) -> dict[str, object]:
    return {
        "name": name,
        "size": len(payload),
        "id": 123,
        "digest": f"sha256:{_hash(payload)}",
        "browser_download_url": f"https://github.com/zcm58/FPVS-Studio-2.0/releases/download/v{TARGET}/{name}",
    }


class Response(io.BytesIO):
    def __init__(self, payload: bytes, url: str) -> None:
        super().__init__(payload)
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}

    def geturl(self) -> str:
        return self.url


@pytest.fixture(autouse=True)
def no_external_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Patch unit tests must not use the network or execute an installer")

    monkeypatch.setattr(patches, "urlopen", forbidden)
    monkeypatch.setattr(github_releases, "urlopen", forbidden)
    monkeypatch.setattr(downloader, "urlopen", forbidden)
    monkeypatch.setattr(installer.subprocess, "Popen", forbidden)


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "installed"
    root.mkdir()
    (root / "FPVS Studio.exe").write_bytes(b"base executable")
    (root / "_internal").mkdir()
    (root / "_internal" / "keep.dll").write_bytes(b"retained dependency")
    raw = (
        "FPVS-STUDIO-OWNED-FILES-1\r\nkind=current\r\nversion=1.5.0\r\n"
        f"FPVS Studio.exe|{_hash(b'base executable')}\r\n"
        f"_internal/keep.dll|{_hash(b'retained dependency')}\r\n"
    ).encode("utf-8-sig")
    (root / patches.INVENTORY_NAME).write_bytes(raw)
    asset = InstallerAsset(
        name=f"FPVS-Studio-Patch-{BASE}-to-{TARGET}.exe",
        download_url=f"https://github.com/zcm58/FPVS-Studio-2.0/releases/download/v{TARGET}/FPVS-Studio-Patch-{BASE}-to-{TARGET}.exe",
        size_bytes=len(PATCH_BYTES),
        sha256=_hash(PATCH_BYTES),
        version=TARGET,
        asset_id=123,
        kind="patch",
        from_version=BASE,
        source_inventory_sha256=_hash(raw),
    )
    patch_metadata = _github_asset(asset.name, PATCH_BYTES)
    document = {
        "schema_version": 1,
        "target_version": TARGET,
        "platform": "windows-x64",
        "patches": [
            {
                "from_version": BASE,
                "source_inventory_sha256": _hash(raw),
                "asset_name": asset.name,
                "size_bytes": len(PATCH_BYTES),
                "sha256": _hash(PATCH_BYTES),
            }
        ],
    }
    release = {
        "tag_name": f"v{TARGET}",
        "assets": [
            _github_asset(f"FPVS-Studio-Setup-{TARGET}.exe", b"full installer"),
            patch_metadata,
        ],
    }
    monkeypatch.setattr(patches, "installed_patch_root", lambda: root)
    monkeypatch.setattr(patches, "__version__", BASE)
    return root, asset, document, release


def _serve_manifest(monkeypatch: pytest.MonkeyPatch, document, release):
    payload = json.dumps(document).encode()
    metadata = _github_asset(f"FPVS-Studio-Update-{TARGET}.json", payload)
    release["assets"] = [item for item in release["assets"] if not item["name"].endswith(".json")]
    release["assets"].append(metadata)
    response = Response(payload, metadata["browser_download_url"])
    monkeypatch.setattr(patches, "urlopen", lambda *_args, **_kwargs: response)
    return response, metadata


def _select(release, current=BASE):
    return select_update_from_releases([release], current_version=current, resolve_patches=True)


def test_authenticated_patch_selection_checks_real_retained_files(fixture, monkeypatch):
    root, asset, document, release = fixture
    response, _ = _serve_manifest(monkeypatch, document, release)
    result = _select(release)
    assert result.installer_asset == asset
    assert result.download_kind == "patch"
    assert response.closed
    (root / "_internal" / "keep.dll").write_bytes(b"changed dependency!")
    _serve_manifest(monkeypatch, document, release)
    result = _select(release)
    assert result.download_kind == "full"
    assert "installed files do not match" in result.selection_reason


@pytest.mark.parametrize(
    "change", ["missing_inventory", "inventory_digest", "missing_file", "wrong_version"]
)
def test_incompatible_base_explicitly_selects_full(fixture, monkeypatch, change):
    root, _, document, release = fixture
    current = BASE
    if change == "missing_inventory":
        (root / patches.INVENTORY_NAME).unlink()
    elif change == "inventory_digest":
        (root / patches.INVENTORY_NAME).write_bytes(b"untrusted ownership receipt")
    elif change == "missing_file":
        (root / "_internal" / "keep.dll").unlink()
    else:
        current = "1.4.0"
    _serve_manifest(monkeypatch, document, release)
    result = _select(release, current)
    assert result.download_kind == "full"
    assert result.selection_reason


def test_source_build_never_fetches_patch_manifest(fixture, monkeypatch):
    _, _, document, release = fixture
    _serve_manifest(monkeypatch, document, release)
    monkeypatch.setattr(patches, "installed_patch_root", lambda: None)
    monkeypatch.setattr(patches, "urlopen", lambda *_a, **_k: pytest.fail("source must not fetch"))
    assert _select(release).download_kind == "full"


@pytest.mark.parametrize(
    "change",
    [
        "target",
        "platform",
        "schema",
        "sha256",
        "size",
        "url",
        "base_hash",
        "duplicate",
        "wrong_name",
        "missing_asset",
    ],
)
def test_untrusted_manifest_or_patch_identity_fails_closed(fixture, monkeypatch, change):
    _, _, document, release = fixture
    row = document["patches"][0]
    if change == "target":
        document["target_version"] = "9.0.0"
    elif change == "platform":
        document["platform"] = "linux"
    elif change == "schema":
        document["schema_version"] = True
    elif change == "sha256":
        row["sha256"] = "a" * 64
    elif change == "size":
        row["size_bytes"] += 1
    elif change == "url":
        release["assets"][1]["browser_download_url"] = "https://example.com/patch.exe"
    elif change == "base_hash":
        row["source_inventory_sha256"] = "invalid"
    elif change == "duplicate":
        document["patches"].append(dict(row))
    elif change == "wrong_name":
        row["asset_name"] = "FPVS-Studio-Patch-1.0.0-to-1.5.1.exe"
    elif change == "missing_asset":
        release["assets"].pop()
    _serve_manifest(monkeypatch, document, release)
    with pytest.raises(UpdateError):
        _select(release)


@pytest.mark.parametrize("change", ["digest", "size", "url", "id", "overflow", "truncated"])
def test_manifest_transfer_binds_github_digest_size_and_url(fixture, monkeypatch, change):
    _, _, document, release = fixture
    response, metadata = _serve_manifest(monkeypatch, document, release)
    if change == "digest":
        metadata["digest"] = "sha256:" + "a" * 64
    elif change == "size":
        metadata["size"] = patches.MAX_PATCH_METADATA_BYTES + 1
    elif change == "url":
        metadata["browser_download_url"] = (
            "https://github.com/someone/else/releases/download/v1.5.1/file.json"
        )
    elif change == "id":
        metadata["id"] = True
    elif change == "overflow":
        response.headers = {}
        metadata["size"] -= 1
    elif change == "truncated":
        response.headers = {}
        metadata["size"] += 1
    with pytest.raises(UpdateError):
        _select(release)


def test_metadata_cancellation_after_read_does_not_fall_back(fixture, monkeypatch):
    _, _, document, release = fixture
    response, _ = _serve_manifest(monkeypatch, document, release)
    event = Event()

    def canceled_read(size):
        data = io.BytesIO.read(response, size)
        event.set()
        return data

    monkeypatch.setattr(response, "read1", canceled_read)
    with pytest.raises(UpdateCancelled):
        select_update_from_releases(
            [release], current_version=BASE, resolve_patches=True, cancel_event=event
        )
    assert response.closed


def test_download_reuse_receipt_retains_patch_identity_and_prunes_at_target(
    fixture, tmp_path, monkeypatch
):
    _, asset, _, _ = fixture
    cache = tmp_path / "cache"
    response = Response(PATCH_BYTES, asset.download_url)
    monkeypatch.setattr(downloader, "urlopen", lambda *_a, **_k: response)
    downloaded = download_installer(asset, destination_dir=cache)
    monkeypatch.setattr(downloader, "urlopen", lambda *_a, **_k: pytest.fail("cached reuse"))
    assert download_installer(asset, destination_dir=cache) == downloaded
    receipt = json.loads((cache / receipt_name(asset.name)).read_text())
    assert receipt["kind"] == "patch"
    assert receipt["source_inventory_sha256"] == asset.source_inventory_sha256
    assert cleanup_update_cache(BASE, cache_dir=cache).kept_installer == downloaded.path
    assert cleanup_update_cache(TARGET, cache_dir=cache).kept_installer is None
    assert not downloaded.path.exists()


def test_changed_base_blocks_patch_download_before_network_or_cache_write(fixture, tmp_path):
    root, asset, _, _ = fixture
    (root / "_internal" / "keep.dll").write_bytes(b"changed")
    cache = tmp_path / "cache"
    with pytest.raises(UpdateIntegrityError, match="Check for updates again"):
        download_installer(asset, destination_dir=cache)
    assert not cache.exists()


def test_launch_rechecks_baseline_and_passes_actual_install_directory(
    fixture, tmp_path, monkeypatch
):
    root, asset, _, _ = fixture
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=tmp_path / "cache")
    calls = []
    marker = object()
    monkeypatch.setattr(
        installer.subprocess, "Popen", lambda command, **kwargs: calls.append(command) or marker
    )
    assert launch_installer(downloaded) is marker
    assert calls == [[str(downloaded.path), f"/DIR={root}", "/RELAUNCH=1"]]
    (root / "_internal" / "keep.dll").write_bytes(b"modified after download")
    with pytest.raises(UpdateIntegrityError, match="Check for updates again"):
        launch_installer(downloaded)
    assert len(calls) == 1


@pytest.mark.parametrize("suffix", ["", ".part", "." + "a" * 32 + ".part", ".verified.json"])
def test_patch_cache_names_recognize_target_version(suffix):
    assert recognized_cache_entry(f"FPVS-Studio-Patch-{BASE}-to-{TARGET}.exe{suffix}") is not None
    assert recognized_cache_entry(f"FPVS-Studio-Patch-{TARGET}-to-{BASE}.exe{suffix}") is None


def test_patch_receipt_cannot_masquerade_as_full_installer(fixture):
    _, asset, _, _ = fixture
    with pytest.raises(UpdateError):
        validate_asset_identity(replace(asset, kind="full"))


def test_hardlinked_retained_file_never_qualifies(fixture, tmp_path, monkeypatch):
    root, _, document, release = fixture
    os.link(root / "_internal" / "keep.dll", tmp_path / "alias.dll")
    _serve_manifest(monkeypatch, document, release)
    result = _select(release)
    assert result.download_kind == "full"
    assert "installed files do not match" in result.selection_reason


@pytest.mark.parametrize(
    "relative",
    [
        "../outside.txt",
        "_internal/../outside.txt",
        "C:/absolute.dll",
        "_internal/NUL.dll",
        "logs/data.csv",
        "fpvs-patch-transaction-v1.txt",
    ],
)
def test_authenticated_inventory_still_requires_safe_relative_paths(fixture, relative):
    root, asset, _, _ = fixture
    raw = (
        f"FPVS-STUDIO-OWNED-FILES-1\r\nkind=current\r\nversion={BASE}\r\n{relative}|{'a' * 64}\r\n"
    ).encode("utf-8-sig")
    (root / patches.INVENTORY_NAME).write_bytes(raw)
    with pytest.raises(UpdateIntegrityError, match="unsafe file path"):
        patches.verify_patch_baseline(
            replace(asset, source_inventory_sha256=_hash(raw)), root, BASE
        )


def test_offline_receipt_tampering_cannot_authorize_patch_launch(fixture, tmp_path, monkeypatch):
    _, asset, _, _ = fixture
    cache = tmp_path / "cache"
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=cache)
    downloaded.path.write_bytes(b"evil!")
    forged = replace(asset, sha256=_hash(b"evil!"))
    (cache / receipt_name(asset.name)).write_text(json.dumps({"schema": 1, **asdict(forged)}))
    with pytest.raises(UpdateIntegrityError, match="SHA-256"):
        launch_installer(downloaded)


def test_normal_update_check_discovers_patch_without_executable_download(fixture, monkeypatch):
    _, asset, document, release = fixture
    _serve_manifest(monkeypatch, document, release)
    response = Response(json.dumps([release]).encode(), github_releases.DEFAULT_RELEASES_API_URL)
    monkeypatch.setattr(github_releases, "urlopen", lambda *_a, **_k: response)
    result = github_releases.check_for_updates(current_version=BASE)
    assert result.installer_asset == asset
    assert response.closed


def test_patch_larger_than_full_uses_full(fixture, monkeypatch):
    _, _, document, release = fixture
    release["assets"][0] = _github_asset(f"FPVS-Studio-Setup-{TARGET}.exe", b"tiny")
    _serve_manifest(monkeypatch, document, release)
    result = _select(release)
    assert result.download_kind == "full"
    assert "smaller download" in result.selection_reason


def test_metadata_total_deadline_is_checked_after_read(fixture, monkeypatch):
    _, _, document, release = fixture
    response, _ = _serve_manifest(monkeypatch, document, release)
    ticks = iter([0, 0, patches.MAX_PATCH_METADATA_SECONDS + 1])
    monkeypatch.setattr(patches.time, "monotonic", lambda: next(ticks))
    with pytest.raises(UpdateError, match="time limit"):
        _select(release)
    assert response.closed


def test_duplicate_json_fields_rejected_before_patch_selection(fixture, monkeypatch):
    _, _, document, release = fixture
    response, metadata = _serve_manifest(monkeypatch, document, release)
    response.close()
    raw = b'{"schema_version":1,"schema_version":1}'
    metadata.update(size=len(raw), digest=f"sha256:{_hash(raw)}")
    response = Response(raw, metadata["browser_download_url"])
    monkeypatch.setattr(patches, "urlopen", lambda *_a, **_k: response)
    with pytest.raises(UpdateIntegrityError, match="duplicate JSON"):
        _select(release)


@pytest.mark.parametrize("limit", ["MAX_INVENTORY_BYTES", "MAX_INVENTORY_FILES", "MAX_BASE_BYTES"])
def test_baseline_verification_is_bounded(fixture, monkeypatch, limit):
    root, asset, _, _ = fixture
    monkeypatch.setattr(patches, limit, 1)
    with pytest.raises(UpdateIntegrityError):
        patches.verify_patch_baseline(asset, root, BASE)


def test_base_hash_cancellation_propagates_without_full_fallback(fixture, monkeypatch):
    _, _, document, release = fixture
    _serve_manifest(monkeypatch, document, release)
    event = Event()
    original = patches.guarded_read_path

    def cancel_file_read(path, **kwargs):
        if path.name == "keep.dll":
            event.set()
        return original(path, **kwargs)

    monkeypatch.setattr(patches, "guarded_read_path", cancel_file_read)
    with pytest.raises(UpdateCancelled):
        select_update_from_releases(
            [release], current_version=BASE, resolve_patches=True, cancel_event=event
        )


def test_patch_cancel_discards_staging_and_retry_starts_from_zero(fixture, tmp_path, monkeypatch):
    _, asset, _, _ = fixture
    cache = tmp_path / "cache"
    event = Event()
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    with pytest.raises(UpdateCancelled):
        download_installer(
            asset,
            destination_dir=cache,
            cancel_event=event,
            progress_callback=lambda *_a: event.set(),
        )
    assert not any(recognized_cache_entry(path.name) for path in cache.iterdir())
    event.clear()
    result = download_installer(asset, destination_dir=cache, cancel_event=event)
    assert result.path.read_bytes() == PATCH_BYTES


def test_changed_running_version_blocks_previously_downloaded_patch(fixture, tmp_path, monkeypatch):
    _, asset, _, _ = fixture
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=tmp_path / "cache")
    monkeypatch.setattr(patches, "__version__", "1.4.0")
    with pytest.raises(UpdateIntegrityError, match="no longer matches"):
        launch_installer(downloaded)


def test_cancellation_during_final_base_verification_prevents_popen(fixture, tmp_path, monkeypatch):
    _, asset, _, _ = fixture
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=tmp_path / "cache")
    event = Event()
    original = patches.verify_patch_baseline

    def cancel_after_hash(*args, **kwargs):
        original(*args, **kwargs)
        event.set()

    monkeypatch.setattr(patches, "verify_patch_baseline", cancel_after_hash)
    with pytest.raises(UpdateCancelled):
        launch_installer(downloaded, cancel_event=event)


def test_startup_removes_patch_for_a_different_installed_base(fixture, tmp_path, monkeypatch):
    _, asset, _, _ = fixture
    cache = tmp_path / "cache"
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=cache)
    result = cleanup_update_cache("1.4.0", cache_dir=cache)
    assert not result.warnings
    assert result.kept_installer is None
    assert not downloaded.path.exists()


def test_full_download_prunes_cached_patch_and_recognized_partials(fixture, tmp_path, monkeypatch):
    _, asset, _, release = fixture
    cache = tmp_path / "cache"
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(PATCH_BYTES, asset.download_url)
    )
    downloaded = download_installer(asset, destination_dir=cache)
    (cache / (asset.name + ".part")).write_bytes(b"partial")
    (cache / "notes.txt").write_text("user-owned")
    full = select_update_from_releases([release], current_version=BASE).installer_asset
    monkeypatch.setattr(
        downloader, "urlopen", lambda *_a, **_k: Response(b"full installer", full.download_url)
    )
    full_download = download_installer(full, destination_dir=cache)
    assert not downloaded.path.exists()
    assert not (cache / (asset.name + ".part")).exists()
    assert not (cache / receipt_name(asset.name)).exists()
    assert full_download.path.exists()
    assert (cache / "notes.txt").read_text() == "user-owned"


@pytest.mark.parametrize("change", [None, "missing", "version", "location", "value_type"])
def test_patch_requires_exact_registered_windows_install(tmp_path, monkeypatch, change):
    # No production registry reads, and do not resolve a possibly linked root.
    calls = []
    values = {
        "InstallLocation": (str(tmp_path), 1),
        "DisplayVersion": (BASE, 1),
    }
    if change == "version":
        values["DisplayVersion"] = ("1.4.0", 1)
    elif change == "location":
        values["InstallLocation"] = (str(tmp_path / "elsewhere"), 1)
    elif change == "value_type":
        values["InstallLocation"] = (str(tmp_path), 2)

    def open_key(*args):
        calls.append(args)
        if change == "missing":
            raise FileNotFoundError("unregistered portable copy")
        return nullcontext("registration")

    registry = SimpleNamespace(
        OpenKey=open_key,
        QueryValueEx=lambda _key, value: values[value],
        HKEY_CURRENT_USER=1,
        KEY_READ=2,
        KEY_WOW64_64KEY=4,
        REG_SZ=1,
    )
    monkeypatch.setitem(sys.modules, "winreg", registry)
    monkeypatch.setattr(
        patches,
        "sys",
        SimpleNamespace(
            platform="win32",
            frozen=True,
            maxsize=2**63,
            executable=str(tmp_path / "FPVS Studio.exe"),
        ),
    )
    monkeypatch.setattr(patches, "platform", SimpleNamespace(machine=lambda: "AMD64"))
    monkeypatch.setattr(patches, "__version__", BASE)
    assert patches.installed_patch_root() == (tmp_path if change is None else None)
    assert calls == [(1, patches._UNINSTALL_KEY, 0, 6)]


@pytest.mark.parametrize(
    "platform_name,machine,frozen",
    [
        ("linux", "x86_64", True),
        ("win32", "ARM64", True),
        ("win32", "AMD64", False),
    ],
)
def test_unsupported_platform_never_reads_install_registration(
    tmp_path, monkeypatch, platform_name, machine, frozen
):
    monkeypatch.setattr(
        patches,
        "sys",
        SimpleNamespace(
            platform=platform_name,
            frozen=frozen,
            maxsize=2**63,
            executable=str(tmp_path / "FPVS Studio.exe"),
        ),
    )
    monkeypatch.setattr(patches, "platform", SimpleNamespace(machine=lambda: machine))
    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            OpenKey=lambda *_a: pytest.fail("unsupported build must not read registry"),
        ),
    )
    assert patches.installed_patch_root() is None
