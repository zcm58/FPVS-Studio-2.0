"""Persistent developer opt-in with a restart-only activation boundary."""

from __future__ import annotations

import hmac
from typing import Protocol

DEVELOPER_MODE_KEY = "developer/enabled"


class PreferenceStore(Protocol):
    def value(self, key: str, defaultValue: object = None) -> object: ...
    def setValue(self, key: str, value: object) -> None: ...
    def sync(self) -> None: ...


class DeveloperMode:
    def __init__(self, settings: PreferenceStore) -> None:
        self._settings = settings
        self.active = self.requested

    @property
    def requested(self) -> bool:
        value = self._settings.value(DEVELOPER_MODE_KEY, False)
        return value is True or (isinstance(value, str) and value.lower() == "true")

    @property
    def restart_required(self) -> bool:
        return self.requested != self.active

    def configure(self, enabled: bool, password: str = "") -> bool:
        if (
            enabled
            and not self.requested
            and not hmac.compare_digest(password.encode("utf-8"), b"developer")
        ):
            return False
        self._settings.setValue(DEVELOPER_MODE_KEY, enabled)
        self._settings.sync()
        return True
