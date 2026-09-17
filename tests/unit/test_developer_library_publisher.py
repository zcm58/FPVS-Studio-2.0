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
    PublisherConfig,
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
    root = tmp_path / "service"
    (root / "scripts").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "scripts" / "publish-catalog.py").write_text("# Test fixture, never executed\n")
    # Core validates an imported copy inside this workspace; keep that nested path
    # independent of pytest's potentially long repository-local basetemp.
    with tempfile.TemporaryDirectory(prefix="dp-", dir=tempfile.gettempdir()) as name:
        temporary = Path(name)
        monkeypatch.setattr(publisher.tempfile, "gettempdir", lambda: str(temporary))
        monkeypatch.setenv(publisher.PUBLISHER_ENV, str(root))
        yield PublisherService(PublisherConfig(root)), temporary


@pytest.fixture
def prepared(configured, tmp_path, monkeypatch):
    service, temporary = configured

    def fake_prepare(source, destination, **kwargs):
        destination.write_bytes(PAYLOAD)
        return report()

    monkeypatch.setattr(publisher, "prepare_library_bundle", fake_prepare)
    result = service.prepare(tmp_path / "source", request())
    return service, result, temporary


def test_configuration_is_hidden_without_opt_in_or_in_frozen_build(configured, monkeypatch):
    service, _ = configured
    assert publisher.get_publisher_config() == service.config
    monkeypatch.delenv(publisher.PUBLISHER_ENV)
    assert publisher.get_publisher_config() is None
    monkeypatch.setenv(publisher.PUBLISHER_ENV, str(service.config.repository_root))
    monkeypatch.setattr(publisher.sys, "frozen", True, raising=False)
    assert publisher.get_publisher_config() is None
    with pytest.raises(PublisherError, match="source checkout"):
        PublisherService(service.config)


def test_configuration_is_hidden_outside_a_source_checkout(configured, monkeypatch, tmp_path):
    monkeypatch.setattr(
        publisher, "__file__", str(tmp_path / "src/fpvs_studio/developer/module.py")
    )
    assert publisher.get_publisher_config() is None


@pytest.mark.parametrize("configured_value", ["relative/path", "C:/missing/publisher-checkout"])
def test_invalid_explicit_configuration_is_actionable(configured, monkeypatch, configured_value):
    monkeypatch.setenv(publisher.PUBLISHER_ENV, configured_value)
    with pytest.raises(PublisherError, match="FPVS_LIBRARY_PUBLISHER_REPO"):
        publisher.get_publisher_config()


def test_missing_publisher_script_never_falls_back(configured):
    service, _ = configured
    (service.config.repository_root / "scripts/publish-catalog.py").unlink()
    with pytest.raises(PublisherError, match="publish-catalog.py"):
        publisher.get_publisher_config()


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


def test_access_checks_remote_before_running_the_private_script(configured, monkeypatch):
    service, _ = configured
    calls = []

    def run(command, root, **kwargs):
        calls.append(command)
        if command[0] == "git":
            return b"git@github.com:zcm58/FPVS-Studio-Library.git\n"
        return json.dumps(
            dict(login="zcm58", repository=publisher.REPOSITORY, can_publish=True)
        ).encode()

    monkeypatch.setattr(publisher, "_run", run)
    assert service.check_access().repository == publisher.REPOSITORY
    assert calls[0] == [
        "git",
        "-C",
        str(service.config.repository_root),
        "remote",
        "get-url",
        "origin",
    ]
    assert calls[1] == [
        publisher.sys.executable,
        str(service.config.repository_root / "scripts/publish-catalog.py"),
        "--check-access",
    ]


@pytest.mark.parametrize(
    "remote",
    [
        b"https://github.com/other/library.git",
        b"https://user:PRIVATE@github.com/zcm58/FPVS-Studio-Library.git",
    ],
)
def test_wrong_or_credential_bearing_remote_prevents_helper_execution(
    configured, monkeypatch, remote
):
    service, _ = configured
    calls = []
    monkeypatch.setattr(publisher, "_run", lambda *args, **kwargs: calls.append(args[0]) or remote)
    with pytest.raises(PublisherError, match="origin") as error:
        service.check_access()
    assert len(calls) == 1
    assert "PRIVATE" not in str(error.value)


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
    monkeypatch.setattr(service, "_validated_root", lambda cancel: service.config.repository_root)
    calls = []

    def run(command, *args, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise PublisherError("Publishing was not confirmed.")
        return json.dumps(
            dict(
                login="zcm58",
                repository=publisher.REPOSITORY,
                can_publish=True,
                tag=publication.request.release_tag,
                catalog_commit="a" * 40,
            )
        ).encode()

    monkeypatch.setattr(publisher, "_run", run)
    before = publication.bundle_path.read_bytes(), publication.metadata_path.read_bytes()
    with pytest.raises(PublisherError, match="Remote state may have changed"):
        service.publish(publication)
    assert (publication.bundle_path.read_bytes(), publication.metadata_path.read_bytes()) == before
    result = service.publish(publication)
    assert result.catalog_commit == "a" * 40
    assert calls[0] == calls[1]
    assert "--publish-online" in calls[1]
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
    monkeypatch.setattr(service, "_validated_root", lambda cancel: service.config.repository_root)
    result = dict(
        login="zcm58",
        repository=publisher.REPOSITORY,
        can_publish=True,
        tag=publication.request.release_tag,
        catalog_commit="a" * 40,
    )
    monkeypatch.setattr(
        publisher, "_run", lambda *args, **kwargs: json.dumps({**result, **changes}).encode()
    )
    with pytest.raises(PublisherError, match="Remote state may have changed"):
        service.publish(publication)
    assert publication.bundle_path.exists()


@pytest.mark.parametrize("target", ["bundle_path", "metadata_path"])
def test_changed_prepared_bytes_cannot_be_published(prepared, monkeypatch, target):
    service, publication, _ = prepared
    getattr(publication, target).write_bytes(b"changed")
    monkeypatch.setattr(publisher, "_run", lambda *args, **kwargs: pytest.fail("must not execute"))
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
    monkeypatch.setattr(publisher, "_run", lambda *args, **kwargs: pytest.fail("must not execute"))
    with pytest.raises(PublisherError, match="unrecognized"):
        service.publish(publication)


def test_precancel_publish_retains_payload_without_execution(prepared, monkeypatch):
    service, publication, _ = prepared
    cancel = Event()
    cancel.set()
    monkeypatch.setattr(publisher, "_run", lambda *args, **kwargs: pytest.fail("must not execute"))
    with pytest.raises(PublisherCancelled, match="Remote state may have changed"):
        service.publish(publication, cancel_event=cancel)
    assert publication.bundle_path.exists()


class FakeProcess:
    def __init__(self, *, returncode=0):
        self.returncode = returncode
        self.terminated = False
        self.waited = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout):
        self.waited = True
        return self.returncode


