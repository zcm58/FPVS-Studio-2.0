"""Maintainer publishing tests use local fixtures and a fake GitHub API only."""

import base64
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fpvs_studio.developer import catalog_publisher as publisher

SCRIPT = Path(publisher.__file__)


class FakeGitHub:
    def __init__(self, bundle, *, existing=False, draft=False, private=True):
        self.bundle = bundle
        self.calls = []
        self.private = private
        self.release = {"id": 45, "tag_name": "test-v1", "draft": draft} if existing else None
        self.assets = [self.asset()] if existing else []
        self.bad_upload = False

    def asset(self):
        return {
            "name": self.bundle.path.name,
            "id": 123,
            "state": "uploaded",
            "size": self.bundle.entry["size_bytes"],
            "digest": "sha256:" + self.bundle.entry["sha256"],
        }

    def list_all(self, path):
        if path.endswith("/assets"):
            return list(self.assets)
        return [self.release] if self.release else []

    def request(self, method, path, *, payload=None, upload=None):
        self.calls.append((method, path))
        if method == "DELETE":
            self.assets = []
            return None
        if method == "GET":
            if path == publisher.REPO_PATH + "/releases/45":
                return dict(self.release)
            if path == publisher.REPO_PATH + "/releases/assets/123":
                return dict(self.assets[0])
            return {
                "full_name": publisher.REPOSITORY,
                "private": self.private,
                "default_branch": "main",
            }
        if method == "PATCH":
            self.release = {**self.release, "draft": False}
            return self.release
        if upload:
            asset = self.asset()
            if self.bad_upload:
                asset["digest"] = "sha256:" + "0" * 64
            self.assets.append(asset)
            return asset
        if payload["draft"] is not True:
            raise AssertionError("A new release must begin as a draft.")
        self.release = {"id": 45, "tag_name": payload["tag_name"], "draft": True}
        return self.release


class OnlineGitHub(FakeGitHub):
    def __init__(self, bundle, catalog, **kwargs):
        super().__init__(bundle, **kwargs)
        self.login = "zcm58"
        self.permissions = {"push": True}
        self.repository = publisher.REPOSITORY
        self.history = {}
        self.head = None
        self.save_catalog(catalog)
        self.catalog_writes = []
        self.conflicts = []
        self.put_error = None
        self.confirm_wrong_catalog = False
        self.lose_put_response = False

    def save_catalog(self, catalog):
        self.head = f"{len(self.history) + 1:040x}"
        raw = None if catalog is None else (json.dumps(catalog) + "\n").encode("utf-8")
        self.history[self.head] = raw

    def blob_sha(self):
        raw = self.history[self.head]
        return hashlib.sha1(raw).hexdigest() if raw is not None else None

    def current_catalog(self):
        return json.loads(self.history[self.head])

    def request(self, method, path, *, payload=None, upload=None):
        if path == "/user":
            self.calls.append((method, path))
            return {"login": self.login}
        if path == publisher.REPO_PATH:
            result = super().request(method, path, payload=payload, upload=upload)
            return {**result, "full_name": self.repository, "permissions": self.permissions}
        if path.endswith("/branches/main"):
            self.calls.append((method, path))
            return {"commit": {"sha": self.head}}
        if "/contents/catalog.json" not in path:
            return super().request(method, path, payload=payload, upload=upload)
        self.calls.append((method, path))
        if method == "GET":
            commit = path.rsplit("?ref=", 1)[1]
            raw = self.history[commit]
            if raw is None:
                raise publisher.GitHubApiError(method, 404)
            if self.confirm_wrong_catalog and self.catalog_writes:
                raw = json.dumps(
                    {"schema_version": "1.0", "library_name": "Other", "items": []}
                ).encode()
            return {
                "type": "file",
                "path": "catalog.json",
                "encoding": "base64",
                "size": len(raw),
                "sha": hashlib.sha1(raw).hexdigest(),
                "content": base64.b64encode(raw).decode("ascii"),
            }
        self.catalog_writes.append(payload)
        if self.conflicts:
            self.save_catalog(self.conflicts.pop(0))
            raise publisher.GitHubApiError(method, 409)
        if self.put_error:
            raise publisher.GitHubApiError(method, self.put_error)
        if payload.get("sha") != self.blob_sha():
            raise publisher.GitHubApiError(method, 409)
        if payload["branch"] != "main":
            raise AssertionError("Only main can receive the published catalog.")
        self.save_catalog(json.loads(base64.b64decode(payload["content"])))
        if self.lose_put_response:
            self.lose_put_response = False
            raise publisher.PublishError("GitHub request failed; no completion is assumed.")
        return {"commit": {"sha": self.head}}


class PublishCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "demo-1.0.0.fpvsbundle"
        records = [
            {"path": path, "size_bytes": 2, "sha256": "a" * 64}
            for path in ("project.json", "stimuli/manifest.json")
        ]
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr(
                "fpvs_bundle.json",
                json.dumps(
                    {
                        "schema_version": "1.0.0",
                        "project": {"project_id": "demo"},
                        "files": records,
                    }
                ),
            )
            for record in records:
                archive.writestr(record["path"], "{}")
        self.metadata = {
            "dry_run": False,
            "asset_name": self.path.name,
            "project_id": "demo",
            "item_id": "demo",
            "version": "1.0.0",
            "title": "Test demo",
            "summary": "Synthetic test",
            "category": "fpvs_oddball",
            "minimum_studio_version": "1.8.0",
            "size_bytes": self.path.stat().st_size,
            "sha256": publisher.file_sha256(self.path),
            "file_count": 2,
            "included_paths": [record["path"] for record in records],
        }
        self.metadata_path = self.root / "demo-1.0.0.json"
        self.write_metadata()
        self.bundle = publisher.verify_bundle(self.metadata_path)
        self.catalog = {"schema_version": "1.0", "library_name": "Test library", "items": []}

    def write_metadata(self):
        self.metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_local_inventory_derives_catalog_limits(self):
        loaded = publisher.load_prepared(self.root)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].entry["uncompressed_size_bytes"], 4)
        self.assertEqual(loaded[0].entry["file_count"], 2)
        self.assertNotIn("asset_id", loaded[0].entry)

    def test_modified_bundle_fails_digest(self):
        self.path.write_bytes(self.path.read_bytes() + b"changed")
        self.metadata["size_bytes"] = self.path.stat().st_size
        self.write_metadata()
        with self.assertRaisesRegex(publisher.PublishError, "checksum differs"):
            publisher.verify_bundle(self.metadata_path)

    def test_wrong_manifest_counts_and_unsafe_filename_fail(self):
        self.metadata["file_count"] = 3
        self.write_metadata()
        with self.assertRaisesRegex(publisher.PublishError, "file count differs"):
            publisher.verify_bundle(self.metadata_path)
        self.metadata["asset_name"] = "../demo.fpvsbundle"
        self.write_metadata()
        with self.assertRaisesRegex(publisher.PublishError, "plain asset_name"):
            publisher.verify_bundle(self.metadata_path)

    def test_creates_draft_uploads_verifies_then_publishes(self):
        api = FakeGitHub(self.bundle)
        result = publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual([call[0] for call in api.calls], ["GET", "POST", "POST", "PATCH"])
        self.assertEqual(result["items"][0]["asset_id"], 123)
        self.assertFalse(api.release["draft"])

    def test_existing_published_release_is_verified_without_mutation(self):
        api = FakeGitHub(self.bundle, existing=True)
        result = publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual([call[0] for call in api.calls], ["GET"])
        self.assertEqual(result["items"][0]["asset_id"], 123)

    def test_missing_asset_on_published_release_requires_new_tag(self):
        api = FakeGitHub(self.bundle, existing=True)
        api.assets = []
        with self.assertRaisesRegex(publisher.PublishError, "immutable"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual([call[0] for call in api.calls], ["GET"])

    def test_failed_uploaded_digest_leaves_draft_unpublished(self):
        api = FakeGitHub(self.bundle)
        api.bad_upload = True
        with self.assertRaisesRegex(publisher.PublishError, "exact expected SHA-256"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertTrue(api.release["draft"])
        self.assertNotIn("PATCH", [call[0] for call in api.calls])

    def test_existing_asset_without_digest_is_never_replaced(self):
        api = FakeGitHub(self.bundle, existing=True, draft=True)
        api.assets[0]["digest"] = None
        with self.assertRaisesRegex(publisher.PublishError, "exact expected SHA-256"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual([call[0] for call in api.calls], ["GET"])

    def starter_api(self, *, draft=True):
        api = FakeGitHub(self.bundle, existing=True, draft=draft)
        api.assets[0].update(
            state="starter", digest=None, updated_at="2000-01-01T00:00:00Z",
        )
        return api

    def test_retry_reuploads_abandoned_draft_starter_and_verifies(self):
        api = self.starter_api()
        result = publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual(result["items"][0]["sha256"], self.bundle.entry["sha256"])
        self.assertEqual([call[0] for call in api.calls],
                         ["GET", "GET", "GET", "DELETE", "POST", "PATCH"])
        self.assertEqual(api.assets[0]["state"], "uploaded")

    def test_recent_or_unidentified_starter_is_not_deleted(self):
        for timestamp in (datetime.now(timezone.utc).isoformat(), None, "bad-date"):
            with self.subTest(timestamp=timestamp):
                api = self.starter_api()
                api.assets[0]["updated_at"] = timestamp
                with self.assertRaisesRegex(publisher.PublishError, "incomplete"):
                    publisher.publish(api, "test-v1", [self.bundle], self.catalog)
                self.assertNotIn("DELETE", [call[0] for call in api.calls])

    def test_published_or_catalogued_starter_is_never_deleted(self):
        for draft, catalogued in ((False, False), (True, True)):
            with self.subTest(draft=draft, catalogued=catalogued):
                api = self.starter_api(draft=draft)
                catalog = self.catalog
                if catalogued:
                    catalog = {**catalog, "items": [{**self.bundle.entry, "asset_id": 123}]}
                with self.assertRaises(publisher.PublishError):
                    publisher.publish(api, "test-v1", [self.bundle], catalog)
                self.assertNotIn("DELETE", [call[0] for call in api.calls])

    def test_changed_local_bundle_never_deletes_starter(self):
        api = self.starter_api()
        self.path.write_bytes(b"changed")
        with self.assertRaisesRegex(publisher.PublishError, "local bundle changed"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertNotIn("DELETE", [call[0] for call in api.calls])

    def test_starter_completed_before_recovery_is_used_without_deleting(self):
        api = self.starter_api()
        request = api.request

        def completed(method, path, **kwargs):
            if method == "GET" and path.endswith("/releases/assets/123"):
                api.assets = [api.asset()]
            return request(method, path, **kwargs)

        api.request = completed
        publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertNotIn("DELETE", [call[0] for call in api.calls])
        self.assertNotIn("POST", [call[0] for call in api.calls])

    def test_release_published_before_recovery_is_not_modified(self):
        api = self.starter_api()
        request = api.request

        def published(method, path, **kwargs):
            if method == "GET" and path.endswith("/releases/45"):
                api.release["draft"] = False
            return request(method, path, **kwargs)

        api.request = published
        with self.assertRaises(publisher.PublishError):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertNotIn("DELETE", [call[0] for call in api.calls])

    def test_recovery_rechecks_asset_identity_and_cancellation(self):
        from threading import Event

        for cancel_before_delete in (False, True):
            with self.subTest(cancel=cancel_before_delete):
                api = self.starter_api()
                request = api.request
                cancel = Event()

                def changed(
                    method, path, *, request=request, cancel=cancel,
                    cancel_before_delete=cancel_before_delete, **kwargs,
                ):
                    result = request(method, path, **kwargs)
                    if method == "GET" and path.endswith("/releases/assets/123"):
                        if cancel_before_delete:
                            cancel.set()
                        else:
                            result["id"] = 999
                    return result

                api.request = changed
                with self.assertRaises(publisher.PublishError):
                    publisher.publish(
                        api, "test-v1", [self.bundle], self.catalog, cancel_event=cancel,
                    )
                self.assertNotIn("DELETE", [call[0] for call in api.calls])

    def test_public_repository_is_rejected_before_writes(self):
        api = FakeGitHub(self.bundle, private=False)
        with self.assertRaisesRegex(publisher.PublishError, "private repository"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual([call[0] for call in api.calls], ["GET"])

    def test_conflicting_catalog_version_is_rejected_before_network(self):
        self.catalog["items"] = [{**self.bundle.entry, "asset_id": 123, "title": "Changed title"}]
        api = FakeGitHub(self.bundle)
        with self.assertRaisesRegex(publisher.PublishError, "new version"):
            publisher.publish(api, "test-v1", [self.bundle], self.catalog)
        self.assertEqual(api.calls, [])

    def test_dry_run_never_requests_credentials_or_network(self):
        arguments = [
            str(SCRIPT),
            "--tag",
            "test-v1",
            "--bundle-directory",
            str(self.root),
            "--catalog-output",
            str(self.root / "catalog.json"),
            "--dry-run",
        ]
        with (
            patch.object(sys, "argv", arguments),
            patch.object(publisher, "maintainer_token") as credential,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(publisher.main(), 0)
            credential.assert_not_called()
        self.assertFalse((self.root / "catalog.json").exists())

    def test_api_redirect_is_rejected_before_credentials_can_follow(self):
        with self.assertRaisesRegex(publisher.PublishError, "no credential was forwarded"):
            publisher.RejectRedirects().redirect_request(
                None, None, 302, None, None, "https://other.example/"
            )

    def test_preparation_inventory_has_a_separate_16_mib_limit(self):
        self.metadata["excluded_paths"] = ["x" * publisher.MAX_JSON_BYTES]
        self.write_metadata()
        self.assertEqual(publisher.verify_bundle(self.metadata_path).entry, self.bundle.entry)
        with patch.object(publisher, "MAX_PREPARATION_REPORT_BYTES", 1024):
            with self.assertRaisesRegex(publisher.PublishError, "JSON exceeds"):
                publisher.verify_bundle(self.metadata_path)

    def test_online_access_rejects_wrong_account_and_repository_before_writes(self):
        for field, value in (
            ("login", "another-maintainer"),
            ("login", None),
            ("private", False),
            ("repository", "zcm58/another-private-repo"),
            ("permissions", {"pull": True}),
        ):
            with self.subTest(field=field, value=value):
                api = OnlineGitHub(self.bundle, self.catalog)
                setattr(api, field, value)
                with self.assertRaises(publisher.PublishError):
                    publisher.publish_online(api, "test-v1", [self.bundle])
                self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_check_access_accepts_admin_and_outputs_expected_identity(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        api.permissions = {"admin": True, "push": False}
        self.assertEqual(
            publisher.check_access(api),
            {"login": "zcm58", "repository": publisher.REPOSITORY, "can_publish": True},
        )
        self.assertEqual(api.calls, [("GET", "/user"), ("GET", publisher.REPO_PATH)])

    def test_online_publish_verifies_release_then_commits_and_confirms_catalog(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        result = publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertEqual(result["published_items"], 1)
        self.assertEqual(result["catalog_commit"], api.head)
        self.assertTrue(result["catalog_updated"])
        self.assertEqual(api.current_catalog()["items"], [{**self.bundle.entry, "asset_id": 123}])
        methods = [method for method, _ in api.calls]
        self.assertLess(methods.index("PATCH"), methods.index("PUT"))
        self.assertEqual(
            api.calls[-1], ("GET", f"{publisher.REPO_PATH}/contents/catalog.json?ref={api.head}")
        )

    def test_online_missing_catalog_fails_before_remote_writes(self):
        api = OnlineGitHub(self.bundle, None)
        with self.assertRaisesRegex(publisher.PublishError, "catalog is unavailable"):
            publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_online_conflict_refetches_and_preserves_unrelated_entries(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        other = {**self.bundle.entry, "item_id": "another-study", "asset_id": 777}
        api.conflicts = [{**self.catalog, "items": [other], "maintainer_note": "Keep this"}]
        result = publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertTrue(result["catalog_updated"])
        self.assertEqual(len(api.catalog_writes), 2)
        self.assertNotEqual(api.catalog_writes[0]["sha"], api.catalog_writes[1]["sha"])
        self.assertEqual(api.current_catalog()["items"][0], other)
        self.assertEqual(api.current_catalog()["maintainer_note"], "Keep this")

    def test_online_conflicting_immutable_version_is_not_overwritten(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        changed = {**self.bundle.entry, "asset_id": 123, "title": "Concurrent edit"}
        api.conflicts = [{**self.catalog, "items": [changed]}]
        with self.assertRaisesRegex(publisher.PublishError, "new version"):
            publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertEqual(api.current_catalog()["items"], [changed])
        self.assertEqual(len(api.catalog_writes), 1)

    def test_online_conflict_retries_are_bounded(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        api.conflicts = [self.catalog] * publisher.MAX_CATALOG_COMMIT_ATTEMPTS
        with self.assertRaisesRegex(publisher.PublishError, "kept changing"):
            publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertEqual(len(api.catalog_writes), publisher.MAX_CATALOG_COMMIT_ATTEMPTS)
        self.assertEqual(api.current_catalog()["items"], [])

    def test_online_success_retry_does_not_write_or_upload_again(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        first = publisher.publish_online(api, "test-v1", [self.bundle])
        api.calls.clear()
        second = publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertEqual(first["catalog_commit"], second["catalog_commit"])
        self.assertFalse(second["catalog_updated"])
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_online_catalog_failure_is_not_success_and_retry_recovers_release(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        api.put_error = 503
        with self.assertRaisesRegex(publisher.PublishError, "HTTP 503"):
            publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertFalse(api.release["draft"])
        self.assertEqual(api.current_catalog()["items"], [])
        api.put_error = None
        api.calls.clear()
        result = publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertTrue(result["catalog_updated"])
        self.assertNotIn("POST", [method for method, _ in api.calls])

    def test_online_lost_commit_response_is_recoverable_without_new_writes(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        api.lose_put_response = True
        with self.assertRaisesRegex(publisher.PublishError, "no completion"):
            publisher.publish_online(api, "test-v1", [self.bundle])
        api.calls.clear()
        result = publisher.publish_online(api, "test-v1", [self.bundle])
        self.assertFalse(result["catalog_updated"])
        self.assertTrue(all(method == "GET" for method, _ in api.calls))

    def test_online_written_commit_must_contain_the_verified_catalog(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        api.confirm_wrong_catalog = True
        with self.assertRaisesRegex(publisher.PublishError, "verification failed"):
            publisher.publish_online(api, "test-v1", [self.bundle])

    def test_cli_check_access_and_online_emit_single_json_without_local_catalog(self):
        api = OnlineGitHub(self.bundle, self.catalog)
        for arguments in (
            ["--check-access"],
            ["--publish-online", "--tag", "test-v1", "--bundle-directory", str(self.root)],
        ):
            with self.subTest(arguments=arguments):
                output = io.StringIO()
                with (
                    patch.object(sys, "argv", [str(SCRIPT), *arguments]),
                    patch.object(publisher, "maintainer_token", return_value="never-displayed"),
                    patch.object(publisher, "GitHubPublisher", return_value=api),
                    contextlib.redirect_stdout(output),
                ):
                    self.assertEqual(publisher.main(), 0)
                result = json.loads(output.getvalue())
                self.assertTrue(result["can_publish"])
                self.assertEqual(result["repository"], publisher.REPOSITORY)
                self.assertNotIn("never-displayed", output.getvalue())
        self.assertFalse((self.root / "catalog.json").exists())

    def test_ordinary_cli_still_writes_local_catalog_without_online_commit(self):
        api = FakeGitHub(self.bundle)
        catalog_path = self.root / "catalog.json"
        output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    str(SCRIPT),
                    "--tag",
                    "test-v1",
                    "--bundle-directory",
                    str(self.root),
                    "--catalog-output",
                    str(catalog_path),
                ],
            ),
            patch.object(publisher, "maintainer_token", return_value="never-displayed"),
            patch.object(publisher, "GitHubPublisher", return_value=api),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(publisher.main(), 0)
        self.assertEqual(json.loads(catalog_path.read_text())["items"][0]["asset_id"], 123)
        self.assertEqual(json.loads(output.getvalue())["catalog"], str(catalog_path))
        self.assertNotIn("PUT", [method for method, _ in api.calls])
        self.assertNotIn(("GET", "/user"), api.calls)

    def test_api_rejects_other_repo_prefix_and_non_get_user(self):
        api = publisher.GitHubPublisher("credential-in-memory")
        with patch.object(api._opener, "open") as connection:
            for method, path in (
                ("GET", publisher.REPO_PATH + "-other/contents/catalog.json"),
                ("POST", "/user"),
            ):
                with self.assertRaisesRegex(publisher.PublishError, "unexpected GitHub"):
                    api.request(method, path)
            connection.assert_not_called()

    def run_failed_cli(self, error, *, operation="--check-access"):
        arguments = [str(SCRIPT)]
        if operation:
            arguments.append(operation)
        if operation != "--check-access":
            arguments.extend(
                [
                    "--tag",
                    "test-v1",
                    "--bundle-directory",
                    str(self.root),
                    "--catalog-output",
                    str(self.root / "catalog.json"),
                ]
            )
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", arguments),
            patch.object(publisher, "maintainer_token", side_effect=error),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            self.assertEqual(publisher.main(), 1)
        return output.getvalue(), errors.getvalue()

    def test_gui_failures_preserve_actionable_controlled_messages_with_a_bound(self):
        message = "An existing catalog version differs; publish a new version instead."
        for operation in ("--check-access", "--publish-online"):
            with self.subTest(operation=operation):
                output, errors = self.run_failed_cli(
                    publisher.PublishError(message),
                    operation=operation,
                )
                self.assertEqual(json.loads(output), {"error": message})
                self.assertEqual(errors, "")
        output, errors = self.run_failed_cli(publisher.PublishError(message * 100))
        self.assertEqual(len(json.loads(output)["error"]), publisher.MAX_GUI_ERROR_CHARS)
        self.assertEqual(errors, "")

    def test_gui_failures_do_not_reflect_raw_exception_or_credential_details(self):
        secret = "sensitive-credential-helper-output"
        for error in (
            OSError(secret),
            ValueError(secret),
            zipfile.BadZipFile(secret),
            publisher.subprocess.TimeoutExpired([secret], 30, output=secret, stderr=secret),
        ):
            with self.subTest(error=type(error).__name__):
                output, errors = self.run_failed_cli(error)
                self.assertNotIn(secret, output + errors)
                self.assertTrue(json.loads(output)["error"])
                self.assertEqual(errors, "")

    def test_gui_failed_credential_helper_never_reflects_captured_output(self):
        secret = "credential-output-must-not-be-displayed"
        result = publisher.subprocess.CompletedProcess(
            ["git", "credential", "fill"],
            1,
            stdout=secret,
            stderr=secret,
        )
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", [str(SCRIPT), "--check-access"]),
            patch.dict(publisher.os.environ, {"GH_TOKEN": ""}),
            patch.object(publisher.subprocess, "run", return_value=result),
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            self.assertEqual(publisher.main(), 1)
        self.assertIn("Configure Git or GH_TOKEN", json.loads(output.getvalue())["error"])
        self.assertNotIn(secret, output.getvalue() + errors.getvalue())
        self.assertEqual(errors.getvalue(), "")

    def test_ordinary_cli_failures_remain_stderr_only(self):
        with self.assertLogs(publisher.__name__, level="ERROR") as captured:
            output, errors = self.run_failed_cli(
                publisher.PublishError("Publish a new version."), operation=""
            )
        self.assertEqual(output, "")
        self.assertEqual(errors, "")
        self.assertIn("Publishing stopped: Publish a new version.", captured.output[0])


if __name__ == "__main__":
    unittest.main()


def test_cancel_before_http_request_never_opens_network(monkeypatch):
    from threading import Event

    import pytest

    cancel = Event()
    api = publisher.GitHubPublisher("synthetic-token", cancel_event=cancel)
    monkeypatch.setattr(api._opener, "open", lambda *a, **k: pytest.fail("network opened"))
    cancel.set()
    with pytest.raises(publisher.CatalogCancelled):
        api.request("GET", "/user")


def test_delete_asset_accepts_github_no_content_response(monkeypatch):
    api = publisher.GitHubPublisher("synthetic-token")
    response = io.BytesIO(b"")
    response.status = 204
    monkeypatch.setattr(api._opener, "open", lambda *args, **kwargs: response)
    assert api.request("DELETE", publisher.REPO_PATH + "/releases/assets/123") is None


def test_upload_and_validation_check_cancellation(tmp_path):
    from threading import Event

    import pytest

    cancel = Event()
    stream = publisher.CancelableUpload(io.BytesIO(b"test"), cancel)
    assert stream.read(1) == b"t"
    cancel.set()
    with pytest.raises(publisher.CatalogCancelled):
        stream.read(1)
    with pytest.raises(publisher.CatalogCancelled):
        publisher.load_prepared(tmp_path, cancel_event=cancel)


def test_git_credentials_are_noninteractive_hidden_and_not_from_project(monkeypatch, tmp_path):
    from types import SimpleNamespace

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(publisher.tempfile, "gettempdir", lambda: str(tmp_path))

    def run(command, **kwargs):
        assert command == ["git", "credential", "fill"]
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["env"]["GCM_INTERACTIVE"] == "never"
        assert kwargs["cwd"] == str(tmp_path)
        assert kwargs["creationflags"] == getattr(publisher.subprocess, "CREATE_NO_WINDOW", 0)
        assert kwargs["timeout"] == 30
        return SimpleNamespace(returncode=0, stdout="password=synthetic-token", stderr="")

    monkeypatch.setattr(publisher.subprocess, "run", run)
    assert publisher.maintainer_token() == "synthetic-token"
