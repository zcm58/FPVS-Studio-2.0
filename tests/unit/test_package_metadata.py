"""Packaging metadata regression guards."""

from __future__ import annotations

import json
import os
import re
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from PIL import ImageFont

from fpvs_studio import __version__
from fpvs_studio.assets import bundled_task_font_path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_TEXT = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
PACKAGE_INIT_TEXT = (REPO_ROOT / "src" / "fpvs_studio" / "__init__.py").read_text(
    encoding="utf-8"
)
PYINSTALLER_SPEC_TEXT = (
    REPO_ROOT / "packaging" / "pyinstaller" / "fpvs_studio.spec"
).read_text(encoding="utf-8")
BUILD_EXE_TEXT = (REPO_ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8")
BUILD_INSTALLER_TEXT = (REPO_ROOT / "scripts" / "build_installer.ps1").read_text(
    encoding="utf-8"
)
BUILD_RELEASE_TEXT = (REPO_ROOT / "scripts" / "build_release.ps1").read_text(
    encoding="utf-8"
)
BUILD_PATHS_TEXT = (REPO_ROOT / "scripts" / "build_paths.ps1").read_text(encoding="utf-8")
PACKAGED_SMOKE_TEXT = (REPO_ROOT / "src" / "fpvs_studio" / "app" / "packaged_smoke.py").read_text(
    encoding="utf-8"
)
GUI_PACKAGED_SMOKE_TEXT = (
    REPO_ROOT / "src" / "fpvs_studio" / "gui" / "packaged_smoke.py"
).read_text(encoding="utf-8")
INNO_SCRIPT_TEXT = (REPO_ROOT / "packaging" / "inno" / "fpvs_studio.iss").read_text(
    encoding="utf-8"
)
INNO_OWNERSHIP_TEXT = (REPO_ROOT / "packaging" / "inno" / "owned_files.iss").read_text(
    encoding="utf-8"
)
INNO_CACHE_TEXT = (REPO_ROOT / "packaging" / "inno" / "updater_cache.iss").read_text(
    encoding="utf-8"
)


def _extract_list_assignment(name: str) -> str:
    match = re.search(
        rf"(?ms)^{re.escape(name)} = \[(.*?)^\]",
        PYPROJECT_TEXT,
    )
    if match is None:
        raise AssertionError(f"Could not find list assignment for '{name}'.")
    return match.group(1)


def test_pyproject_targets_python_310_only() -> None:
    assert 'name = "fpvs-studio"' in PYPROJECT_TEXT
    assert 'requires-python = ">=3.10,<3.11"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3 :: Only"' in PYPROJECT_TEXT
    assert '"Programming Language :: Python :: 3.10"' in PYPROJECT_TEXT


def test_package_version_matches_pyproject_version() -> None:
    pyproject_match = re.search(r'^version = "([^"]+)"$', PYPROJECT_TEXT, re.MULTILINE)

    assert pyproject_match is not None
    assert "version(\"fpvs-studio\")" in PACKAGE_INIT_TEXT
    assert "_source_tree_version() or _installed_version()" in PACKAGE_INIT_TEXT
    assert "__version__ = \"0.1.0\"" not in PACKAGE_INIT_TEXT
    assert __version__ == pyproject_match.group(1)


def test_frozen_version_ignores_empty_upgrade_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    bundle = tmp_path / "_internal"
    (bundle / "fpvs_studio-1.3.0.dist-info" / "licenses").mkdir(parents=True)
    current = bundle / "fpvs_studio-1.4.0.dist-info"
    current.mkdir()
    (current / "METADATA").write_text("Name: fpvs-studio\nVersion: 1.4.0\n")
    package = bundle / "fpvs_studio"
    package.mkdir()
    init = package / "__init__.py"
    init.write_text(PACKAGE_INIT_TEXT, encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert runpy.run_path(str(init))["__version__"] == "1.4.0"

    from fpvs_studio.gui.packaged_smoke import _fpvs_studio_dist_info_names

    assert _fpvs_studio_dist_info_names() == [current.name]
    (bundle / "fpvs_studio-1.3.0.dist-info" / "METADATA").write_text(
        "Name: fpvs-studio\nVersion: 1.3.0\n"
    )
    with pytest.raises(RuntimeError, match="exactly one complete"):
        runpy.run_path(str(init))


@pytest.mark.parametrize(
    "metadata", [None, "Name: fpvs-studio\n", "Name: fpvs-studio\nVersion: invalid\n"]
)
def test_frozen_version_rejects_missing_or_invalid_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, metadata: str | None
) -> None:
    import sys

    from packaging.version import InvalidVersion

    bundle = tmp_path / "_internal"
    dist = bundle / "fpvs_studio-1.4.0.dist-info"
    dist.mkdir(parents=True)
    if metadata is not None:
        (dist / "METADATA").write_text(metadata)
    package = bundle / "fpvs_studio"
    package.mkdir()
    init = package / "__init__.py"
    init.write_text(PACKAGE_INIT_TEXT, encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    with pytest.raises((RuntimeError, InvalidVersion)):
        runpy.run_path(str(init))


def test_default_install_requires_pyside6_but_keeps_psychopy_optional() -> None:
    dependencies_block = _extract_list_assignment("dependencies").lower()
    dev_dependencies_block = _extract_list_assignment("dev").lower()
    packaging_dependencies_block = _extract_list_assignment("packaging").lower()
    assert "psychopy" not in dependencies_block
    assert "pyside6" in dependencies_block
    engine_dependencies_block = _extract_list_assignment("engine").lower()
    assert "psychopy" in engine_dependencies_block
    assert "sounddevice" in engine_dependencies_block
    assert "pytest-qt" in dev_dependencies_block
    assert "pytest-timeout" in dev_dependencies_block
    assert "pyinstaller" in packaging_dependencies_block


def test_pyinstaller_includes_psychopy_visual_lazy_imports() -> None:
    assert '_collect_submodules("psychopy.visual")' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.pygletbackend"' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.backends.glfwbackend"' in PYINSTALLER_SPEC_TEXT
    assert '"psychopy.visual.line"' in PYINSTALLER_SPEC_TEXT
    assert "Could not collect PyInstaller submodules" in PYINSTALLER_SPEC_TEXT
    assert "Could not copy PyInstaller package metadata" in PYINSTALLER_SPEC_TEXT


def test_pyinstaller_rejects_path_resolved_host_icu_dlls() -> None:
    assert "_is_host_icu_binary" in PYINSTALLER_SPEC_TEXT
    assert 'name == "icuuc.dll"' in PYINSTALLER_SPEC_TEXT
    assert 'name.startswith("icudt")' in PYINSTALLER_SPEC_TEXT
    assert "a.binaries = [" in PYINSTALLER_SPEC_TEXT


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_studio_spec_collects_secure_library_backend_for_linux_only(
    monkeypatch: pytest.MonkeyPatch, platform: str,
) -> None:
    hooks = ModuleType("PyInstaller.utils.hooks")
    developer_modules = [
        "fpvs_studio.developer",
        "fpvs_studio.developer.library_publisher",
        "fpvs_studio.developer.catalog_publisher",
        "fpvs_studio.developer.mode",
        "fpvs_studio.gui.library_publisher_controller",
        "fpvs_studio.gui.library_publisher_dialog",
    ]
    hooks.collect_submodules = (  # type: ignore[attr-defined]
        lambda package: [package, "fpvs_studio.library.client", *developer_modules]
        if package == "fpvs_studio" else [package]
    )
    hooks.collect_data_files = lambda package: []  # type: ignore[attr-defined]
    hooks.collect_dynamic_libs = lambda package: []  # type: ignore[attr-defined]
    hooks.copy_metadata = lambda package: [(package, "metadata")]  # type: ignore[attr-defined]
    for name, module in (
        ("PyInstaller", ModuleType("PyInstaller")),
        ("PyInstaller.utils", ModuleType("PyInstaller.utils")),
        ("PyInstaller.utils.hooks", hooks),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "platform", platform)

    def analysis(_entries: list[str], **kwargs: object) -> SimpleNamespace:
        if "hiddenimports" in kwargs:
            assert "fpvs_studio.developer" not in kwargs["excludes"]
            assert "fpvs_studio.gui.library_publisher_controller" not in kwargs["excludes"]
            assert "fpvs_studio.gui.library_publisher_dialog" not in kwargs["excludes"]
        return SimpleNamespace(pure=[], scripts=[], binaries=[], zipfiles=[], datas=kwargs["datas"])

    result = runpy.run_path(
        str(REPO_ROOT / "packaging" / "pyinstaller" / "fpvs_studio.spec"),
        init_globals={
            "SPECPATH": str(REPO_ROOT / "packaging" / "pyinstaller"),
            "Analysis": analysis,
            "PYZ": lambda pure: pure,
            "EXE": lambda *args, **kwargs: None,
            "COLLECT": lambda *args, **kwargs: None,
        },
    )
    assert ("keyring.backends.SecretService" in result["hiddenimports"]) == (platform == "linux")
    assert (("keyring", "metadata") in result["datas"]) == (platform == "linux")
    assert (("SecretStorage", "metadata") in result["datas"]) == (platform == "linux")
    assert "fpvs_studio.library.client" in result["hiddenimports"]
    assert set(developer_modules).issubset(result["hiddenimports"])


def test_bundled_open_sans_font_and_license_are_packaged_assets() -> None:
    font_path = bundled_task_font_path("Open Sans")

    assert font_path is not None and font_path.is_file()
    assert ImageFont.truetype(str(font_path), size=12).getname()[0] == "Open Sans"
    assert "SIL OPEN FONT LICENSE Version 1.1" in font_path.with_name(
        "OpenSans-OFL.txt"
    ).read_text(encoding="utf-8")
    assert '    "fpvs_studio",' in PYINSTALLER_SPEC_TEXT
    assert "datas += _collect_data(package)" in PYINSTALLER_SPEC_TEXT


def test_build_exe_fails_on_stale_installed_package_metadata() -> None:
    assert "Assert-PackageMetadataVersion" in BUILD_EXE_TEXT
    assert "Assert-BundledPackageMetadataVersion" in BUILD_EXE_TEXT
    assert "m.version('fpvs-studio')" in BUILD_EXE_TEXT
    assert "Package version drift before PyInstaller build" in BUILD_EXE_TEXT


def test_installer_reconciles_exact_owned_files_only_after_success() -> None:
    assert "[InstallDelete]" not in INNO_SCRIPT_TEXT
    assert "UninstallLogMode=append" in INNO_SCRIPT_TEXT
    assert "UninstallLogMode=overwrite" not in INNO_SCRIPT_TEXT
    assert "function PrepareToInstall" in INNO_SCRIPT_TEXT
    assert "Result := OwnedPrepareUpgrade" in INNO_SCRIPT_TEXT
    assert "if CurStep = ssPostInstall then" in INNO_SCRIPT_TEXT
    assert "OwnedReconcileAfterSuccess" in INNO_SCRIPT_TEXT
    assert 'DestName: "fpvs-owned-files-v1.txt"' in INNO_SCRIPT_TEXT
    assert "OwnedWritePending(Root, OwnedPreviousRecords)" in INNO_OWNERSHIP_TEXT
    assert "OwnedKeepPathRecords(Path, OwnedPreviousRecords, Remaining)" in INNO_OWNERSHIP_TEXT
    assert "GetSHA256OfStream(Stream)" in INNO_OWNERSHIP_TEXT
    assert "OwnedSetDisposition(Handle, 4, DeleteFlag, 1)" in INNO_OWNERSHIP_TEXT
    assert "Info.LinkCount <> 1" in INNO_OWNERSHIP_TEXT
    assert "OwnedOpenReparsePoint" in INNO_OWNERSHIP_TEXT
    assert "CreatedTemporary := True" in INNO_OWNERSHIP_TEXT
    assert "if CreatedTemporary then" in INNO_OWNERSHIP_TEXT
    assert "Nonfatal ownership-journal uninstall cleanup error" in INNO_SCRIPT_TEXT
    assert "Nonfatal update-cache uninstall cleanup error" in INNO_SCRIPT_TEXT
    assert "DelTree(" not in INNO_OWNERSHIP_TEXT
    assert "filesandordirs" not in INNO_SCRIPT_TEXT


def test_inno_runtime_constant_literals_are_known() -> None:
    # The compiler cannot validate names inside Pascal runtime strings.
    # Reviewed subset: https://jrsoftware.org/ishelp/topic_consts.htm
    known_constants = {
        "app", "localappdata", "userappdata", "userdocs", "userdesktop",
        "commonappdata", "commonpf", "commoncf", "win", "sys", "tmp",
    }
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((REPO_ROOT / "packaging" / "inno").glob("*.iss"))
    )
    templates = re.findall(
        r"ExpandConstant\s*\(\s*'((?:[^']|'')*)'\s*\)", source, re.IGNORECASE
    )
    assert templates, "No literal ExpandConstant calls were checked."
    names = {
        name.casefold()
        for template in templates
        for name in re.findall(r"\{([^{}]*)\}", template)
    }
    assert names, "No runtime constants were checked."
    assert names <= known_constants, f"Unreviewed Inno runtime constants: {names - known_constants}"


def test_inno_profile_root_lookup_is_noncreating_and_fails_closed() -> None:
    # Source guards, not a claim that native setup has been executed.
    root_guard = INNO_OWNERSHIP_TEXT.split("function OwnedSafeInstallRoot(", 1)[1].split(
        "function OwnedSafeRelativePath(", 1
    )[0]
    assert "OwnedCSIDLProfile = $0028;" in INNO_OWNERSHIP_TEXT
    lookup = re.search(
        r"Blocked\[0\] := RemoveBackslashUnlessRoot\(\s*"
        r"GetShellFolderByCSIDL\(OwnedCSIDLProfile, False\)\);",
        root_guard,
    )
    validation = re.search(
        r"if not OwnedLocalAbsolutePath\(Blocked\[0\]\) then\s+Exit;", root_guard
    )
    assert lookup is not None
    assert validation is not None
    assert root_guard.index("Result := False") < lookup.start() < validation.start()
    assert validation.end() < root_guard.index("for I := 0 to GetArrayLength(Blocked)")
    assert "SameText(Root, RemoveBackslashUnlessRoot(Blocked[I]))" in root_guard
    prepare = INNO_OWNERSHIP_TEXT.split("function OwnedPrepareUpgrade:", 1)[1].split(
        "function OwnedDeleteKnownFile(", 1
    )[0]
    assert prepare.index("OwnedSafeInstallRoot(Root)") < prepare.index("ExtractTemporaryFile(")
    assert prepare.index("OwnedSafeInstallRoot(Root)") < prepare.index("OwnedWritePending(")


def test_uninstall_cache_uses_backend_lock_and_strict_filename_matching() -> None:
    assert "if CurUninstallStep = usPostUninstall then" in INNO_SCRIPT_TEXT
    assert "UpdateCleanupCacheOnUninstall" in INNO_SCRIPT_TEXT
    assert r"{localappdata}\FPVS Studio\updates" in INNO_CACHE_TEXT
    assert ".fpvs-update.lock" in INNO_CACHE_TEXT
    assert "UpdateLockFile(LockHandle, 3, 0, 1, 0, Overlapped)" in INNO_CACHE_TEXT
    assert "OwnedShareRead or OwnedShareWrite" in INNO_CACHE_TEXT
    assert "Result := OwnedValidVersion(Version)" in INNO_CACHE_TEXT
    assert "UpdateHexUuid" in INNO_CACHE_TEXT
    assert "UpdateRemoveQuiescentCache(Root)" in INNO_CACHE_TEXT
    assert "OwnedReadAccess or OwnedDeleteAccess, 0, 0, OwnedOpenExisting" in INNO_CACHE_TEXT
    assert "DelTree(" not in INNO_CACHE_TEXT
    assert "RemoveDir(Root)" in INNO_CACHE_TEXT


def test_uninstall_helper_cache_reuses_pinned_lock_protocol_and_strict_names() -> None:
    helper_matcher = INNO_CACHE_TEXT.split("function UpdateHelperOwnedName(", 1)[1].split(
        "function UpdateOwnedPayloadName(", 1
    )[0]
    assert "Name <> Lowercase(Name)" in helper_matcher
    assert "Copy(Name, 1, 8) <> 'updater-'" in helper_matcher
    assert "Length(Stem) = 68" in helper_matcher
    assert "OwnedValidHash(Copy(Stem, 1, 64))" in helper_matcher
    assert "Length(Stem) = 37" in helper_matcher
    assert "UpdateHexUuid(Copy(Stem, 1, 32))" in helper_matcher
    assert "UpdateOwnedPayloadName(FindRec.Name, Helpers)" in INNO_CACHE_TEXT
    assert "UpdateDeleteCachePayload(Root, FindRec.Name, Helpers)" in INNO_CACHE_TEXT
    cleanup = INNO_CACHE_TEXT.split("procedure UpdateCleanupCacheOnUninstall;", 1)[1]
    assert r"ExpandConstant('{localappdata}\FPVS Studio\updates')), False)" in cleanup
    assert r"ExpandConstant('{localappdata}\FPVS Studio\updater-helper')), True)" in cleanup
    assert "UpdateRemoveQuiescentCache(RemoveBackslashUnlessRoot(" in cleanup
    assert r"ExpandConstant('{localappdata}\FPVS Studio\updater-install'))" in cleanup
    assert "FindFirst(" not in cleanup


def test_pending_journal_bounds_are_checked_before_temporary_creation() -> None:
    pending_writer = INNO_OWNERSHIP_TEXT.split("function OwnedWritePending(", 1)[1].split(
        "procedure OwnedBuildCurrentIndexes", 1
    )[0]
    assert re.search(
        r"if Records\.Count > OwnedMaxRecords then begin\s+Log\([^\n]+\);\s+Exit;\s+end;",
        pending_writer,
    )
    assert re.search(
        r"if Length\(Data\) > OwnedMaxManifestBytes then begin\s+Log\([^\n]+\);\s+Exit;\s+end;",
        pending_writer,
    )
    assert pending_writer.index("Result := False") < pending_writer.index(
        "if Records.Count > OwnedMaxRecords"
    ) < pending_writer.index("OwnedGuardDirectories")
    assert pending_writer.index("Data := Utf8Encode") < pending_writer.index(
        "if Length(Data) > OwnedMaxManifestBytes"
    ) < pending_writer.index("Temporary := GenerateUniqueName")
    assert pending_writer.index("Temporary := GenerateUniqueName") < pending_writer.index(
        "Handle := OwnedCreateFile(Temporary"
    )


def test_uninstall_installer_name_limit_matches_backend_basename_limit() -> None:
    installer_matcher = INNO_CACHE_TEXT.split("function UpdateInstallerName(", 1)[1].split(
        "function UpdateHexUuid", 1
    )[0]
    assert re.search(r"if Length\(Name\) > 200 then\s+Exit;", installer_matcher)
    assert installer_matcher.index("Result := False") < installer_matcher.index(
        "if Length(Name) > 200"
    ) < installer_matcher.index("LowerName := Lowercase(Name)")


def test_installer_build_validates_bundle_and_runs_packaged_smoke() -> None:
    assert "[switch]$SkipSmoke" in BUILD_INSTALLER_TEXT
    assert "Assert-BundleInput" in BUILD_INSTALLER_TEXT
    assert '$BundleInternalPath = Join-Path $BundleRoot "_internal"' in BUILD_INSTALLER_TEXT
    assert "Remove-PackagingOutput -RepoRoot $RepoRoot -TargetPath $InstallerOutputDir" in (
        BUILD_INSTALLER_TEXT
    )
    assert (
        'Get-ChildItem -Path $BundleInternalPath -Directory -Filter "fpvs_studio-*.dist-info"'
        in BUILD_INSTALLER_TEXT
    )
    assert "Running packaged app smoke check before installer build" in BUILD_INSTALLER_TEXT
    assert "Invoke-PackagedSmoke" in BUILD_INSTALLER_TEXT
    assert "build_installer_inventory.py" in BUILD_INSTALLER_TEXT
    assert "published-legacy-inventory.json" in BUILD_INSTALLER_TEXT
    assert '"--bundle-root"' in BUILD_INSTALLER_TEXT
    assert '"--legacy-inventory"' in BUILD_INSTALLER_TEXT
    assert '"/DOwnedInventoryRoot=$InventoryOutputDir"' in BUILD_INSTALLER_TEXT
    assert '"/DBundleRoot=$BundleRoot"' in BUILD_INSTALLER_TEXT
    assert "InstallLocation" in BUILD_INSTALLER_TEXT
    assert "$SmokePackagedAppScript" not in BUILD_RELEASE_TEXT


def test_release_wrapper_forwards_explicit_inno_compiler_path() -> None:
    assert "& $BuildInstallerScript -BuildLabel $BuildLabel -InnoCompiler $InnoCompiler" in (
        BUILD_RELEASE_TEXT
    )


def test_build_stages_share_safe_labeled_paths_before_resolving_python() -> None:
    for script in (BUILD_EXE_TEXT, BUILD_INSTALLER_TEXT):
        assert "[string]$BuildLabel" in script
        assert '. (Join-Path $PSScriptRoot "build_paths.ps1")' in script
        assert script.index("Get-PackagingBuildPaths") < script.index("Resolve-RepoPython")
        assert "Remove-Item" not in script
    assert '$bundleRoot = $BuildPaths.BundleRoot' in BUILD_EXE_TEXT
    assert '$exePath = Join-Path $BuildPaths.BundleRoot "FPVS Studio.exe"' in BUILD_EXE_TEXT
    assert re.search(r'"--workpath",\s+\$BuildPaths.WorkRoot', BUILD_EXE_TEXT)
    assert re.search(r'"--distpath",\s+\$BuildPaths.DistRoot', BUILD_EXE_TEXT)
    assert "$InstallerOutputDir = $BuildPaths.InstallerRoot" in BUILD_INSTALLER_TEXT
    assert "$InventoryOutputDir = $BuildPaths.InventoryRoot" in BUILD_INSTALLER_TEXT
    assert "& $BuildExeScript -SkipInstall -BuildLabel $BuildLabel" in BUILD_RELEASE_TEXT
    assert "& $BuildExeScript -BuildLabel $BuildLabel" in BUILD_RELEASE_TEXT
    assert "& $BuildInstallerScript -BuildLabel $BuildLabel" in BUILD_RELEASE_TEXT
    assert "-BaselineInventory $BaselineInventory" in BUILD_RELEASE_TEXT
    assert "-BaselineInventorySha256 $BaselineInventorySha256" in BUILD_RELEASE_TEXT
    assert "-SkipSmoke:$SkipSmoke -AllowVisibleGui:$AllowVisibleGui" in BUILD_RELEASE_TEXT
    assert "[System.IO.FileAttributes]::ReparsePoint" in BUILD_PATHS_TEXT
    assert "Remove-Item -LiteralPath $target -Recurse -Force" in BUILD_PATHS_TEXT
    assert BUILD_PATHS_TEXT.index("Get-ChildItem -LiteralPath $directory") < (
        BUILD_PATHS_TEXT.index("Remove-Item -LiteralPath $target")
    )


def _run_build_path_helper(root: Path, command: str, **variables: str) -> object:
    """Run only the path helper against fixtures, never a build/app/installer stage."""
    powershell = shutil.which("powershell.exe")
    if os.name != "nt" or powershell is None:
        pytest.skip("Windows PowerShell is required for native build-path fixtures")
    environment = dict(os.environ)
    environment.update(
        FPVS_BUILD_TEST_HELPER=str(REPO_ROOT / "scripts" / "build_paths.ps1"),
        FPVS_BUILD_TEST_ROOT=str(root),
        **variables,
    )
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "$ErrorActionPreference = 'Stop'; . $env:FPVS_BUILD_TEST_HELPER; " + command,
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_build_paths_keep_defaults_and_isolate_beta_outputs(tmp_path: Path) -> None:
    actual = _run_build_path_helper(
        tmp_path,
        "@(Get-PackagingBuildPaths -RepoRoot $env:FPVS_BUILD_TEST_ROOT; "
        "Get-PackagingBuildPaths -RepoRoot $env:FPVS_BUILD_TEST_ROOT "
        "-BuildLabel beta-1.3.1b1) | ConvertTo-Json -Compress",
    )
    for paths, label in zip(actual, ("", "beta-1.3.1b1"), strict=True):
        build = tmp_path / "build" / label
        dist = tmp_path / "dist" / label
        assert paths == {
            "WorkRoot": str(build / "pyinstaller"),
            "DistRoot": str(dist),
            "BundleRoot": str(dist / "FPVS Studio"),
            "InstallerRoot": str(dist / "installer"),
            "InventoryRoot": str(build / "installer-inventory"),
        }


def test_build_labels_reject_unsafe_and_reserved_components(tmp_path: Path) -> None:
    labels = [
        ".", "..", "../beta", r"..\beta", "beta/next", r"beta\next", r"C:\beta",
        "beta.", "beta ", " beta", "beta:test", "be ta", ".beta", "beta*", "beta?",
        "beta\n", "béta", "a" * 65, "CON", "con.txt", "PRN", "AUX", "NUL.tar",
        "COM1", "lpt9.txt", "CONIN$", "CONOUT$", "build", "dist", "pyinstaller",
        "INSTALLER", "installer-inventory",
    ]
    results = _run_build_path_helper(
        tmp_path,
        "$labels = ConvertFrom-Json $env:FPVS_BUILD_TEST_LABELS; "
        "@($labels | ForEach-Object { try { Assert-PackagingBuildLabel -BuildLabel $_; "
        "$false } catch { $true } }) | ConvertTo-Json -Compress",
        FPVS_BUILD_TEST_LABELS=json.dumps(labels),
    )
    assert results == [True] * len(labels)


def test_labeled_cleanup_preserves_other_output_and_unknown_sentinels(tmp_path: Path) -> None:
    removed = [
        tmp_path / "build" / "beta-1.3.1b1" / "pyinstaller",
        tmp_path / "dist" / "beta-1.3.1b1" / "FPVS Studio",
        tmp_path / "dist" / "beta-1.3.1b1" / "installer",
    ]
    preserved = [
        tmp_path / "build" / "pyinstaller",
        tmp_path / "dist" / "FPVS Studio",
        tmp_path / "dist" / "installer",
        tmp_path / "build" / "beta-1.3.1b1" / "installer-inventory",
        tmp_path / "dist" / "other-label" / "FPVS Studio",
    ]
    for directory in removed + preserved:
        directory.mkdir(parents=True)
        (directory / "sentinel.txt").write_text("fixture", encoding="utf-8")
    assert _run_build_path_helper(
        tmp_path,
        "$paths = Get-PackagingBuildPaths -RepoRoot $env:FPVS_BUILD_TEST_ROOT "
        "-BuildLabel beta-1.3.1b1; "
        "@($paths.WorkRoot, $paths.BundleRoot, $paths.InstallerRoot) | ForEach-Object { "
        "Remove-PackagingOutput -RepoRoot $env:FPVS_BUILD_TEST_ROOT -TargetPath $_ }; "
        "$true | ConvertTo-Json -Compress",
    )
    assert all(not path.exists() for path in removed)
    assert all(
        (path / "sentinel.txt").read_text(encoding="utf-8") == "fixture" for path in preserved
    )


def test_packaging_cleanup_rejects_broad_and_outside_paths(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    targets = [root, root / "build", root / "dist", tmp_path / "repo-other" / "build" / "x"]
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
        (target / "sentinel.txt").write_text("fixture", encoding="utf-8")
    labels = [str(path) for path in targets] + [str(root / "build") + "\\"]
    results = _run_build_path_helper(
        root,
        "$targets = ConvertFrom-Json $env:FPVS_BUILD_TEST_TARGETS; "
        "@($targets | ForEach-Object { try { Remove-PackagingOutput "
        "-RepoRoot $env:FPVS_BUILD_TEST_ROOT -TargetPath $_; $false } catch { $true } }) "
        "| ConvertTo-Json -Compress",
        FPVS_BUILD_TEST_TARGETS=json.dumps(labels),
    )
    assert results == [True] * len(labels)
    assert all((path / "sentinel.txt").is_file() for path in targets)


@pytest.mark.parametrize("nested", [False, True])
def test_packaging_cleanup_refuses_ancestor_and_nested_junctions(
    tmp_path: Path, nested: bool
) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction safety fixture")
    root = tmp_path / "repo"
    output = root / "dist" / "beta-1.3.1b1" / "FPVS Studio"
    destination = tmp_path / "outside-output"
    destination.mkdir()
    sentinel = destination / "sentinel.txt"
    sentinel.write_text("untouched", encoding="utf-8")
    junction = output / "nested-link" if nested else output.parent
    junction.parent.mkdir(parents=True)
    try:
        assert _run_build_path_helper(
            root,
            "New-Item -ItemType Junction -Path $env:FPVS_BUILD_TEST_LINK "
            "-Target $env:FPVS_BUILD_TEST_DESTINATION | Out-Null; "
            "$result = try { Remove-PackagingOutput -RepoRoot $env:FPVS_BUILD_TEST_ROOT "
            "-TargetPath $env:FPVS_BUILD_TEST_OUTPUT; $false } "
            "catch { $_.Exception.Message.Contains('reparse point') }; "
            "$result | ConvertTo-Json -Compress",
            FPVS_BUILD_TEST_LINK=str(junction),
            FPVS_BUILD_TEST_DESTINATION=str(destination),
            FPVS_BUILD_TEST_OUTPUT=str(output),
        )
        assert sentinel.read_text(encoding="utf-8") == "untouched"
        assert junction.is_dir()
    finally:
        if junction.exists():
            junction.rmdir()  # Remove only this fixture's junction, never its destination.


def test_release_icon_has_one_packaged_source() -> None:
    assert '"packaging" / "assets" / "fpvs-studio.ico"' not in PYINSTALLER_SPEC_TEXT
    assert '"fpvs_studio" / "assets" / "fpvs-studio.ico"' in PYINSTALLER_SPEC_TEXT
    assert r"SetupIconFile=..\..\src\fpvs_studio\assets\fpvs-studio.ico" in INNO_SCRIPT_TEXT


def test_packaged_smoke_checks_runtime_dependency_imports() -> None:
    assert "collect_packaged_smoke_report" in PACKAGED_SMOKE_TEXT
    assert "_isolate_psychopy_user_dirs" in GUI_PACKAGED_SMOKE_TEXT
    assert '"APPDATA"' in GUI_PACKAGED_SMOKE_TEXT
    assert '"LOCALAPPDATA"' in GUI_PACKAGED_SMOKE_TEXT
    assert "runtime_dependencies_ok" in GUI_PACKAGED_SMOKE_TEXT
    assert "runtime_dependency_report" in GUI_PACKAGED_SMOKE_TEXT
    assert '"psychopy.visual.backends.pygletbackend"' in GUI_PACKAGED_SMOKE_TEXT
    assert '"psychopy.visual.backends.glfwbackend"' in GUI_PACKAGED_SMOKE_TEXT
    assert '"psychtoolbox"' in GUI_PACKAGED_SMOKE_TEXT
    assert '"sounddevice"' in GUI_PACKAGED_SMOKE_TEXT


def _evaluate_updater_spec(monkeypatch: pytest.MonkeyPatch, modules: list[str]) -> dict:
    """Execute the spec graph checks with a simulated PyInstaller analysis, without Qt."""
    hooks = ModuleType("PyInstaller.utils.hooks")
    hooks.copy_metadata = lambda distribution: [(distribution, "metadata")]  # type: ignore[attr-defined]
    for name, module in (
        ("PyInstaller", ModuleType("PyInstaller")),
        ("PyInstaller.utils", ModuleType("PyInstaller.utils")),
        ("PyInstaller.utils.hooks", hooks),
    ):
        monkeypatch.setitem(sys.modules, name, module)
    calls: dict = {}

    def analysis(entries: list[str], **kwargs: object) -> SimpleNamespace:
        calls["analysis"] = (entries, kwargs)
        return SimpleNamespace(
            pure=[(name, "fixture.py", "PYMODULE") for name in modules],
            binaries=[
                ("python310.dll", "fixture", "BINARY"),
                ("icuuc.dll", "foreign", "BINARY"),
                ("icudt78.dll", "foreign", "BINARY"),
                ("PySide6/Qt6Core.dll", "fixture", "BINARY"),
            ],
            scripts=[
                ("pyi_rth_pyside6", "fixture", "PYSOURCE"),
                ("updater_main", "fixture", "PYSOURCE"),
            ],
            datas=kwargs["datas"],
        )

    def executable(*args: object, **kwargs: object) -> None:
        calls["exe"] = (args, kwargs)

    result = runpy.run_path(
        str(REPO_ROOT / "packaging" / "pyinstaller" / "fpvs_updater.spec"),
        init_globals={
            "SPECPATH": str(REPO_ROOT / "packaging" / "pyinstaller"),
            "Analysis": analysis,
            "PYZ": lambda pure: pure,
            "EXE": executable,
        },
    )
    return {"calls": calls, "result": result}


def test_updater_is_self_contained_windowed_and_keeps_a_narrow_dependency_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual = _evaluate_updater_spec(
        monkeypatch,
        ["fpvs_studio", "fpvs_studio.updates.models", "fpvs_studio.gui.updater_window"],
    )
    entries, analysis = actual["calls"]["analysis"]
    assert entries == [str(REPO_ROOT / "src" / "fpvs_studio" / "updater_main.py")]
    assert analysis["datas"][0] == ("fpvs-studio", "metadata")
    arguments, options = actual["calls"]["exe"]
    assert options["name"] == "FPVS Studio Updater"
    assert options["console"] is False
    assert options.get("exclude_binaries", False) is False
    assert arguments[2] == [
        ("python310.dll", "fixture", "BINARY"),
        ("PySide6/Qt6Core.dll", "fixture", "BINARY"),
    ]
    assert arguments[3] == analysis["datas"]
    assert arguments[1] == [("updater_main", "fixture", "PYSOURCE")]
    assert analysis["runtime_hooks"] == [
        str(REPO_ROOT / "packaging" / "pyinstaller" / "updater_qt_runtime.py")
    ]
    assert "coll" not in actual["result"]


@pytest.mark.parametrize(
    "module",
    ["psychopy.visual", "numpy", "fpvs_studio.runtime.preflight", "fpvs_studio.gui.controller"],
)
def test_updater_build_fails_when_it_collects_studio_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch, module: str
) -> None:
    with pytest.raises(RuntimeError, match="Updater collected Studio/runtime dependencies"):
        _evaluate_updater_spec(monkeypatch, ["fpvs_studio.updates.models", module])


def test_updater_runtime_hook_configures_qt_without_importing_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    for name in ("PATH", "QT_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        monkeypatch.setenv(name, "before-hook")
    loaded = set(sys.modules)
    runpy.run_path(str(REPO_ROOT / "packaging" / "pyinstaller" / "updater_qt_runtime.py"))
    assert os.environ["QT_PLUGIN_PATH"] == str(tmp_path / "PySide6" / "plugins")
    assert os.environ["QML2_IMPORT_PATH"] == str(tmp_path / "PySide6" / "qml")
    assert os.environ["PATH"] == str(tmp_path) + os.pathsep + "before-hook"
    assert not any(name.startswith("PySide6") for name in set(sys.modules) - loaded)


def test_installer_builds_and_checks_updater_before_final_ownership_inventory() -> None:
    script = (REPO_ROOT / "scripts" / "build_updater.ps1").read_text(encoding="utf-8")
    assert script.index("Get-PackagingBuildPaths") < script.index("Resolve-RepoPython")
    assert 'Join-Path $BuildPaths.BundleRoot "Updater"' in script
    assert '"pyinstaller-updater"' in script
    assert '"--packaging-check"' in script
    assert "-WindowStyle Hidden" in script
    assert "$report.version -ne $appVersion" in script
    assert "$report.frozen -ne $true" in script
    assert "$report.gui_loaded -ne $false" in script
    assert "$report.protocol_version -ne 1" in script
    assert "[switch]$AllowVisibleGui" in script
    assert '"--gui-smoke"' in script
    assert "$guiReport.passed -ne $true" in script
    assert "$guiReport.installer -ne $false" in script
    assert "$guiReport.network -ne $false" in script
    assert "$guiReport.standalone_repair -ne $true" in script
    assert "$guiReport.repair_after_failure -ne $true" in script
    assert "Remove-Item" not in script
    assert "bundle version does not match pyproject.toml" in BUILD_INSTALLER_TEXT
    assert BUILD_INSTALLER_TEXT.index("& $BuildUpdaterScript -BuildLabel $BuildLabel") < (
        BUILD_INSTALLER_TEXT.index("Invoke-Native -File $Python -Arguments @(")
    )
    assert 'Name: "{group}\\FPVS Studio Update & Repair"' in INNO_SCRIPT_TEXT
    assert "Check: UpdaterShortcutRequested" in INNO_SCRIPT_TEXT
    assert "Result := ShortcutsRequested and FileExists" in INNO_SCRIPT_TEXT
    assert "(Pos('/NOLAUNCH=1', Uppercase(GetCmdTail)) = 0)" in INNO_SCRIPT_TEXT