def test_subprocess_uses_hidden_shell_free_launch_without_tokens(configured, monkeypatch):
    service, _ = configured
    handles = []
    monkeypatch.setenv("GH_TOKEN", "PRIVATE-TOKEN")

    def popen(command, **kwargs):
        assert "PRIVATE-TOKEN" not in repr(command)
        assert kwargs["shell"] is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
        assert kwargs["cwd"] == service.config.repository_root
        assert "env" not in kwargs  # Credentials stay inherited; adapter never reads them.
        handles.extend([kwargs["stdout"], kwargs["stderr"]])
        kwargs["stdout"].write(b'{"ok":true}')
        kwargs["stdout"].flush()
        return FakeProcess()

    monkeypatch.setattr(publisher.subprocess, "Popen", popen)
    assert (
        publisher._run(
            ["python", "script.py"], service.config.repository_root, cancel_event=None, timeout=30
        )
        == b'{"ok":true}'
    )
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize("mode", ["stdout", "stderr", "cancel", "timeout", "nonzero"])
def test_subprocess_failures_are_bounded_sanitized_and_cleanup(configured, monkeypatch, mode):
    service, _ = configured
    cancel = Event()
    process = FakeProcess(returncode=1 if mode == "nonzero" else None)
    handles = []

    def popen(command, **kwargs):
        handles.extend([kwargs["stdout"], kwargs["stderr"]])
        if mode in ("stdout", "stderr"):
            kwargs[mode].write(b"x" * (publisher._OUTPUT_LIMIT + 1))
            kwargs[mode].flush()
        if mode == "cancel":
            cancel.set()
        if mode == "nonzero":
            kwargs["stderr"].write(b"PRIVATE-TOKEN")
            kwargs["stderr"].flush()
        return process

    monkeypatch.setattr(publisher.subprocess, "Popen", popen)
    with pytest.raises(PublisherError, match="Remote state may have changed") as error:
        publisher._run(
            ["python", "script.py"],
            service.config.repository_root,
            cancel_event=cancel,
            timeout=0 if mode == "timeout" else 30,
            publishing=True,
        )
    assert "PRIVATE-TOKEN" not in str(error.value)
    assert mode == "nonzero" or (process.terminated and process.waited)
    assert all(handle.closed for handle in handles)


@pytest.mark.parametrize(
    "output, expected",
    [
        (
            b'{"error":"This version already has different bytes. Choose a new version."}',
            "Choose a new version",
        ),
        (b"PRIVATE-TOKEN", "Publisher access check failed"),
        (b'{"error":42}', "Publisher access check failed"),
        (b'["PRIVATE-TOKEN"]', "Publisher access check failed"),
        (json.dumps({"error": "x" * 1025}).encode(), "Publisher access check failed"),
        (b'{"error":"PRIVATE-TOKEN\\n"}', "Publisher access check failed"),
    ],
)
def test_only_bounded_structured_helper_errors_reach_the_gui(
    configured, monkeypatch, output, expected
):
    service, _ = configured

    def popen(command, **kwargs):
        kwargs["stdout"].write(output)
        kwargs["stdout"].flush()
        kwargs["stderr"].write(b"PRIVATE-TOKEN")
        kwargs["stderr"].flush()
        return FakeProcess(returncode=1)

    monkeypatch.setattr(publisher.subprocess, "Popen", popen)
    with pytest.raises(PublisherError, match=expected) as error:
        publisher._run(
            ["python", "script.py"],
            service.config.repository_root,
            cancel_event=None,
            timeout=30,
        )
    assert "PRIVATE-TOKEN" not in str(error.value)


def test_invalid_json_after_publish_preserves_uncertain_result(prepared, monkeypatch):
    service, publication, _ = prepared
    monkeypatch.setattr(service, "_validated_root", lambda cancel: service.config.repository_root)
    monkeypatch.setattr(publisher, "_run", lambda *args, **kwargs: b"not JSON")
    with pytest.raises(PublisherError, match="Remote state may have changed"):
        service.publish(publication)
    assert publication.directory.exists()


def test_stubborn_process_is_killed_and_reaped():
    class StubbornProcess(FakeProcess):
        def __init__(self):
            super().__init__(returncode=None)
            self.killed = False
            self.wait_calls = 0

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.wait_calls += 1
            if not self.killed:
                raise subprocess.TimeoutExpired("safe-helper", timeout)
            self.returncode = -9
            return self.returncode

        def kill(self):
            self.killed = True

    process = StubbornProcess()
    publisher._stop(process)
    assert process.terminated and process.killed and process.wait_calls == 2
