"""Secure storage adapters fail closed and never expose a plaintext fallback."""

from __future__ import annotations

import ctypes
import json
from types import SimpleNamespace

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.library import credentials
from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import DeviceCredential


def credential():
    return DeviceCredential(token="t" * 43, device_name="Synthetic machine", library_api_version=2)


def test_untagged_secure_credential_is_recognized_as_previous_protocol():
    raw = '{"token":"' + "t" * 43 + '","device_name":"Old PC"}'
    assert credentials._decode(raw).library_api_version == 1


@pytest.mark.parametrize("version", [0, 3, "2", True])
def test_unsupported_credential_protocol_is_rejected(version):
    raw = credential().model_dump()
    raw["library_api_version"] = version
    with pytest.raises(LibraryError, match="invalid"):
        credentials._decode(json.dumps(raw))


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
    set_module_platform(monkeypatch, credentials, "win32")
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


def test_macos_selects_only_explicit_keychain_backend(monkeypatch):
    requested = []
    backend = SimpleNamespace(priority=5)

    def load(name):
        requested.append(name)
        return SimpleNamespace(Keyring=lambda: backend)

    monkeypatch.setattr(credentials.importlib, "import_module", load)
    assert credentials.MacOSKeychainCredentialStore._backend() is backend
    assert requested == ["keyring.backends.macOS"]


@pytest.mark.parametrize("failure", ["missing", "disabled"])
def test_macos_unavailable_keychain_fails_closed_without_private_diagnostics(monkeypatch, failure):
    def load(_name):
        if failure == "missing":
            raise ImportError("private backend details " + "t" * 43)
        return SimpleNamespace(Keyring=lambda: SimpleNamespace(priority=0))

    monkeypatch.setattr(credentials.importlib, "import_module", load)
    with pytest.raises(LibraryError, match="macOS Keychain") as error:
        credentials.MacOSKeychainCredentialStore._backend()
    assert "private" not in str(error.value)
    assert "t" * 43 not in str(error.value)


def test_macos_keychain_roundtrip_and_missing_delete_use_only_native_backend(monkeypatch):
    values = {}
    deletes = []

    class Backend:
        def get_password(self, target, username):
            return values.get((target, username))

        def set_password(self, target, username, value):
            values[target, username] = value

        def delete_password(self, target, username):
            deletes.append((target, username))
            del values[target, username]

    monkeypatch.setattr(credentials.MacOSKeychainCredentialStore, "_backend", staticmethod(Backend))
    store = credentials.MacOSKeychainCredentialStore("synthetic-keychain-target")
    assert store.load() is None
    store.delete()
    assert not deletes
    store.save(credential())
    assert store.load() == credential()
    assert list(values) == [("synthetic-keychain-target", "device")]
    store.delete()
    assert store.load() is None
    assert deletes == [("synthetic-keychain-target", "device")]


@pytest.mark.parametrize("operation", ["load", "save", "delete"])
def test_macos_denied_or_locked_operations_are_explicit_and_redacted(monkeypatch, operation):
    secret = "t" * 43

    def fail(*_args):
        raise RuntimeError("Denied private keychain value " + secret)

    backend = SimpleNamespace(get_password=fail, set_password=fail, delete_password=fail)
    monkeypatch.setattr(credentials.MacOSKeychainCredentialStore, "_backend",
                        staticmethod(lambda: backend))
    store = credentials.MacOSKeychainCredentialStore("synthetic")
    with pytest.raises(LibraryError, match="macOS Keychain") as error:
        if operation == "save":
            store.save(credential())
        else:
            getattr(store, operation)()
    assert secret not in str(error.value)
    assert "private" not in str(error.value)
    assert error.value.__cause__ is None


def test_macos_rejects_oversized_metadata_before_backend_access(monkeypatch):
    def forbidden():
        raise AssertionError("Native backend must not be touched")

    monkeypatch.setattr(
        credentials.MacOSKeychainCredentialStore, "_backend", staticmethod(forbidden),
    )
    monkeypatch.setattr(credentials, "MAX_CREDENTIAL_BYTES", 1)
    with pytest.raises(LibraryError, match="storage limits"):
        credentials.MacOSKeychainCredentialStore("synthetic").save(credential())


def test_macos_library_and_results_have_separate_targets_and_shared_dispatch(monkeypatch, tmp_path):
    from fpvs_studio.data_sharing.credentials import sharing_credential_store

    set_module_platform(monkeypatch, credentials, "darwin")
    library = credentials.credential_store("https://one.example")
    another_origin = credentials.credential_store("https://two.example")
    results = sharing_credential_store("https://one.example", tmp_path, "a" * 64)
    moved = sharing_credential_store("https://one.example", tmp_path / "copy", "a" * 64)
    changed_protocol = sharing_credential_store("https://one.example", tmp_path, "b" * 64)
    stores = (library, another_origin, results, moved, changed_protocol)
    assert all(isinstance(store, credentials.MacOSKeychainCredentialStore) for store in stores)
    assert len({store.target for store in stores}) == 5
    assert library.target.startswith("FPVS-Studio/Experiment-Library/")
    assert results.target.startswith("FPVS-Studio/Data-Sharing/")
    assert str(tmp_path) not in results.target


def test_unsupported_results_credential_platform_keeps_error_contract(monkeypatch, tmp_path):
    from fpvs_studio.data_sharing.credentials import sharing_credential_store
    from fpvs_studio.data_sharing.errors import DataSharingError

    set_module_platform(monkeypatch, credentials, "freebsd")
    with pytest.raises(DataSharingError) as error:
        sharing_credential_store("https://example.test", tmp_path, "a" * 64)
    assert error.value.code == "credential_store"
