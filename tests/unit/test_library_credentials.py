"""Secure storage adapters fail closed and never expose a plaintext fallback."""

from __future__ import annotations

import ctypes
from types import SimpleNamespace

import pytest

from fpvs_studio.library import credentials
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import DeviceCredential


def credential():
    return DeviceCredential(token="t" * 43, device_name="Synthetic machine")


def test_windows_roundtrip_uses_machine_local_generic_credential(monkeypatch):
    stored = {}
    freed = []

    class Api:
        def CredWriteW(self, pointer, flags):
            value = ctypes.cast(pointer, ctypes.POINTER(credentials._Credential)).contents
            assert flags == 0
            assert value.Type == 1
            assert value.Persist == 2
            stored[value.TargetName] = ctypes.string_at(
                value.CredentialBlob, value.CredentialBlobSize
            )
            return 1

        def CredReadW(self, target, kind, flags, out_pointer):
            assert kind == 1 and flags == 0
            raw = stored[target]
            self.blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
            self.value = credentials._Credential()
            self.value.CredentialBlobSize = len(raw)
            self.value.CredentialBlob = ctypes.cast(self.blob, ctypes.POINTER(ctypes.c_ubyte))
            ctypes.cast(out_pointer, ctypes.POINTER(ctypes.POINTER(credentials._Credential)))[0] = (
                ctypes.pointer(self.value)
            )
            return 1

        def CredFree(self, pointer):
            freed.append(True)

        def CredDeleteW(self, target, kind, flags):
            assert kind == 1 and flags == 0
            del stored[target]
            return 1

    api = Api()
    monkeypatch.setattr(credentials.WindowsCredentialStore, "_api", staticmethod(lambda: api))
    store = credentials.WindowsCredentialStore("test-target")
    store.save(credential())
    assert store.load() == credential()
    assert freed == [True]
    assert "t" * 43 not in repr(credential())
    store.delete()
    assert stored == {}


@pytest.mark.parametrize("error, expected", [(1168, None), (5, LibraryError)])
def test_windows_missing_and_denied_are_distinct(monkeypatch, error, expected):
    api = SimpleNamespace(CredReadW=lambda *args: 0)
    monkeypatch.setattr(credentials.WindowsCredentialStore, "_api", staticmethod(lambda: api))
    monkeypatch.setattr(ctypes, "get_last_error", lambda: error, raising=False)
    store = credentials.WindowsCredentialStore("test")
    if expected is None:
        assert store.load() is None
    else:
        with pytest.raises(expected):
            store.load()


def test_windows_write_failure_stays_explicit(monkeypatch):
    api = SimpleNamespace(CredWriteW=lambda *args: 0)
    monkeypatch.setattr(credentials.WindowsCredentialStore, "_api", staticmethod(lambda: api))
    with pytest.raises(LibraryError, match="Could not save"):
        credentials.WindowsCredentialStore("test").save(credential())


def test_service_origins_have_separate_credential_targets(monkeypatch):
    monkeypatch.setattr(credentials.sys, "platform", "win32")
    first = credentials.credential_store("https://one.example")
    second = credentials.credential_store("https://two.example")
    assert first.target != second.target
    assert first.target.startswith("FPVS-Studio/Experiment-Library/")


def test_linux_selects_only_secret_service(monkeypatch):
    requested = []
    backend = SimpleNamespace(priority=1)

    def load(name):
        requested.append(name)
        return SimpleNamespace(Keyring=lambda: backend)

    monkeypatch.setattr(credentials.importlib, "import_module", load)
    assert credentials.SecretServiceCredentialStore._backend() is backend
    assert requested == ["keyring.backends.SecretService"]


def test_linux_missing_or_locked_secret_service_fails_closed(monkeypatch):
    def unavailable(name):
        raise ImportError("private backend diagnostic")

    monkeypatch.setattr(credentials.importlib, "import_module", unavailable)
    with pytest.raises(LibraryError, match="Secret Service") as error:
        credentials.SecretServiceCredentialStore._backend()
    assert "private" not in str(error.value)


def test_linux_adapter_roundtrip_uses_only_os_backend(monkeypatch):
    values = {}

    class Backend:
        def get_password(self, target, username):
            return values.get((target, username))

        def set_password(self, target, username, value):
            values[target, username] = value

        def delete_password(self, target, username):
            del values[target, username]

    monkeypatch.setattr(credentials.SecretServiceCredentialStore, "_backend", staticmethod(Backend))
    store = credentials.SecretServiceCredentialStore("synthetic")
    assert store.load() is None
    store.save(credential())
    assert store.load() == credential()
    store.delete()
    assert store.load() is None


@pytest.mark.parametrize(
    "raw", ["{}", "not json", "x" * 2561, '{"token":"bad","device_name":"machine"}']
)
def test_invalid_stored_credentials_are_rejected(raw):
    with pytest.raises(LibraryError, match="invalid"):
        credentials._decode(raw)
