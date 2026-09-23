"""Semantic project-version selection never needs an installed release to remain listed."""

from threading import Event

import pytest

from fpvs_studio.core.library_origin import LibraryProjectOrigin
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryCatalog, LibraryItem
from fpvs_studio.library.project_updates import check_project_update, select_project_update


def origin(**changes):
    return LibraryProjectOrigin(**{
        "service_url": "https://library.example.test", "item_id": "masking",
        "installed_version": "1.0.0", "bundle_sha256": "a" * 64,
        "local_project_id": "masking", **changes,
    })


def item(version, **changes):
    return LibraryItem(**{
        "item_id": "masking", "version": version, "title": "Masking",
        "description": "Synthetic", "experiment_category": "fpvs_oddball",
        "filename": "masking.fpvsbundle", "size_bytes": 10,
        "uncompressed_size_bytes": 20, "file_count": 2, "sha256": "a" * 64,
        "min_studio_version": "1.0.0", **changes,
    })


def catalog(*items):
    return LibraryCatalog(schema_version="1.0", library_name="Library", items=list(items))


class Client:
    service_url = "https://library.example.test"

    def __init__(self, result=None, *, connected=True):
        self.result = result or catalog(item("1.1.0"))
        self.connected = connected
        self.calls = []

    def connection_info(self):
        self.calls.append("connection")
        return object() if self.connected else None

    def catalog(self, *, cancel_event=None):
        self.calls.append("catalog")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_selects_newest_semantic_version_when_installed_version_was_withdrawn():
    result = select_project_update(
        origin(), catalog(item("1.9.0"), item("1.10.0"), item("99.0", item_id="other")),
    )
    assert result.status == "update_available"
    assert result.latest_item.version == "1.10.0"
    assert result.can_install


def test_newest_incompatible_version_remains_visible_without_downgrading_candidate():
    result = select_project_update(
        origin(), catalog(item("1.1.0"), item("2.0.0", min_studio_version="99.0.0")),
    )
    assert result.status == "incompatible"
    assert result.latest_item.version == "2.0.0"
    assert "99.0.0" in result.message
    assert not result.can_install


@pytest.mark.parametrize("version", ["0.9.0", "1.0.0"])
def test_no_downgrade_or_repeat_update(version):
    result = select_project_update(origin(), catalog(item(version)))
    assert result.status == "current"
    assert not result.can_install


def test_unknown_legacy_version_is_not_claimed_to_have_an_update():
    receipt = origin(installed_version=None, bundle_sha256=None)
    result = select_project_update(receipt, catalog(item("1.1.0")))
    assert result.status == "version_unknown"
    assert result.origin == receipt
    assert result.can_install


@pytest.mark.parametrize("available", [
    catalog(), catalog(item("1.0"), item("1.0.0")), catalog(item("1.0.0", sha256="b" * 64)),
])
def test_missing_ambiguous_or_changed_release_is_not_reported_current(available):
    result = select_project_update(origin(), available)
    assert result.status == "unavailable"
    assert not result.can_install


@pytest.mark.parametrize("receipt, status", [
    (None, "unlinked"), (origin(auto_check=False), "disabled"),
    (origin(service_url="https://different.example.test"), "unavailable"),
])
def test_unlinked_disabled_or_foreign_origin_never_contacts_client(receipt, status):
    client = Client()
    result = check_project_update(client, receipt)
    assert result.status == status
    assert client.calls == []


def test_manual_check_bypasses_auto_check_preference():
    client = Client()
    assert check_project_update(client, origin(auto_check=False), automatic=False).can_install
    assert client.calls == ["connection", "catalog"]


def test_disconnected_check_does_not_fetch_catalog():
    client = Client(connected=False)
    assert check_project_update(client, origin()).status == "not_connected"
    assert client.calls == ["connection"]


@pytest.mark.parametrize("error, status", [
    (LibraryError("Offline; retry later."), "unavailable"),
    (LibraryAuthorizationError("Reconnect this device."), "not_connected"),
])
def test_service_errors_return_non_destructive_status(error, status):
    receipt = origin()
    result = check_project_update(Client(error), receipt)
    assert result.status == status
    assert result.origin == receipt
    assert result.message == str(error)
    assert not result.can_install


def test_cancellation_propagates_before_or_during_network():
    cancel = Event()
    cancel.set()
    client = Client()
    with pytest.raises(LibraryCancelled):
        check_project_update(client, origin(), cancel_event=cancel)
    assert client.calls == []
    with pytest.raises(LibraryCancelled):
        check_project_update(Client(LibraryCancelled("cancelled")), origin())
