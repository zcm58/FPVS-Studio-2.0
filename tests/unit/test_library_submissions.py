"""Exact-condition packaging and submission retry boundaries with synthetic bytes."""

from __future__ import annotations

import hashlib
import zipfile
from contextlib import contextmanager
from dataclasses import replace
from threading import Event
from uuid import uuid4

import pytest
from tests.unit.test_library_client import MemoryStore, Response
from tests.unit.test_library_publish import _ready_project, _snapshot

from fpvs_studio.core.condition_modifiers import create_backward_counting_modifier
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.library_publish import LibraryBundlePreparation, prepare_library_bundle
from fpvs_studio.core.project_bundle import ProjectBundleError, import_project_bundle
from fpvs_studio.core.project_service import create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import TaskBinding
from fpvs_studio.developer.library_publisher import PreparedPublication, PublicationRequest
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.submissions import list_submissions, submit_condition
from fpvs_studio.preprocessing.manifest import create_empty_manifest, write_stimulus_manifest


def test_one_condition_keeps_modifier_baseline_and_source_unchanged(
    tmp_path,
    multi_condition_project,
    multi_condition_project_root,
):
    project = multi_condition_project
    root = multi_condition_project_root
    group = create_backward_counting_modifier()
    project.schema_version = ProjectSchemaVersion.V1_6
    project.task_modules = group.task_modules
    project.condition_modifiers = [group.modifier]
    condition = project.conditions[0]
    condition.pre_task_bindings = [
        TaskBinding(task_id=value) for value in group.modifier.pre_task_ids
    ]
    condition.post_task_bindings = [
        TaskBinding(task_id=value) for value in group.modifier.post_task_ids
    ]
    _ready_project(root, project)
    before = _snapshot(root)
    bundle = tmp_path / "selected.fpvsbundle"
    report = prepare_library_bundle(root, bundle, condition_id=condition.condition_id)
    imported = import_project_bundle(bundle, tmp_path / "imports")
    selected = load_project_file(imported.project_root / "project.json")
    assert [item.condition_id for item in selected.conditions] == [condition.condition_id]
    assert group.modifier.baseline_task_id in {item.task_id for item in selected.task_modules}
    assert len(selected.condition_modifiers) == 1
    assert report.condition_count == 1
    assert _snapshot(root) == before
    referenced = {condition.base_stimulus_set_id, condition.oddball_stimulus_set_id}
    assert {item.set_id for item in selected.stimulus_sets} == referenced


def test_selection_drops_unrelated_tasks(
    tmp_path, multi_condition_project, multi_condition_project_root
):
    project = multi_condition_project
    root = multi_condition_project_root
    _ready_project(root, project)
    chosen = next(
        item
        for item in project.conditions
        if not item.pre_task_bindings and not item.post_task_bindings
    )
    report = prepare_library_bundle(
        root, tmp_path / "selected.fpvsbundle", condition_id=chosen.condition_id
    )
    assert report.task_count == 0


def test_unknown_condition_fails_without_output(
    tmp_path, multi_condition_project, multi_condition_project_root
):
    _ready_project(multi_condition_project_root, multi_condition_project)
    target = tmp_path / "selected.fpvsbundle"
    with pytest.raises(ProjectBundleError, match="no longer exists"):
        prepare_library_bundle(multi_condition_project_root, target, condition_id="missing")
    assert not target.exists()


def test_word_condition_remains_runnable_without_unrelated_assets(
    tmp_path,
    multi_condition_project,
    multi_condition_project_root,
):
    project = multi_condition_project
    chosen = project.conditions[0]
    for pool in project.stimulus_sets:
        pool.modality = StimulusModality.WORD
        pool.source_dir = None
        pool.resolution = None
        pool.image_count = 0
        pool.words = ["alpha", "beta"]
    source = multi_condition_project_root
    save_project_file(project, source / "project.json")
    write_stimulus_manifest(source, create_empty_manifest(project.meta.project_id))
    bundle = tmp_path / "word.fpvsbundle"
    report = prepare_library_bundle(source, bundle, condition_id=chosen.condition_id)
    imported = import_project_bundle(bundle, tmp_path / "imports")
    selected = load_project_file(imported.project_root / "project.json")
    assert report.condition_count == 1
    assert all(pool.words == ["alpha", "beta"] for pool in selected.stimulus_sets)


