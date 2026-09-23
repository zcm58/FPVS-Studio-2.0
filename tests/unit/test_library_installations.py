"""Installed identity gates both Library downloads and explicit project updates."""

import json
from pathlib import Path
from threading import Event

import pytest
from tests.unit.test_library_project_updates import item, origin

from fpvs_studio.core.library_installations import LibraryInstallStatus, scan_library_projects
from fpvs_studio.core.library_origin import LibraryOriginError, save_library_origin
from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.installations import check_library_install, download_library_install


def project(root, *, project_id="masking", name="Masking", version="1.0", linked=True,
            service_url="https://library.example.test"):
    folder = root / project_id
    folder.mkdir(parents=True)
    (folder / "project.json").write_text(json.dumps({
        "meta": {"project_id": project_id, "name": name, "template_id": "custom"},
    }), encoding="utf-8")
    if linked:
        save_library_origin(folder, origin(
            local_project_id=project_id, installed_version=version, service_url=service_url,
        ))
    return folder


class Client:
    service_url = "https://library.example.test"

    def __init__(self, during_download=lambda: None):
        self.calls = 0
        self.releases = 0
        self.during_download = during_download

    def download(self, item, **kwargs):
        self.calls += 1
        self.during_download()
        return Path("verified.fpvsbundle")

    def release_download(self):
        self.releases += 1


@pytest.mark.parametrize("installed,requested,state", [
    ("1.0", "1.0.0", "installed"), ("1.10", "1.9", "installed"),
    ("1.9", "1.10", "update"), (None, "1.0", "review"),
])
def test_receipt_identity_survives_renamed_title_and_collision_id(
    tmp_path, installed, requested, state,
):
    folder = project(tmp_path, project_id="renamed-from-bundle-2", name="Edited title",
                     version=installed)
    result = check_library_install(tmp_path, Client.service_url, item(requested))
    assert result.state == state
    assert result.project.root == folder


@pytest.mark.parametrize("project_id,name", [
    ("masking", "Edited"), ("masking-from-bundle-2", "Edited"), ("custom", "MASKING"),
])
def test_legacy_candidates_require_review_without_writing_a_receipt(tmp_path, project_id, name):
    folder = project(tmp_path, project_id=project_id, name=name, linked=False)
    result = check_library_install(tmp_path, Client.service_url, item("1.1"))
    assert result.state == "review"
    assert not (folder / ".fpvs-library").exists()


def test_unrelated_linked_title_is_not_identity(tmp_path):
    project(tmp_path, service_url="https://other.example.test")
    assert check_library_install(tmp_path, Client.service_url, item("1.0")).state == "new"


def test_scan_finds_nested_projects_but_skips_payload_and_app_storage(tmp_path):
    folder = project(tmp_path / "group")
    for parent in (folder / "runs", tmp_path / ".fpvs-studio" / "import-staging"):
        parent.mkdir(parents=True)
        (parent / "project.json").write_text("invalid", encoding="utf-8")
    projects = scan_library_projects(tmp_path)
    assert [value.root for value in projects] == [folder]


@pytest.mark.parametrize("update", [False, True])
def test_no_payload_bytes_for_same_or_newer_installed_version(tmp_path, update):
    project(tmp_path, version="1.1")
    client = Client()
    result = download_library_install(client, item("1.0"), tmp_path, update=update)
    assert result.state == "installed"
    assert client.calls == client.releases == 0


@pytest.mark.parametrize("linked", [False, True])
def test_old_or_unknown_copy_requires_explicit_update(tmp_path, linked):
    project(tmp_path, linked=linked)
    client = Client()
    result = download_library_install(client, item("1.1"), tmp_path)
    assert isinstance(result, LibraryInstallStatus)
    assert client.calls == 0
    assert isinstance(download_library_install(client, item("1.1"), tmp_path, update=True), Path)
    assert client.calls == 1


def test_update_does_not_download_release_already_installed_beside_old_project(tmp_path):
    project(tmp_path, version="1.0")
    project(tmp_path, project_id="masking-from-bundle", version="1.1")
    client = Client()
    result = download_library_install(client, item("1.1"), tmp_path, update=True)
    assert result.state == "installed"
    assert client.calls == 0


def test_installation_appearing_during_download_releases_payload_without_import(tmp_path):
    client = Client(lambda: project(tmp_path))
    with pytest.raises(LibraryError, match="already installed"):
        download_library_install(client, item("1.0"), tmp_path)
    assert client.calls == client.releases == 1


@pytest.mark.parametrize("corrupt", ["project", "receipt", "identity"])
def test_unreadable_inventory_fails_closed_before_download(tmp_path, corrupt):
    folder = project(tmp_path)
    if corrupt == "project":
        (folder / "project.json").write_text("not json", encoding="utf-8")
    elif corrupt == "receipt":
        (folder / ".fpvs-library" / "project-origin.json").write_text("{}", encoding="utf-8")
    else:
        save_library_origin(folder, origin(local_project_id="different"))
    client = Client()
    with pytest.raises(LibraryOriginError):
        download_library_install(client, item("1.1"), tmp_path)
    assert client.calls == 0


def test_cancel_before_scan_never_downloads(tmp_path):
    cancel = Event()
    cancel.set()
    client = Client()
    with pytest.raises(LibraryCancelled):
        download_library_install(client, item("1.1"), tmp_path, cancel_event=cancel)
    assert client.calls == 0
