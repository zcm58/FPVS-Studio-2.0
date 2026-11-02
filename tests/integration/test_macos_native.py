"""Opt-in hosted Mac OS-service checks; no windows, playback or EEG are opened.

Run only on a disposable/authorized Mac with FPVS_MACOS_NATIVE_CHECKS=1. The
Keychain item and Trash file have unique synthetic identities and are cleaned up.
Display metadata is diagnostic: a hosted VM cannot qualify a physical display.
"""

from __future__ import annotations

import importlib
import os
import platform
import sys
import uuid
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin" or os.environ.get("FPVS_MACOS_NATIVE_CHECKS") != "1",
    reason="requires an authorized Mac with FPVS_MACOS_NATIVE_CHECKS=1",
)


def test_native_source_dependencies_import_without_opening_windows(record_property) -> None:
    for module in ("AppKit", "Foundation", "objc", "keyring.backends.macOS", "psychopy", "pyglet"):
        importlib.import_module(module)
    for distribution in ("psychopy", "pyglet", "PySide6", "pyobjc-framework-Cocoa", "keyring"):
        record_property(distribution, version(distribution))
    record_property("macos", platform.mac_ver()[0])
    record_property("cpu", platform.machine())
    assert sys.version_info[:2] == (3, 10)


def test_native_display_api_links_and_reports_fixed_mode_or_explicit_unknown(
    record_property,
) -> None:
    from fpvs_studio.runtime.display_mode import DisplayModeError, query_primary_native_display_mode
    from fpvs_studio.runtime.macos_display import _load_core_graphics

    assert _load_core_graphics().CGMainDisplayID() >= 0
    try:
        mode = query_primary_native_display_mode()
    except DisplayModeError as exc:
        assert str(exc).strip()
        record_property("native_display_diagnostic", str(exc))
    else:
        assert mode.platform_name == "macOS"
        assert mode.refresh_hz > 0
        record_property("native_display_diagnostic", mode.mode_text)
    record_property("physical_display_qualified", "false")


def test_native_keychain_roundtrip_uses_and_cleans_only_a_unique_synthetic_entry() -> None:
    from fpvs_studio.library.credentials import MacOSKeychainCredentialStore
    from fpvs_studio.library.models import DeviceCredential

    target = f"FPVS-Studio/CI/{uuid.uuid4().hex}"
    store = MacOSKeychainCredentialStore(target)
    credential = DeviceCredential(
        token="synthetic_ci_" + uuid.uuid4().hex + uuid.uuid4().hex,
        device_name="Synthetic macOS CI",
        library_api_version=2,
    )
    try:
        assert store.load() is None
        store.save(credential)
        assert MacOSKeychainCredentialStore(target).load() == credential
        store.delete()
        assert store.load() is None
    finally:
        store.delete()


def test_native_trash_moves_and_cleans_only_a_task_owned_temporary_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from fpvs_studio.gui import native_files

    foundation = importlib.import_module("Foundation")
    native_manager = foundation.NSFileManager.defaultManager()
    filename = f"fpvs-ci-{uuid.uuid4().hex}.txt"
    original = tmp_path / filename
    payload = b"Synthetic FPVS macOS Trash acceptance file."
    original.write_bytes(payload)
    trashed: list[Path] = []

    def _trash(url, result_url, error_pointer):
        result = native_manager.trashItemAtURL_resultingItemURL_error_(
            url, result_url, error_pointer,
        )
        if result[0] and result[1] is not None:
            trashed.append(Path(str(result[1].path())))
        return result

    # Instrument the result URL while calling the actual native NSFileManager.
    wrapped = SimpleNamespace(
        NSURL=foundation.NSURL,
        NSFileManager=SimpleNamespace(defaultManager=lambda: SimpleNamespace(
            trashItemAtURL_resultingItemURL_error_=_trash,
        )),
    )
    monkeypatch.setattr(native_files, "_macos_framework", lambda _name: wrapped)
    try:
        native_files.move_to_macos_trash(original)
        assert not original.exists()
        assert len(trashed) == 1
        assert trashed[0].name == filename
        assert trashed[0].read_bytes() == payload
    finally:
        for item in trashed:
            if item.name == filename and item.is_file():
                item.unlink()