def test_native_ab_selected_condition_keeps_its_recall_tasks(tmp_path):
    scaffold = create_project(
        tmp_path,
        "AB",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    source = scaffold.project_root
    project = load_project_file(source / "project.json")
    bundle = tmp_path / "ab-selected.fpvsbundle"
    report = prepare_library_bundle(source, bundle, condition_id=project.conditions[0].condition_id)
    with zipfile.ZipFile(bundle) as archive:
        selected = type(project).model_validate_json(archive.read("project.json"))
    assert report.condition_count == 1
    assert selected.conditions[0].post_task_bindings
    assert {task.task_id for task in selected.task_modules} == {
        binding.task_id for binding in selected.conditions[0].post_task_bindings
    }


@pytest.fixture
def submission(tmp_path, monkeypatch):
    identifier = str(uuid4())
    path = tmp_path / f"reviewed-{identifier}-1.0.0.fpvsbundle"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("project.json", "synthetic")
    data = path.read_bytes()
    report = LibraryBundlePreparation(
        project_id="source",
        title="Condition",
        category="fpvs_oddball",
        minimum_studio_version="2.2.7",
        bundle_schema_version="1.0",
        project_schema_version="1.4.0",
        condition_count=1,
        stimulus_set_count=0,
        task_count=0,
        file_count=1,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        included_paths=("project.json",),
        excluded_paths=(),
        sanitized_fields=(),
        dry_run=False,
    )
    prepared = PreparedPublication(
        PublicationRequest(f"reviewed-{identifier}", "Condition", "1.0.0", "Purpose", "2.2.7"),
        tmp_path,
        path,
        path.with_suffix(".json"),
        report,
    )
    client = LibraryClient("https://library.example.test", MemoryStore(), tmp_path / "cache")

    @contextmanager
    def operation(_cancel):
        yield

    monkeypatch.setattr(client, "_operation", operation)
    status = dict(
        submission_id=identifier,
        project_id="source",
        condition_id="chosen",
        condition_name="Chosen",
        title="Condition",
        sha256=report.sha256,
        status="uploading",
        review_notes="",
        tested_studio_version=None,
        item_id=prepared.request.item_id,
        version="1.0.0",
        created_at=1,
    )
    calls = []

    def create(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return {"schema_version": "1.0", "submission": status.copy()}

    @contextmanager
    def upload(method, url, **kwargs):
        raw = b"".join(iter(lambda: kwargs["data"].read(4096), b""))
        calls.append((method, url, kwargs))
        assert raw == data
        assert kwargs["content_length"] == len(data)
        yield Response(
            {"schema_version": "1.0", "submission": {**status, "status": "pending"}},
            client.service_url + url,
        )

    monkeypatch.setattr(client, "_json_request", create)
    monkeypatch.setattr(client, "_response", upload)
    return client, prepared, status, calls


def send(client, prepared, **changes):
    return submit_condition(
        client,
        prepared,
        condition_id="chosen",
        condition_name="Chosen",
        author_name="Researcher",
        author_email="researcher@example.test",
        **changes,
    )


def test_submission_uploads_exact_bytes_with_enrolled_token_and_retries_same_id(submission):
    client, prepared, status, calls = submission
    result = send(client, prepared)
    assert result.status == "pending"
    payload = calls[0][2]["payload"]
    assert payload["rights_confirmed"] is True
    assert payload["condition_id"] == "chosen"
    assert calls[1][2]["token"] == "t" * 43
    status["status"] = "pending"
    result = send(client, prepared)
    assert result.status == "pending"
    assert len(calls) == 3  # Receipt retry does not upload again.
    assert calls[2][2]["payload"] == payload


def test_mutated_bundle_fails_before_network(submission):
    client, prepared, _, calls = submission
    prepared.bundle_path.write_bytes(b"changed")
    with pytest.raises(LibraryError, match="changed"):
        send(client, prepared)
    assert not calls


@pytest.mark.parametrize("changes", [{"condition_count": 2}, {"size_bytes": 65 * 1024 * 1024}])
def test_bundle_limits_fail_before_network(submission, changes):
    client, prepared, _, calls = submission
    prepared = replace(prepared, report=replace(prepared.report, **changes))
    with pytest.raises(LibraryError, match="one condition"):
        send(client, prepared)
    assert not calls


def test_cancellation_before_upload_leaves_prepared_bytes(submission):
    client, prepared, _, calls = submission
    event = Event()
    event.set()
    with pytest.raises(LibraryCancelled):
        send(client, prepared, cancel_event=event)
    assert prepared.bundle_path.exists()
    assert not calls


def test_receipt_cannot_identify_another_digest(submission):
    client, prepared, status, _ = submission
    status["sha256"] = "a" * 64
    with pytest.raises(LibraryError, match="different submission"):
        send(client, prepared)


def test_status_list_validates_server_metadata(submission, monkeypatch):
    client, _, _, _ = submission
    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *_args, **_kwargs: {"schema_version": "1.0", "submissions": []},
    )
    assert list_submissions(client).submissions == []
    monkeypatch.setattr(
        client,
        "_json_request",
        lambda *_args, **_kwargs: {
            "schema_version": "1.0",
            "submissions": [{"status": "accepted"}],
        },
    )
    with pytest.raises(LibraryError, match="statuses"):
        list_submissions(client)
