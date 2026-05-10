# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the local FPVS Studio Windows developer build."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

repo_root = Path(SPECPATH).parents[1]
src_root = repo_root / "src"
entrypoint = src_root / "fpvs_studio" / "app" / "main.py"
app_icon = repo_root / "packaging" / "assets" / "fpvs-studio.ico"


def _collect_submodules(package_name: str) -> list[str]:
    try:
        return collect_submodules(package_name)
    except Exception as error:
        raise RuntimeError(
            f"Could not collect PyInstaller submodules for {package_name}."
        ) from error


def _collect_data(package_name: str) -> list[tuple[str, str]]:
    try:
        return collect_data_files(package_name)
    except Exception as error:
        raise RuntimeError(
            f"Could not collect PyInstaller data files for {package_name}."
        ) from error


def _collect_binaries(package_name: str) -> list[tuple[str, str]]:
    try:
        return collect_dynamic_libs(package_name)
    except Exception as error:
        raise RuntimeError(
            f"Could not collect PyInstaller dynamic libraries for {package_name}."
        ) from error


def _copy_metadata(distribution_name: str) -> list[tuple[str, str]]:
    try:
        return copy_metadata(distribution_name)
    except Exception as error:
        raise RuntimeError(
            f"Could not copy PyInstaller package metadata for {distribution_name}."
        ) from error


hiddenimports = []
hiddenimports += _collect_submodules("fpvs_studio")
hiddenimports += _collect_submodules("serial")
hiddenimports += _collect_submodules("psychopy.visual")
hiddenimports += [
    "psychopy",
    "psychopy.core",
    "psychopy.visual",
    "psychopy.visual.backends",
    "psychopy.visual.backends.glfwbackend",
    "psychopy.visual.line",
    "psychopy.visual.backends.pygletbackend",
    "psychopy.hardware",
    "psychopy.hardware.keyboard",
    "psychtoolbox",
    "pyglet",
    "sounddevice",
]

datas = []
for package in (
    "fpvs_studio",
    "psychopy",
    "psychtoolbox",
    "pyglet",
):
    datas += _collect_data(package)

for distribution in (
    "fpvs-studio",
    "psychopy",
    "psychtoolbox",
    "pyglet",
    "pyserial",
    "sounddevice",
    "Pillow",
    "numpy",
    "PySide6",
    "pydantic",
):
    datas += _copy_metadata(distribution)

binaries = []
for package in (
    "psychopy",
    "psychtoolbox",
    "sounddevice",
):
    binaries += _collect_binaries(package)

a = Analysis(
    [str(entrypoint)],
    pathex=[str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FPVS Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="FPVS Studio",
)
