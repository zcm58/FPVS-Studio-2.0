"""Developer preference semantics without Qt or real user settings."""

import pytest

from fpvs_studio.developer.mode import DEVELOPER_MODE_KEY, DeveloperMode


class Settings:
    def __init__(self):
        self.values = {}
        self.synced = 0

    def value(self, key, defaultValue=None):
        return self.values.get(key, defaultValue)

    def setValue(self, key, value):
        self.values[key] = value

    def sync(self):
        self.synced += 1


@pytest.mark.parametrize("password", ["", "wrong", "Developer", "developer ", "🔑"])
def test_wrong_password_does_not_write_settings(password):
    settings = Settings()
    mode = DeveloperMode(settings)
    assert not mode.active
    assert not mode.configure(True, password)
    assert settings.values == {}
    assert settings.synced == 0


def test_enabling_and_disabling_require_restart_and_never_store_password():
    settings = Settings()
    mode = DeveloperMode(settings)
    assert mode.configure(True, "developer")
    assert mode.requested and not mode.active and mode.restart_required
    assert settings.values == {DEVELOPER_MODE_KEY: True}
    restarted = DeveloperMode(settings)
    assert restarted.active and not restarted.restart_required
    assert restarted.configure(False)
    assert restarted.active and not restarted.requested and restarted.restart_required
    assert not DeveloperMode(settings).active


def test_reverting_pending_change_removes_restart_requirement():
    mode = DeveloperMode(Settings())
    assert mode.configure(True, "developer")
    assert mode.configure(False)
    assert not mode.restart_required


@pytest.mark.parametrize(
    "value, enabled",
    [(True, True), ("true", True), ("false", False), (False, False), (None, False), ("bad", False)],
)
def test_preference_parsing_fails_closed(value, enabled):
    settings = Settings()
    settings.values[DEVELOPER_MODE_KEY] = value
    assert DeveloperMode(settings).active is enabled
