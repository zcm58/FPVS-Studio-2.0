"""Verify Studio-prepared bundles, publish an immutable release, and write its catalog.

Dry runs are entirely local. Publishing uses a maintainer credential in memory; the
Worker's separate read-only GitHub App credential is never used by this script.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from threading import Event
from typing import Any, TypeGuard

REPOSITORY = "zcm58/FPVS-Studio-Library"
REPO_PATH = f"/repos/{REPOSITORY}"
MAX_ASSET_BYTES = 2 * 1024**3 - 1
MAX_UNCOMPRESSED_BYTES = 20 * 1024**3
MAX_FILES = 50000
MAX_JSON_BYTES = 1024 * 1024
MAX_PREPARATION_REPORT_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_CATALOG_COMMIT_ATTEMPTS = 3
MAX_GUI_ERROR_CHARS = 1024
VERSION_PATTERN = r"\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?(?:\+[a-z0-9.-]+)?"


class PublishError(ValueError):
    """A local or remote verification failed; do not publish the catalog."""


class CatalogCancelled(PublishError):
    """A cooperative cancellation; already received GitHub writes remain possible."""


def check_cancellation(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise CatalogCancelled("Publishing stopped; remote state may have changed.")


class CancelableUpload:
    def __init__(self, handle: Any, cancel_event: Event | None) -> None:
        self.handle = handle
        self.cancel_event = cancel_event

    def read(self, size: int = -1) -> bytes:
        check_cancellation(self.cancel_event)
        return bytes(self.handle.read(size))


class GitHubApiError(PublishError):
    """A safe HTTP failure retaining only its status for conflict handling."""

    def __init__(self, method: str, status_code: int) -> None:
        super().__init__(f"GitHub {method} request failed with HTTP {status_code}.")
        self.status_code = status_code


@dataclass(frozen=True)
class PreparedBundle:
    path: Path
    entry: dict


@dataclass(frozen=True)
class RemoteCatalog:
    catalog: dict
    blob_sha: str | None
    commit_sha: str


def read_json(path: Path, maximum: int = MAX_JSON_BYTES) -> Any:
    if path.stat().st_size > maximum:
        raise PublishError(f"JSON exceeds its size limit: {path.name}")
    with path.open("rb") as handle:
        return json.load(handle)


def file_sha256(path: Path, cancel_event: Event | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            check_cancellation(cancel_event)
            digest.update(chunk)
    return digest.hexdigest()


def positive_integer(value: Any, maximum: int) -> bool:
    return type(value) is int and 0 < value <= maximum


def bounded_string(value: Any, maximum: int, minimum: int = 1) -> bool:
    return isinstance(value, str) and minimum <= len(value) <= maximum


def validate_entry(entry: dict, *, require_asset: bool = False) -> None:
    if (
        not isinstance(entry, dict)
        or not bounded_string(entry.get("item_id"), 80)
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry["item_id"])
        or entry.get("kind") != "experiment"
        or not bounded_string(entry.get("title"), 160)
        or not bounded_string(entry.get("description"), 4000, 0)
        or entry.get("experiment_category")
        not in {
            "fpvs_oddball",
            "cognitive_load_fpvs",
            "attentional_blink",
        }
        or not bounded_string(entry.get("filename"), 160, 12)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.fpvsbundle", entry["filename"])
        or re.match(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\.", entry["filename"], re.I)
        or not positive_integer(entry.get("size_bytes"), MAX_ASSET_BYTES)
        or not positive_integer(entry.get("uncompressed_size_bytes"), MAX_UNCOMPRESSED_BYTES)
        or not positive_integer(entry.get("file_count"), MAX_FILES)
        or not isinstance(entry.get("sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
        or (require_asset and not positive_integer(entry.get("asset_id"), 2**53 - 1))
    ):
        raise PublishError("Catalog entry metadata is invalid.")
    for key in ("version", "min_studio_version"):
        if not bounded_string(entry.get(key), 64) or not re.fullmatch(
            VERSION_PATTERN, entry[key], re.I
        ):
            raise PublishError(f"Catalog {key} is invalid.")


def verify_bundle(metadata_path: Path, cancel_event: Event | None = None) -> PreparedBundle:
    check_cancellation(cancel_event)
    metadata = read_json(metadata_path, MAX_PREPARATION_REPORT_BYTES)
    if not isinstance(metadata, dict) or metadata.get("dry_run") is not False:
        raise PublishError(f"Expected a completed Studio preparation report: {metadata_path.name}")
    name = metadata.get("asset_name")
    if not isinstance(name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]*\.fpvsbundle", name
    ):
        raise PublishError("Preparation metadata needs a plain asset_name ending in .fpvsbundle.")
    path = metadata_path.parent / name
    if (
        path.is_symlink()
        or path.resolve().parent != metadata_path.parent.resolve()
        or not path.is_file()
    ):
        raise PublishError(f"Bundle must be a file in the selected directory: {name}")
    size = path.stat().st_size
    if not positive_integer(size, MAX_ASSET_BYTES) or metadata.get("size_bytes") != size:
        raise PublishError(f"Bundle size differs from preparation metadata: {name}")
    digest = file_sha256(path, cancel_event)
    if metadata.get("sha256") != digest:
        raise PublishError(f"Bundle checksum differs from preparation metadata: {name}")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(infos) > MAX_FILES + 1 or len(names) != len(set(names)):
            raise PublishError("Bundle archive has duplicate or excessive entries.")
        try:
            manifest_info = archive.getinfo("fpvs_bundle.json")
        except KeyError:
            raise PublishError("Bundle has no fpvs_bundle.json.") from None
        if manifest_info.file_size > MAX_BUNDLE_MANIFEST_BYTES:
            raise PublishError("Bundle manifest is too large.")
        if manifest_info.file_size >= 1024 * 1024 and (
            manifest_info.file_size / max(1, manifest_info.compress_size) > 200
        ):
            raise PublishError("Bundle manifest has an unsafe compression ratio.")
        manifest = json.loads(archive.read(manifest_info))
        records = manifest.get("files")
        if manifest.get("schema_version") != "1.0.0" or not isinstance(records, list):
            raise PublishError("Unsupported bundle manifest.")
        if len(records) != metadata.get("file_count") or not positive_integer(
            len(records), MAX_FILES
        ):
            raise PublishError("Bundle file count differs from preparation metadata.")
        record_names = [record.get("path") for record in records if isinstance(record, dict)]
        if len(record_names) != len(records) or any(
            not isinstance(value, str) for value in record_names
        ):
            raise PublishError("Invalid bundle file records.")
        if len(record_names) != len(set(record_names)) or set(names) != {
            "fpvs_bundle.json",
            *record_names,
        }:
            raise PublishError("Bundle archive differs from its declared file inventory.")
        total = 0
        for record in records:
            check_cancellation(cancel_event)
            relative = record["path"]
            relative_path = PurePosixPath(relative)
            if (
                relative_path.is_absolute()
                or ".." in relative_path.parts
                or "\\" in relative
                or ":" in relative
                or (relative != "project.json" and not relative.startswith("stimuli/"))
            ):
                raise PublishError("Bundle contains an unsafe or unsupported payload path.")
            info = archive.getinfo(relative)
            if (
                info.is_dir()
                or type(record.get("size_bytes")) is not int
                or record["size_bytes"] != info.file_size
            ):
                raise PublishError("Bundle payload sizes differ from the manifest.")
            if info.file_size > 4 * 1024**3:
                raise PublishError("Bundle contains an oversized payload file.")
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise PublishError("Bundle expands beyond the 20 GiB limit.")
        if set(record_names) != set(metadata.get("included_paths", [])):
            raise PublishError("Bundle inventory differs from the preparation report.")
        if metadata.get("project_id") != manifest.get("project", {}).get("project_id"):
            raise PublishError("Bundle project identity differs from the preparation report.")
    entry = {
        "item_id": metadata.get("item_id"),
        "kind": "experiment",
        "version": metadata.get("version"),
        "title": metadata.get("title"),
        "description": metadata.get("summary"),
        "experiment_category": metadata.get("category"),
        "filename": name,
        "size_bytes": size,
        "uncompressed_size_bytes": total,
        "file_count": len(records),
        "sha256": digest,
        "min_studio_version": metadata.get("minimum_studio_version"),
    }
    validate_entry(entry)
    return PreparedBundle(path=path, entry=entry)


def load_prepared(directory: Path, cancel_event: Event | None = None) -> list[PreparedBundle]:
    check_cancellation(cancel_event)
    if not directory.is_dir():
        raise PublishError("Bundle directory does not exist.")
    reports = sorted(directory.glob("*.json"))
    if not reports or len(reports) > 500:
        raise PublishError("Select a directory with 1-500 Studio preparation reports.")
    bundles = [verify_bundle(path, cancel_event) for path in reports]
    identities = {(item.entry["item_id"], item.entry["version"]) for item in bundles}
    if len(identities) != len(bundles) or len({item.path.name for item in bundles}) != len(bundles):
        raise PublishError("Duplicate item versions or asset filenames in preparation reports.")
    return bundles


def maintainer_token() -> str:
    token = os.environ.get("GH_TOKEN", "")
    if token:
        return token
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    result = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
        capture_output=True,
        env=env,
        timeout=30,
        check=False,
        cwd=tempfile.gettempdir(),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        raise PublishError(
            "No noninteractive GitHub credential is available. Configure Git or GH_TOKEN."
        )
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    token = fields.get("password", "")
    if not token:
        raise PublishError("Git did not return a GitHub credential.")
    return token


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, request: Any, response: Any, code: Any, message: Any, headers: Any, new_url: Any
    ) -> Any:
        raise PublishError("GitHub returned a redirect; no credential was forwarded.")


class GitHubPublisher:
    def __init__(self, token: str, cancel_event: Event | None = None) -> None:
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,8192}", token):
            raise PublishError("The GitHub credential has an invalid format.")
        self._token = token
        self._cancel_event = cancel_event
        self._opener = urllib.request.build_opener(RejectRedirects())

    def request(
        self, method: str, path: str, *, payload: Any = None, upload: Path | None = None
    ) -> Any:
        check_cancellation(self._cancel_event)
        # Callers supply only constructed repository API paths, never response URLs.
        permitted_path = path == REPO_PATH or path.startswith(REPO_PATH + "/")
        if method == "GET" and path == "/user" and upload is None:
            permitted_path = True
        if not permitted_path or ".." in path:
            raise PublishError("Refusing an unexpected GitHub repository path.")
        host = "uploads.github.com" if upload else "api.github.com"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "FPVS-Studio-Library-Publisher",
            "X-GitHub-Api-Version": "2026-03-10",
        }
        handle = None
        data: bytes | CancelableUpload | None
        try:
            if upload:
                handle = upload.open("rb")
                data = CancelableUpload(handle, self._cancel_event)
                headers.update(
                    {
                        "Content-Type": "application/octet-stream",
                        "Content-Length": str(upload.stat().st_size),
                    }
                )
            else:
                data = json.dumps(payload).encode("utf-8") if payload is not None else None
                if data is not None:
                    headers["Content-Type"] = "application/json"
            request = urllib.request.Request(
                f"https://{host}{path}", data=data, headers=headers, method=method
            )
            with self._opener.open(request, timeout=120 if upload else 30) as response:
                raw = response.read(8 * MAX_JSON_BYTES + 1)
                if len(raw) > 8 * MAX_JSON_BYTES:
                    raise PublishError("GitHub response exceeded its size limit.")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raise GitHubApiError(method, error.code) from None
        except urllib.error.URLError:
            raise PublishError(
                "GitHub request failed; no release/catalog completion is assumed."
            ) from None
        finally:
            if handle is not None:
                handle.close()

    def list_all(self, path: str) -> list[dict]:
        values = []
        for page in range(1, 11):
            result = self.request("GET", f"{path}?per_page=100&page={page}")
            if not isinstance(result, list):
                raise PublishError("Unexpected GitHub list response.")
            values.extend(result)
            if len(result) < 100:
                return values
        raise PublishError("GitHub listing exceeded the publisher's 1,000-entry limit.")


def verify_asset(asset: dict, bundle: PreparedBundle) -> int:
    entry = bundle.entry
    if (
        asset.get("name") != entry["filename"]
        or asset.get("size") != entry["size_bytes"]
        or asset.get("digest") != f"sha256:{entry['sha256']}"
        or asset.get("state") != "uploaded"
        or not positive_integer(asset.get("id"), 2**53 - 1)
    ):
        raise PublishError(
            f"GitHub asset lacks the exact expected SHA-256/size: {entry['filename']}"
        )
    return int(asset["id"])


def merge_catalog(existing: dict, entries: list[dict]) -> dict:
    if existing.get("schema_version") != "1.0" or not bounded_string(
        existing.get("library_name"), 120
    ):
        raise PublishError("Existing catalog envelope is invalid.")
    if not isinstance(existing.get("items"), list) or len(existing["items"]) > 500:
        raise PublishError("Existing catalog items are invalid.")
    items = list(existing["items"])
    for item in items:
        if not isinstance(item, dict):
            raise PublishError("Existing catalog items must be objects.")
        if item.get("kind") != "condition":
            validate_entry(item, require_asset=True)
    identities = [(item.get("item_id"), item.get("version")) for item in items]
    if len(identities) != len(set(identities)):
        raise PublishError("Existing catalog has duplicate versions.")
    for entry in entries:
        identity = entry["item_id"], entry["version"]
        if identity in identities:
            previous = items[identities.index(identity)]
            if any(previous.get(key) != value for key, value in entry.items()):
                raise PublishError(
                    "An existing catalog version differs; publish a new version instead."
                )
        else:
            items.append(entry)
            identities.append(identity)
    result = {**existing, "items": items}
    if len(items) > 500 or len(json.dumps(result).encode("utf-8")) > MAX_JSON_BYTES:
        raise PublishError("Merged catalog exceeds its published limits.")
    return result


def publish(
    api: GitHubPublisher,
    tag: str,
    bundles: list[PreparedBundle],
    existing: dict,
    *,
    cancel_event: Event | None = None,
) -> dict:
    # Validate known catalog fields before any remote mutation.
    merge_catalog(existing, [bundle.entry for bundle in bundles])
    repository = api.request("GET", REPO_PATH)
    if repository.get("full_name") != REPOSITORY or repository.get("private") is not True:
        raise PublishError(f"Publisher requires the private repository {REPOSITORY}.")
    releases = api.list_all(f"{REPO_PATH}/releases")
    matches = [release for release in releases if release.get("tag_name") == tag]
    if len(matches) > 1:
        raise PublishError("Multiple releases use the selected tag.")
    release = (
        matches[0]
        if matches
        else api.request(
            "POST",
            f"{REPO_PATH}/releases",
            payload={
                "tag_name": tag,
                "target_commitish": repository["default_branch"],
                "name": tag,
                "body": "Validated FPVS Studio whole-project library bundles.",
                "draft": True,
                "prerelease": False,
                "make_latest": "false",
            },
        )
    )
    release_id = release.get("id")
    if not positive_integer(release_id, 2**53 - 1) or type(release.get("draft")) is not bool:
        raise PublishError("GitHub returned an invalid release identity.")
    assets = api.list_all(f"{REPO_PATH}/releases/{release_id}/assets")
    names = [asset.get("name") for asset in assets]
    expected = {bundle.path.name for bundle in bundles}
    if len(names) != len(set(names)) or set(names) - expected:
        raise PublishError(
            "Release contains unrelated or duplicate assets; use another release tag."
        )
    by_name = {asset["name"]: asset for asset in assets}
    for bundle in bundles:
        if bundle.path.name in by_name:
            verify_asset(by_name[bundle.path.name], bundle)
        elif not release["draft"]:
            raise PublishError(
                "Published releases are immutable; missing assets require a new tag."
            )
    entries = []
    for bundle in bundles:
        # Rehash immediately before an upload; changed local data cannot be published.
        if (
            bundle.path.stat().st_size != bundle.entry["size_bytes"]
            or file_sha256(bundle.path, cancel_event) != bundle.entry["sha256"]
        ):
            raise PublishError("A local bundle changed after verification.")
        asset = by_name.get(bundle.path.name)
        if asset is None:
            asset = api.request(
                "POST",
                f"{REPO_PATH}/releases/{release_id}/assets?name={urllib.parse.quote(bundle.path.name)}",
                upload=bundle.path,
            )
        asset_id = verify_asset(asset, bundle)
        entries.append({**bundle.entry, "asset_id": asset_id})
    catalog = merge_catalog(existing, entries)
    # Re-fetch the asset inventory before releasing the draft to detect concurrent uploads.
    final_assets = api.list_all(f"{REPO_PATH}/releases/{release_id}/assets")
    if {asset.get("name") for asset in final_assets} != expected or len(final_assets) != len(
        bundles
    ):
        raise PublishError("Release inventory changed during publishing; draft was not published.")
    for bundle in bundles:
        final_asset = next(asset for asset in final_assets if asset["name"] == bundle.path.name)
        expected_id = next(
            entry["asset_id"] for entry in entries if entry["filename"] == bundle.path.name
        )
        if verify_asset(final_asset, bundle) != expected_id:
            raise PublishError("Release asset identity changed during publishing.")
    if release["draft"]:
        completed = api.request(
            "PATCH",
            f"{REPO_PATH}/releases/{release_id}",
            payload={"draft": False, "make_latest": "false"},
        )
        if completed.get("draft") is not False or completed.get("id") != release_id:
            raise PublishError("Release publication was not confirmed; no catalog was written.")
    return catalog


def check_access(api: GitHubPublisher) -> dict:
    """Require the named maintainer account and actual private-repository write access."""
    user = api.request("GET", "/user")
    login = user.get("login") if isinstance(user, dict) else None
    if not isinstance(login, str) or login.lower() != "zcm58":
        raise PublishError("Developer publishing requires the GitHub account zcm58.")
    repository = api.request("GET", REPO_PATH)
    permissions = repository.get("permissions", {}) if isinstance(repository, dict) else {}
    if (
        not isinstance(repository, dict)
        or repository.get("full_name") != REPOSITORY
        or repository.get("private") is not True
        or not isinstance(permissions, dict)
        or not (permissions.get("push") is True or permissions.get("admin") is True)
    ):
        raise PublishError(f"The zcm58 account needs write access to the private {REPOSITORY}.")
    return {"login": "zcm58", "repository": REPOSITORY, "can_publish": True}


def _valid_git_sha(value: Any) -> TypeGuard[str]:
    return (
        isinstance(value, str) and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value) is not None
    )


def read_remote_catalog(api: GitHubPublisher, *, commit_sha: str | None = None) -> RemoteCatalog:
    """Read catalog.json at an exact main commit for compare-and-swap publication."""
    if commit_sha is None:
        branch = api.request("GET", f"{REPO_PATH}/branches/main")
        commit = branch.get("commit") if isinstance(branch, dict) else None
        commit_sha = commit.get("sha") if isinstance(commit, dict) else None
    if not _valid_git_sha(commit_sha):
        raise PublishError("GitHub did not identify a valid main-branch commit.")
    try:
        response = api.request("GET", f"{REPO_PATH}/contents/catalog.json?ref={commit_sha}")
    except GitHubApiError as error:
        if error.status_code != 404:
            raise
        raise PublishError(
            "The published catalog is unavailable on main; restore it before publishing.",
        ) from None
    if (
        not isinstance(response, dict)
        or response.get("type") != "file"
        or response.get("path") != "catalog.json"
        or response.get("encoding") != "base64"
        or not positive_integer(response.get("size"), MAX_JSON_BYTES)
        or not _valid_git_sha(response.get("sha"))
        or not bounded_string(response.get("content"), 2 * MAX_JSON_BYTES)
    ):
        raise PublishError("GitHub returned invalid or oversized catalog content.")
    try:
        raw = base64.b64decode("".join(response["content"].split()), validate=True)
        if len(raw) != response["size"] or len(raw) > MAX_JSON_BYTES:
            raise PublishError("GitHub catalog size differs from its metadata.")
        catalog = json.loads(raw)
        if not isinstance(catalog, dict):
            raise PublishError("GitHub catalog must contain an object.")
        merge_catalog(catalog, [])
    except (binascii.Error, UnicodeError, json.JSONDecodeError):
        raise PublishError("GitHub catalog content is invalid.") from None
    return RemoteCatalog(catalog, response["sha"], commit_sha)


def commit_online_catalog(
    api: GitHubPublisher,
    tag: str,
    entries: list[dict],
    snapshot: RemoteCatalog,
) -> tuple[str, bool]:
    """Merge concurrent catalog updates with a bounded retry and verify the written commit."""
    for attempt in range(MAX_CATALOG_COMMIT_ATTEMPTS):
        merged = merge_catalog(snapshot.catalog, entries)
        if merged == snapshot.catalog:
            return snapshot.commit_sha, False
        raw = (json.dumps(merged, indent=2) + "\n").encode("utf-8")
        if len(raw) > MAX_JSON_BYTES:
            raise PublishError("Formatted catalog exceeds its published size limit.")
        payload = {
            "message": f"Publish experiment library release {tag}",
            "content": base64.b64encode(raw).decode("ascii"),
            "branch": "main",
        }
        if snapshot.blob_sha is not None:
            payload["sha"] = snapshot.blob_sha
        try:
            written = api.request("PUT", f"{REPO_PATH}/contents/catalog.json", payload=payload)
        except GitHubApiError as error:
            if error.status_code not in {409, 422}:
                raise
            if attempt + 1 == MAX_CATALOG_COMMIT_ATTEMPTS:
                raise PublishError(
                    "The release is verified, but the catalog kept changing. Retry publication.",
                ) from None
            latest = read_remote_catalog(api)
            if error.status_code == 422 and latest.blob_sha == snapshot.blob_sha:
                raise
            snapshot = latest
            continue
        commit = written.get("commit") if isinstance(written, dict) else None
        commit_sha = commit.get("sha") if isinstance(commit, dict) else None
        if not _valid_git_sha(commit_sha):
            raise PublishError(
                "Catalog update returned no valid commit; retry to verify publication."
            )
        confirmed = read_remote_catalog(api, commit_sha=commit_sha)
        if confirmed.catalog != merged or confirmed.blob_sha is None:
            raise PublishError(
                "Committed catalog verification failed; publication is not confirmed."
            )
        return commit_sha, True
    raise PublishError("Catalog publication was not confirmed.")


def publish_online(
    api: GitHubPublisher,
    tag: str,
    bundles: list[PreparedBundle],
    *,
    cancel_event: Event | None = None,
) -> dict:
    """Publish using remote main; no local checkout catalog or git push is required."""
    access = check_access(api)
    snapshot = read_remote_catalog(api)
    published = publish(api, tag, bundles, snapshot.catalog, cancel_event=cancel_event)
    by_identity = {(item["item_id"], item["version"]): item for item in published["items"]}
    entries = [
        {
            **bundle.entry,
            "asset_id": by_identity[(bundle.entry["item_id"], bundle.entry["version"])]["asset_id"],
        }
        for bundle in bundles
    ]
    # Uploads can take minutes. Re-read main before deciding that publication is already complete.
    commit_sha, updated = commit_online_catalog(api, tag, entries, read_remote_catalog(api))
    return {
        **access,
        "tag": tag,
        "published_items": len(bundles),
        "catalog_commit": commit_sha,
        "catalog_updated": updated,
        "branch": "main",
        "catalog_url": f"https://github.com/{REPOSITORY}/blob/{commit_sha}/catalog.json",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--check-access",
        action="store_true",
        help="Verify zcm58 publishing access; emit JSON only",
    )
    operation.add_argument(
        "--publish-online",
        action="store_true",
        help="Publish and commit catalog.json to remote main with conflict checks",
    )
    parser.add_argument("--tag", help="Release tag; published assets are never replaced")
    parser.add_argument(
        "--bundle-directory",
        type=Path,
        help="Reviewed Studio bundles and preparation JSON reports",
    )
    parser.add_argument(
        "--catalog-output",
        type=Path,
        default=Path("catalog.json"),
        help="Merge and write this local catalog; commit/push separately",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate local bundles and catalog only; no credentials or network",
    )
    args = parser.parse_args()
    if args.check_access and (args.dry_run or args.tag or args.bundle_directory):
        parser.error("--check-access cannot be combined with bundle or dry-run options.")
    if not args.check_access and (not args.tag or args.bundle_directory is None):
        parser.error("--tag and --bundle-directory are required for publication or dry-run.")
    try:
        if args.check_access:
            sys.stdout.write((json.dumps(check_access(GitHubPublisher(maintainer_token())))) + "\n")
            return 0
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", args.tag):
            raise PublishError("Tag must be a plain release name up to 100 characters.")
        bundles = load_prepared(args.bundle_directory)
        if args.publish_online and not args.dry_run:
            sys.stdout.write(
                (json.dumps(publish_online(GitHubPublisher(maintainer_token()), args.tag, bundles)))
                + "\n"
            )
            return 0
        existing_bytes = args.catalog_output.read_bytes() if args.catalog_output.exists() else None
        existing = (
            read_json(args.catalog_output)
            if existing_bytes is not None
            else {
                "schema_version": "1.0",
                "library_name": "NERD Lab Experiment Library",
                "items": [],
            }
        )
        if args.dry_run:
            merge_catalog(existing, [bundle.entry for bundle in bundles])
            sys.stdout.write(
                (
                    json.dumps(
                        {
                            "dry_run": True,
                            "repository": REPOSITORY,
                            "tag": args.tag,
                            "items": [bundle.entry for bundle in bundles],
                        },
                        indent=2,
                    )
                )
                + "\n"
            )
            return 0
        catalog = publish(GitHubPublisher(maintainer_token()), args.tag, bundles, existing)
        current = args.catalog_output.read_bytes() if args.catalog_output.exists() else None
        if current != existing_bytes:
            raise PublishError(
                "Local catalog changed during publishing; preserve it and rerun to merge."
            )
        args.catalog_output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=args.catalog_output.parent,
                prefix=".catalog-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                json.dump(catalog, handle, indent=2)
                handle.write("\n")
            temporary.replace(args.catalog_output)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        sys.stdout.write(
            (
                json.dumps(
                    {
                        "repository": REPOSITORY,
                        "tag": args.tag,
                        "catalog": str(args.catalog_output),
                        "published_items": len(bundles),
                    }
                )
            )
            + "\n"
        )
        return 0
    except (
        PublishError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        subprocess.TimeoutExpired,
    ) as error:
        if args.check_access or args.publish_online:
            if isinstance(error, PublishError):
                message = " ".join(str(error).split())[:MAX_GUI_ERROR_CHARS]
            elif isinstance(error, subprocess.TimeoutExpired):
                message = "GitHub credential lookup timed out. Configure Git or GH_TOKEN and retry."
            elif isinstance(error, OSError):
                message = "A file or network operation failed. Check access and retry."
            else:
                message = (
                    "Bundle or catalog data could not be read. Check the preparation and retry."
                )
            sys.stdout.write((json.dumps({"error": message})) + "\n")
        else:
            # Preserve the ordinary CLI; GUI modes never reflect raw external exceptions.
            logging.getLogger(__name__).error("Publishing stopped: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
