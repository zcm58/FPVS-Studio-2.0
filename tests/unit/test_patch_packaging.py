"""Sparse payload equivalence and trust-boundary tests; no application or Qt launch."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
for name in ("build_installer_inventory", "build_patch", "check_build_dll_origins"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
patch = sys.modules["build_patch"]
inventory = sys.modules["build_installer_inventory"]
origins = sys.modules["check_build_dll_origins"]


def _write_tree(root: Path, files: dict[str, bytes]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _manifest(root: Path, destination: Path, version: str) -> Path:
    destination.write_bytes(
        inventory.serialize_manifest(
            inventory.inventory_bundle(root), kind="current", version=version
        ).encode("utf-8-sig")
    )
    return destination


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, object]:
    source = tmp_path / "source"
    target = tmp_path / "target"
    _write_tree(
        source,
        {
            "FPVS Studio.exe": b"base exe",
            "_internal/retained.dll": b"unchanged bytes",
            "_internal/changed.dll": b"old bytes",
            "_internal/removed.dll": b"obsolete bytes",
            "_internal/fpvs_studio-1.5.0.dist-info/METADATA": b"Version: 1.5.0\n",
        },
    )
    _write_tree(
        target,
        {
            "FPVS Studio.exe": b"target exe",
            "_internal/retained.dll": b"unchanged bytes",
            "_internal/changed.dll": b"new bytes",
            "_internal/new.dll": b"added bytes",
            "_internal/fpvs_studio-1.5.1.dist-info/METADATA": b"Version: 1.5.1\n",
        },
    )
    baseline = _manifest(source, tmp_path / "baseline.txt", "1.5.0")
    target_manifest = _manifest(target, tmp_path / "target.txt", "1.5.1")
    return {
        "baseline_inventory": baseline,
        "source_inventory_sha256": inventory.sha256_file(baseline),
        "bundle_root": target,
        "target_inventory": target_manifest,
        "target_version": "1.5.1",
        "output_dir": tmp_path / "patch",
    }


def test_patch_payload_reconstructs_exact_target(inputs: dict, tmp_path: Path) -> None:
    result = patch.prepare_patch(**inputs)
    payload = inputs["output_dir"] / "payload"
    paths = {path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()}
    assert paths == {
        "FPVS Studio.exe",
        "_internal/changed.dll",
        "_internal/new.dll",
        "_internal/fpvs_studio-1.5.1.dist-info/METADATA",
    }
    reconstructed = tmp_path / "reconstructed"
    shutil.copytree(tmp_path / "source", reconstructed)
    shutil.copytree(payload, reconstructed, dirs_exist_ok=True)
    _, source, _ = patch.current_inventory(inputs["baseline_inventory"])
    _, target, _ = patch.current_inventory(inputs["target_inventory"])
    for removed in inventory.obsolete_inventory(source, target).files:
        (reconstructed / removed).unlink()
    assert inventory.inventory_bundle(reconstructed) == target
    assert result["retained_files"] == 1
    assert result["removed_files"] == 2
    assert result["payload_files"] == 4
    assert result["source_inventory_sha256"] == inputs["source_inventory_sha256"]


@pytest.mark.parametrize("previous_updater", [None, b"previous helper", b"target helper"])
def test_patch_ownership_includes_added_changed_or_retained_independent_updater(
    inputs: dict, tmp_path: Path, previous_updater: bytes | None
) -> None:
    relative = "Updater/FPVS Studio Updater.exe"
    if previous_updater is not None:
        _write_tree(tmp_path / "source", {relative: previous_updater})
    _write_tree(inputs["bundle_root"], {relative: b"target helper"})
    _manifest(tmp_path / "source", inputs["baseline_inventory"], "1.5.0")
    inputs["source_inventory_sha256"] = inventory.sha256_file(inputs["baseline_inventory"])
    _manifest(inputs["bundle_root"], inputs["target_inventory"], "1.5.1")

    patch.prepare_patch(**inputs)

    _, target, _ = patch.current_inventory(inputs["target_inventory"])
    assert target.files[relative] == (hashlib.sha256(b"target helper").hexdigest(),)
    payload = inputs["output_dir"] / "payload" / relative
    if previous_updater == b"target helper":
        assert not payload.exists()
    else:
        assert payload.read_bytes() == b"target helper"


def test_wrong_authenticated_baseline_refused_before_output(inputs: dict) -> None:
    inputs["source_inventory_sha256"] = "0" * 64
    with pytest.raises(inventory.InventoryError, match="authenticated SHA-256"):
        patch.prepare_patch(**inputs)
    assert not inputs["output_dir"].exists()


@pytest.mark.parametrize(
    "relative", ["../outside", "_internal/../../outside", "C:/outside", patch.PATCH_MARKER_NAME]
)
def test_unsafe_baseline_paths_refused(inputs: dict, relative: str) -> None:
    baseline = inputs["baseline_inventory"]
    baseline.write_bytes(
        baseline.read_bytes() + f"{relative}|{'1' * 64}\r\n".encode()
    )
    inputs["source_inventory_sha256"] = inventory.sha256_file(baseline)
    with pytest.raises(inventory.InventoryError):
        patch.prepare_patch(**inputs)
    assert not inputs["output_dir"].exists()


@pytest.mark.parametrize("version", ["1.5.0", "1.4.0"])
def test_same_or_older_target_refused(inputs: dict, version: str) -> None:
    inputs["target_version"] = version
    with pytest.raises(inventory.InventoryError, match="older than"):
        patch.prepare_patch(**inputs)


def test_changed_target_after_inventory_refused(inputs: dict) -> None:
    (inputs["bundle_root"] / "_internal/retained.dll").write_bytes(b"unexpected")
    with pytest.raises(inventory.InventoryError, match="differs from"):
        patch.prepare_patch(**inputs)


def test_target_metadata_version_required(inputs: dict) -> None:
    metadata = inputs["bundle_root"] / "_internal/fpvs_studio-1.5.1.dist-info/METADATA"
    metadata.write_bytes(b"Version: 1.5.0\n")
    _manifest(inputs["bundle_root"], inputs["target_inventory"], "1.5.1")
    with pytest.raises(inventory.InventoryError, match="package metadata"):
        patch.prepare_patch(**inputs)


def test_stale_payload_directory_refused(inputs: dict) -> None:
    inputs["output_dir"].mkdir()
    sentinel = inputs["output_dir"] / "user.txt"
    sentinel.write_bytes(b"preserve")
    with pytest.raises(inventory.InventoryError, match="new directory"):
        patch.prepare_patch(**inputs)
    assert sentinel.read_bytes() == b"preserve"


def test_hardlinked_target_refused(inputs: dict, tmp_path: Path) -> None:
    source = inputs["bundle_root"] / "_internal/retained.dll"
    os.link(source, tmp_path / "external-link.dll")
    with pytest.raises(inventory.InventoryError, match="hardlink"):
        patch.prepare_patch(**inputs)


def test_linked_baseline_refused(inputs: dict, tmp_path: Path) -> None:
    os.link(inputs["baseline_inventory"], tmp_path / "linked-manifest.txt")
    with pytest.raises(inventory.InventoryError, match="single-link"):
        patch.prepare_patch(**inputs)


def _make_junction(junction: Path, outside: Path) -> None:
    if os.name != "nt":
        pytest.skip("Native Windows junction fixture")
    environment = dict(os.environ, PATCH_LINK=str(junction), PATCH_TARGET=str(outside))
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            "New-Item -ItemType Junction -Path $env:PATCH_LINK "
            "-Value $env:PATCH_TARGET -ErrorAction Stop | Out-Null",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr


def test_junction_target_subdirectory_refused(inputs: dict, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"preserve")
    junction = inputs["bundle_root"] / "linked"
    _make_junction(junction, outside)
    try:
        with pytest.raises(inventory.InventoryError, match="unsafe directory"):
            patch.prepare_patch(**inputs)
        assert (outside / "sentinel").read_bytes() == b"preserve"
        assert not inputs["output_dir"].exists()
    finally:
        os.rmdir(junction)


def test_release_manifest_binds_actual_installer_bytes(inputs: dict, tmp_path: Path) -> None:
    result = patch.prepare_patch(**inputs)
    output = tmp_path / "installer"
    output.mkdir()
    (output / "FPVS-Studio-Setup-1.5.1.exe").write_bytes(b"full installer fixture")
    (output / result["asset_name"]).write_bytes(b"patch installer fixture")
    manifest = patch.build_release_manifest(
        target_version="1.5.1",
        installer_dir=output,
        patch_builds=[inputs["output_dir"] / "patch-build.json"],
    )
    document = json.loads(manifest.read_text())
    assert document == {
        "schema_version": 1,
        "target_version": "1.5.1",
        "platform": "windows-x64",
        "patches": [{
            "from_version": "1.5.0",
            "source_inventory_sha256": inputs["source_inventory_sha256"],
            "asset_name": "FPVS-Studio-Patch-1.5.0-to-1.5.1.exe",
            "size_bytes": len(b"patch installer fixture"),
            "sha256": hashlib.sha256(b"patch installer fixture").hexdigest(),
        }],
    }
    assert manifest.with_suffix(".json.sha256").read_text().startswith(
        inventory.sha256_file(manifest)
    )


def _write_build_toc(
    path: Path, kind: str, rows: list[tuple[str, str, str]],
) -> None:
    document = (rows,) if kind == "studio" else (
        "FPVS Studio Updater.pkg", {"BINARY": True}, rows, "python310.dll", False,
        False, False, [], None, None, None,
    )
    path.write_text(repr(document), encoding="utf-8")


@pytest.mark.parametrize("kind", ["studio", "updater"])
def test_dll_origin_audit_accepts_native_files_from_both_python_roots(
    tmp_path: Path, kind: str,
) -> None:
    environment = tmp_path / "venv"
    base = tmp_path / "python"
    _write_tree(environment, {"Lib/module.pyd": b"extension"})
    _write_tree(base, {"DLLs/runtime.dll": b"runtime"})
    toc = tmp_path / "build.toc"
    _write_build_toc(toc, kind, [
        ("module.pyd", str(environment / "Lib/module.pyd"), "EXTENSION"),
        ("runtime.dll", str(base / "DLLs/runtime.dll"), "BINARY"),
    ])
    audit = origins.audit_toc(toc, kind, (environment.resolve(), base.resolve()))
    assert audit.native_files == 2
    assert audit.sha256 == hashlib.sha256(toc.read_bytes()).hexdigest()


@pytest.mark.parametrize("kind", ["studio", "updater"])
def test_dll_origin_audit_rejects_external_dlls_even_as_data(
    tmp_path: Path, kind: str,
) -> None:
    environment = tmp_path / "venv"
    foreign = tmp_path / "venv-other"
    _write_tree(environment, {"runtime.dll": b"trusted"})
    _write_tree(foreign, {"runtime.dll": b"foreign"})
    toc = tmp_path / "build.toc"
    _write_build_toc(toc, kind, [
        ("runtime.dll", str(environment / "runtime.dll"), "BINARY"),
        ("foreign.dll", str(foreign / "runtime.dll"), "DATA"),
    ])
    with pytest.raises(origins.NativeOriginError, match="outside approved Python paths"):
        origins.audit_toc(toc, kind, (environment.resolve(),))


def test_dll_origin_audit_resolves_junction_before_checking_containment(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    outside = tmp_path / "outside"
    environment.mkdir()
    _write_tree(outside, {"runtime.dll": b"foreign"})
    link = environment / "linked"
    _make_junction(link, outside)
    try:
        toc = tmp_path / "build.toc"
        _write_build_toc(toc, "studio", [("runtime.dll", str(link / "runtime.dll"), "BINARY")])
        with pytest.raises(origins.NativeOriginError, match="outside approved Python paths"):
            origins.audit_toc(toc, "studio", (environment.resolve(),))
    finally:
        os.rmdir(link)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("__import__('os').getcwd()", "Malformed PyInstaller TOC"),
        ("([], [], [])", "Unexpected studio PyInstaller TOC format"),
        ("([('bad', 'row')],)", "Malformed PyInstaller TOC row"),
        ("([],)", "No native files were found"),
        ("([('a.dll', 'relative.dll', 'BINARY')],)", "Native source is not absolute"),
    ],
)
def test_dll_origin_audit_fails_closed_on_bad_toc(
    tmp_path: Path, contents: str, message: str,
) -> None:
    toc = tmp_path / "build.toc"
    toc.write_text(contents, encoding="utf-8")
    with pytest.raises(origins.NativeOriginError, match=message):
        origins.audit_toc(toc, "studio", (tmp_path.resolve(),))


def test_dll_origin_audit_refuses_missing_toc(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        origins.audit_toc(tmp_path / "missing.toc", "studio", (tmp_path.resolve(),))


@pytest.mark.parametrize("change", ["asset", "extra", "missing", "toc", "receipt", "absent"])
def test_installer_build_receipt_detects_changed_evidence(tmp_path: Path, change: str) -> None:
    full = "FPVS-Studio-Setup-2.8.1.exe"
    manifest = "FPVS-Studio-Update-2.8.1.json"
    sparse = "FPVS-Studio-Patch-2.8.0-to-2.8.1.exe"
    installer = tmp_path / "installer"
    _write_tree(installer, {
        name: name.encode()
        for artifact in (full, manifest, sparse)
        for name in (artifact, f"{artifact}.sha256")
    })
    studio = origins.TocAudit(2, "1" * 64)
    updater = origins.TocAudit(2, "2" * 64)
    receipt = tmp_path / "receipt.json"
    origins.check_receipt(receipt, installer, studio, updater, write=True)
    origins.check_receipt(receipt, installer, studio, updater, write=False)
    assert set(json.loads(receipt.read_bytes())["assets"]) == {
        full, f"{full}.sha256", manifest, f"{manifest}.sha256", sparse, f"{sparse}.sha256",
    }
    if change == "asset":
        # Same-size content changes must also fail verification.
        (installer / full).write_bytes(b"x" * len(full))
    elif change == "extra":
        (installer / "unexpected.exe.sha256").write_bytes(b"unexpected")
    elif change == "missing":
        (installer / f"{sparse}.sha256").unlink()
    elif change == "toc":
        updater = origins.TocAudit(2, "3" * 64)
    elif change == "receipt":
        receipt.write_bytes(b"invalid JSON")
    else:
        receipt.unlink()
    with pytest.raises((FileNotFoundError, origins.NativeOriginError)):
        origins.check_receipt(receipt, installer, studio, updater, write=False)


def test_native_patch_recovery_and_commit_guards_are_present() -> None:
    native = (SCRIPTS.parent / "packaging/inno/patch_upgrade.iss").read_text()
    assert "PatchSourceSHA256" in native
    assert "PatchKnownRecoveryState" in native
    assert "PatchVerifyRecords(PatchSourceRecords)" in native
    assert "PatchVerifyRecords(PatchTargetRecords)" in native
    assert "PatchTransactionSHA256" in native
    installer = (SCRIPTS.parent / "packaging/inno/fpvs_studio.iss").read_text()
    assert "if not PatchVerifyInstalledTarget then" in installer
    assert "function GetCustomSetupExitCode" in native
    assert "Result := 12" in native
    event = installer.split("procedure CurStepChanged", 1)[1]
    event = event.split("procedure DeinitializeSetup", 1)[0]
    assert event.index("OwnedReconcileAfterSuccess") < event.index("if RelaunchRequested")
