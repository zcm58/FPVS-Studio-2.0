"""Opt-in hosted Mac OS-service checks; no windows, playback or EEG are opened.

Run only on a disposable/authorized Mac with FPVS_MACOS_NATIVE_CHECKS=1. The
Keychain item and Trash file have unique synthetic identities and are cleaned up.
Display metadata is diagnostic: a hosted VM cannot qualify a physical display.
"""

from __future__ import annotations

import importlib
import os
import platform
import secrets
import shlex
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
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


def _security(*arguments: str) -> str:
    return subprocess.run(
        ["/usr/bin/security", *arguments],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout


@contextmanager
def _temporary_ci_keychain(root: Path) -> Iterator[Path]:
    """Isolate OS defaults only on a disposable hosted runner and restore them."""
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
    ):
        pytest.skip("Private Keychain selection requires a disposable GitHub-hosted Mac")
    try:
        previous = shlex.split(_security("default-keychain", "-d", "user"))
    except subprocess.CalledProcessError:
        security = importlib.import_module("Security")
        status, _keychain = security.SecKeychainCopyDomainDefault(
            security.kSecPreferencesDomainUser, None,
        )
        if status != security.errSecNoDefaultKeychain:
            raise
        previous = []
    search_list = shlex.split(_security("list-keychains", "-d", "user"))
    if len(previous) > 1:
        pytest.fail("Cannot safely snapshot the hosted runner's default Keychain")
    keychain = root / f"fpvs-ci-{uuid.uuid4().hex}.keychain-db"
    password = secrets.token_urlsafe(32)
    created = False
    selected = False
    try:
        _security("create-keychain", "-p", password, str(keychain))
        created = True
        _security("set-keychain-settings", "-lut", "3600", str(keychain))
        _security("unlock-keychain", "-p", password, str(keychain))
        selected = True
        _security("list-keychains", "-d", "user", "-s", str(keychain), *search_list)
        _security("default-keychain", "-d", "user", "-s", str(keychain))
        yield keychain
    finally:
        try:
            if selected:
                _security("default-keychain", "-d", "user", "-s", *previous)
        finally:
            try:
                if selected:
                    _security("list-keychains", "-d", "user", "-s", *search_list)
            finally:
                if created:
                    _security("delete-keychain", str(keychain))


@pytest.mark.timeout(120)
def test_native_keychain_roundtrip_uses_and_cleans_only_a_unique_synthetic_entry(
    tmp_path: Path, record_property,
) -> None:
    # keyring 25 ignores KEYCHAIN_PATH; use the actual backend against a temporary
    # OS default. Never unlock the login Keychain or weaken its access controls.
    code = """
import sys
import uuid
from fpvs_studio.library.credentials import MacOSKeychainCredentialStore
from fpvs_studio.library.models import DeviceCredential
store = MacOSKeychainCredentialStore(sys.argv[1])
credential = DeviceCredential(token='synthetic_ci_' + uuid.uuid4().hex + uuid.uuid4().hex,
                              device_name='Synthetic macOS CI', library_api_version=2)
try:
    assert store.load() is None
    store.save(credential)
    assert MacOSKeychainCredentialStore(sys.argv[1]).load() == credential
    store.delete()
    assert store.load() is None
finally:
    store.delete()
"""
    with _temporary_ci_keychain(tmp_path):
        # A blocked Security prompt must fail this check without killing pytest
        # before its fixture restores the original OS selection.
        result = subprocess.run(
            [sys.executable, "-c", code, f"FPVS-Studio/CI/{uuid.uuid4().hex}"],
            capture_output=True, text=True, check=False, timeout=20,
        )
        assert result.returncode == 0, result.stderr
    record_property(
        "keychain_scope", "temporary hosted-runner Keychain, original selection restored",
    )


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


def test_native_child_ipc_rejects_acquisition_before_engine_or_hardware(
    monkeypatch: pytest.MonkeyPatch, sample_project, sample_project_root, record_property,
) -> None:
    from fpvs_studio.core.compiler import compile_session_plan
    from fpvs_studio.core.execution import ParticipantMetadata
    from fpvs_studio.runtime import macos_session_process as process
    from fpvs_studio.runtime.launcher import LaunchSettings

    plan = compile_session_plan(sample_project, project_root=sample_project_root, refresh_hz=60)
    request = process._Request(
        project_root=str(sample_project_root), session_plan=plan, participant_number="001",
        participant_metadata=ParticipantMetadata(),
        launch_settings=asdict(LaunchSettings(
            experiment_test_mode=False, serial_enabled=True, verify_refresh_rate=True,
        )),
    )
    responses = []
    original = process._private_file

    def private_file(path, *, write=None):
        value = original(path, write=write)
        if path.name == "response.json" and write is None:
            responses.append(process._Response.model_validate_json(value))
        return value

    monkeypatch.setattr(process, "_private_file", private_file)
    with pytest.raises(process.MacOSSessionProcessError):
        process._exchange(request)
    assert len(responses) == 1
    assert responses[0].error == "invalid_request"
    assert responses[0].summary is None and responses[0].verification is None
    assert any("_settings" in frame for frame in responses[0].child_traceback)
    record_property(
        "child_ipc", "real private request/response; acquisition rejected before engine",
    )
