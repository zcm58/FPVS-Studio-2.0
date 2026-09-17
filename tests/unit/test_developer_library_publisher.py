"""Source-only publishing adapter: no real credentials, subprocesses or remote writes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import zipfile
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event

import pytest

from fpvs_studio.core.library_publish import LibraryBundlePreparation
from fpvs_studio.core.project_bundle import ProjectBundleCancelled
from fpvs_studio.core.serialization import save_project_file
from fpvs_studio.developer import library_publisher as publisher
from fpvs_studio.developer.library_publisher import (
    PublicationRequest,
    PublisherCancelled,
    PublisherError,
    PublisherService,
)
from fpvs_studio.preprocessing.inspection import inspect_source_directory
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    write_stimulus_manifest,
)

PAYLOAD = b"synthetic prepared bundle"


def request(**changes):
    values = dict(
        item_id="synthetic",
        title="Public example",
        version="1.0.0",
        summary="A synthetic test experiment.",
        minimum_studio_version="1.8.0",
    )
    return PublicationRequest(**{**values, **changes})


def report():
    return LibraryBundlePreparation(
        project_id="source-project",
        title="Original project",
        category="fpvs_oddball",
        minimum_studio_version="1.8.0",
        bundle_schema_version="1.0.0",
        project_schema_version="1.4",
        condition_count=1,
        stimulus_set_count=2,
        task_count=0,
        file_count=2,
        size_bytes=len(PAYLOAD),
        sha256=hashlib.sha256(PAYLOAD).hexdigest(),
        included_paths=("project.json", "stimuli/manifest.json"),
        excluded_paths=("runs/private.csv",),
        sanitized_fields=("manual_removed_electrodes",),
        dry_run=False,
    )


@pytest.fixture
def configured(tmp_path, monkeypatch):
    # Core validates an imported copy inside this workspace; keep that nested path
    # independent of pytest's potentially long repository-local basetemp.
    with tempfile.TemporaryDirectory(prefix="dp-", dir=tempfile.gettempdir()) as name:
        temporary = Path(name)
        monkeypatch.setattr(publisher.tempfile, "gettempdir", lambda: str(temporary))
        yield PublisherService(), temporary


@pytest.fixture
def prepared(configured, tmp_path, monkeypatch):
    service, temporary = configured

    def fake_prepare(source, destination, **kwargs):
        destination.write_bytes(PAYLOAD)
        return report()

    monkeypatch.setattr(publisher, "prepare_library_bundle", fake_prepare)
    result = service.prepare(tmp_path / "source", request())
    monkeypatch.setattr(publisher, "_api", lambda cancel: None)
    monkeypatch.setattr(
        publisher.catalog_publisher, "load_prepared", lambda directory, **kwargs: [result]
    )
    return service, result, temporary


@pytest.mark.parametrize(
    "changes",
    [
        dict(item_id="../escape"),
        dict(title=" "),
        dict(title="x" * 161),
        dict(summary="x" * 4001),
        dict(version="not a version"),
        dict(version="1.0.0-alpha"),
        dict(minimum_studio_version="1.8"),
        dict(item_id="x" * 80, version="1." + "1" * 50),
    ],
)
def test_publication_request_validates_before_preparation(changes):
    with pytest.raises(PublisherError):
        request(**changes)
    valid = request()
    with pytest.raises(FrozenInstanceError):
        valid.title = "changed"


def test_access_uses_bundled_owner_check_without_a_checkout(configured, monkeypatch):
    service, _ = configured
    sentinel = object()
    monkeypatch.setattr(publisher, "_api", lambda cancel: sentinel)

    def access(api):
        assert api is sentinel
        return dict(login="zcm58", repository=publisher.REPOSITORY, can_publish=True)

    monkeypatch.setattr(publisher.catalog_publisher, "check_access", access)
    assert service.check_access().login == "zcm58"


def test_preparation_preserves_source_and_writes_reviewed_metadata(
    configured,
    sample_project,
    sample_project_root,
):
    service, temporary = configured
    sample_project.manual_removed_electrodes = {"001": ["A1"]}
    manifest = create_empty_manifest(sample_project.meta.project_id)
    for stimulus_set in sample_project.stimulus_sets:
        summary = inspect_source_directory(
            sample_project_root / stimulus_set.source_dir, relative_prefix=stimulus_set.source_dir
        )
        manifest.sets.append(
            inspection_summary_to_manifest_set(set_id=stimulus_set.set_id, summary=summary)
        )
    save_project_file(sample_project, sample_project_root / "project.json")
    write_stimulus_manifest(sample_project_root, manifest)
    before = {path: path.read_bytes() for path in sample_project_root.rglob("*") if path.is_file()}
    result = service.prepare(sample_project_root, request())
    assert result.directory.parent == temporary
    assert not result.directory.is_relative_to(sample_project_root)
    assert all(path.read_bytes() == contents for path, contents in before.items())
    metadata = json.loads(result.metadata_path.read_bytes())
    assert metadata["title"] == "Public example"
    assert metadata["asset_name"] == "synthetic-1.0.0.fpvsbundle"
    assert metadata["summary"] == request().summary
    assert metadata["sha256"] == result.report.sha256
    with zipfile.ZipFile(result.bundle_path) as archive:
        assert json.loads(archive.read("project.json"))["manual_removed_electrodes"] == {}
    service.discard(result)
    assert not result.directory.exists()
    assert sample_project_root.exists()


def test_failed_or_canceled_preparation_removes_only_generated_workspace(
    configured, tmp_path, monkeypatch
):
    service, temporary = configured
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "keep.txt"
    sentinel.write_text("keep")

    def cancel(source, destination, **kwargs):
        destination.write_bytes(PAYLOAD)
        raise ProjectBundleCancelled("Canceled")

    monkeypatch.setattr(publisher, "prepare_library_bundle", cancel)
    with pytest.raises(PublisherCancelled):
        service.prepare(source, request())
    assert list(temporary.iterdir()) == []
    assert sentinel.read_text() == "keep"


def test_publish_failure_retains_exact_preparation_for_retry(prepared, monkeypatch):
    service, publication, _ = prepared
    calls = []

    def run(api, tag, bundles, **kwargs):
        calls.append((tag, bundles))
        if len(calls) == 1:
            raise PublisherError("Publishing was not confirmed.")
        return dict(
            login="zcm58",
            repository=publisher.REPOSITORY,
            can_publish=True,
            tag=publication.request.release_tag,
            catalog_commit="a" * 40,
        )

    monkeypatch.setattr(publisher.catalog_publisher, "publish_online", run)
    before = publication.bundle_path.read_bytes(), publication.metadata_path.read_bytes()
    with pytest.raises(PublisherError, match="Remote state may have changed"):
        service.publish(publication)
    assert (publication.bundle_path.read_bytes(), publication.metadata_path.read_bytes()) == before
    result = service.publish(publication)
    assert result.catalog_commit == "a" * 40
    assert calls[0] == calls[1]
    assert calls[1][0] == publication.request.release_tag
    assert publication.directory.exists()


@pytest.mark.parametrize(
    "changes",
    [
        dict(catalog_commit="not-a-commit"),
        dict(tag="other"),
        dict(repository="other/repo"),
        dict(login="someone-else"),
        dict(can_publish=False),
    ],
)
def test_invalid_publish_confirmation_cannot_claim_success(prepared, monkeypatch, changes):
    service, publication, _ = prepared
    result = dict(
        login="zcm58",
        repository=publisher.REPOSITORY,
        can_publish=True,
        tag=publication.request.release_tag,
        catalog_commit="a" * 40,
    )
    monkeypatch.setattr(
        publisher.catalog_publisher, "publish_online", lambda *args, **kwargs: {**result, **changes}
    )
    with pytest.raises(PublisherError, match="Remote state may have changed"):
        service.publish(publication)
    assert publication.bundle_path.exists()


@pytest.mark.parametrize("target", ["bundle_path", "metadata_path"])
def test_changed_prepared_bytes_cannot_be_published(prepared, monkeypatch, target):
    service, publication, _ = prepared
    getattr(publication, target).write_bytes(b"changed")
    monkeypatch.setattr(
        publisher.catalog_publisher,
        "publish_online",
        lambda *args, **kwargs: pytest.fail("must not execute"),
    )
    with pytest.raises(PublisherError, match="changed"):
        service.publish(publication)


def test_discard_refuses_foreign_directory_or_added_user_file(prepared, tmp_path):
    service, publication, _ = prepared
    with pytest.raises(PublisherError, match="does not belong"):
        service.discard(replace(publication, directory=tmp_path))
    note = publication.directory / "user-notes.txt"
    note.write_text("preserve")
    with pytest.raises(PublisherError, match="unrecognized"):
        service.discard(publication)
    assert note.read_text() == "preserve"


def test_unreviewed_extra_metadata_prevents_publishing(prepared, monkeypatch):
    service, publication, _ = prepared
    (publication.directory / "another-item.json").write_text("{}")
    monkeypatch.setattr(
        publisher.catalog_publisher,
        "publish_online",
        lambda *args, **kwargs: pytest.fail("must not execute"),
    )
    with pytest.raises(PublisherError, match="unrecognized"):
        service.publish(publication)


def test_precancel_publish_retains_payload_without_execution(prepared, monkeypatch):
    service, publication, _ = prepared
    cancel = Event()
    cancel.set()
    monkeypatch.setattr(
        publisher.catalog_publisher,
        "publish_online",
        lambda *args, **kwargs: pytest.fail("must not execute"),
    )
    with pytest.raises(PublisherCancelled, match="Remote state may have changed"):
        service.publish(publication, cancel_event=cancel)
    assert publication.bundle_path.exists()


@pytest.mark.parametrize(
    "exception",
    [
        OSError("PRIVATE-TOKEN"),
        ValueError("PRIVATE-TOKEN"),
        subprocess.TimeoutExpired("PRIVATE-TOKEN", 30),
    ],
)
def test_external_errors_never_expose_credentials(prepared, monkeypatch, exception):
    service, publication, _ = prepared

    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(publisher.catalog_publisher, "publish_online", fail)
    with pytest.raises(PublisherError, match="Remote state may have changed") as error:
        service.publish(publication)
    assert "PRIVATE-TOKEN" not in str(error.value)
    assert publication.bundle_path.exists()


def test_api_cancellation_retains_exact_preparation(prepared, monkeypatch):
    service, publication, _ = prepared

    def fail(*args, **kwargs):
        raise publisher.catalog_publisher.CatalogCancelled("canceled")

    monkeypatch.setattr(publisher.catalog_publisher, "publish_online", fail)
    with pytest.raises(PublisherCancelled, match="Remote state may have changed"):
        service.publish(publication)
    assert publication.bundle_path.exists()
