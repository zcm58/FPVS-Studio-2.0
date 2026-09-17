"""OS-protected device access; deliberately no file-backed credential fallback."""

from __future__ import annotations

import ctypes
import hashlib
import importlib
import sys
from ctypes import wintypes
from typing import Any, Protocol

from fpvs_studio.library.errors import LibraryError
from fpvs_studio.library.models import DeviceCredential

MAX_CREDENTIAL_BYTES = 2560  # Windows generic credential blob limit.


class CredentialStore(Protocol):
    def load(self) -> DeviceCredential | None: ...

    def save(self, credential: DeviceCredential) -> None: ...

    def delete(self) -> None: ...


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _decode(value: str) -> DeviceCredential:
    try:
        if len(value.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
            raise ValueError("credential too large")
        return DeviceCredential.model_validate_json(value)
    except (ValueError, UnicodeError):
        raise LibraryError(
            "Stored Library access is invalid. Remove it in your OS credential manager."
        ) from None


class WindowsCredentialStore:
    def __init__(self, target: str) -> None:
        self.target = target

    @staticmethod
    def _api() -> Any:
        try:
            api = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
            api.CredReadW.argtypes = [
                wintypes.LPCWSTR,
                wintypes.DWORD,
                wintypes.DWORD,
                ctypes.POINTER(ctypes.POINTER(_Credential)),
            ]
            api.CredReadW.restype = wintypes.BOOL
            api.CredWriteW.argtypes = [ctypes.POINTER(_Credential), wintypes.DWORD]
            api.CredWriteW.restype = wintypes.BOOL
            api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
            api.CredDeleteW.restype = wintypes.BOOL
            api.CredFree.argtypes = [ctypes.c_void_p]
            api.CredFree.restype = None
            return api
        except (AttributeError, OSError):
            raise LibraryError(
                "Windows Credential Manager is unavailable. Library access was not saved."
            ) from None

    def load(self) -> DeviceCredential | None:
        api = self._api()
        pointer = ctypes.POINTER(_Credential)()
        if not api.CredReadW(self.target, 1, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == 1168:  # ERROR_NOT_FOUND
                return None
            raise LibraryError("Could not read Library access from Windows Credential Manager.")
        try:
            if pointer.contents.CredentialBlobSize > MAX_CREDENTIAL_BYTES:
                raise LibraryError("Stored Library access exceeds the supported size.")
            raw = ctypes.string_at(
                pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize
            )
            try:
                return _decode(raw.decode("utf-8"))
            except UnicodeError:
                raise LibraryError("Stored Library access is invalid.") from None
        finally:
            api.CredFree(pointer)

    def save(self, credential: DeviceCredential) -> None:
        raw = credential.model_dump_json().encode("utf-8")
        if len(raw) > MAX_CREDENTIAL_BYTES:
            raise LibraryError("Library access metadata exceeds secure storage limits.")
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        value = _Credential()
        value.Type = 1  # CRED_TYPE_GENERIC
        value.TargetName = self.target
        value.CredentialBlobSize = len(raw)
        value.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        value.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE: this OS user, on this machine.
        value.UserName = "FPVS Studio Experiment Library"
        if not self._api().CredWriteW(ctypes.byref(value), 0):
            raise LibraryError("Could not save Library access in Windows Credential Manager.")

    def delete(self) -> None:
        if not self._api().CredDeleteW(self.target, 1, 0) and ctypes.get_last_error() != 1168:
            raise LibraryError("Could not remove Library access from Windows Credential Manager.")


class SecretServiceCredentialStore:
    def __init__(self, target: str) -> None:
        self.target = target

    @staticmethod
    def _backend() -> Any:
        try:
            # Instantiate only this backend, never keyring's automatic backend chooser.
            backend = importlib.import_module("keyring.backends.SecretService").Keyring()
            if backend.priority <= 0:
                raise RuntimeError("unavailable")
            return backend
        except Exception:
            raise LibraryError(
                "Library access requires an unlocked Linux Secret Service keyring. "
                "Install keyring/SecretStorage and start your desktop keyring service."
            ) from None

    def load(self) -> DeviceCredential | None:
        try:
            value = self._backend().get_password(self.target, "device")
        except Exception:
            raise LibraryError("Could not read Library access from Linux Secret Service.") from None
        return _decode(value) if value is not None else None

    def save(self, credential: DeviceCredential) -> None:
        value = credential.model_dump_json()
        if len(value.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
            raise LibraryError("Library access metadata exceeds secure storage limits.")
        try:
            self._backend().set_password(self.target, "device", value)
        except Exception:
            raise LibraryError("Could not save Library access in Linux Secret Service.") from None

    def delete(self) -> None:
        try:
            backend = self._backend()
            if backend.get_password(self.target, "device") is not None:
                backend.delete_password(self.target, "device")
        except Exception:
            raise LibraryError(
                "Could not remove Library access from Linux Secret Service."
            ) from None


def credential_store(service_url: str) -> CredentialStore:
    identity = hashlib.sha256(service_url.encode("utf-8")).hexdigest()
    target = f"FPVS-Studio/Experiment-Library/{identity}"
    if sys.platform == "win32":
        return WindowsCredentialStore(target)
    if sys.platform.startswith("linux"):
        return SecretServiceCredentialStore(target)
    raise LibraryError("Secure Library access is supported on Windows and Linux desktops.")
