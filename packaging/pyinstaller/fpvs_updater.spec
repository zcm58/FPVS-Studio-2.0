# -*- mode: python ; coding: utf-8 -*-
"""Independent, one-file update and repair application; no Studio runtime bundle."""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

from PyInstaller.utils.hooks import copy_metadata

repo_root = Path(SPECPATH).parents[1]
src_root = repo_root / "src"
app_icon = src_root / "fpvs_studio" / "assets" / "fpvs-studio.ico"

# Do not collect all fpvs_studio submodules or package data: that would bring the
# experiment engine and its scientific dependencies into the repair application.
allowed_gui_modules = {
    "fpvs_studio.gui",
    "fpvs_studio.gui.updater_window",
    "fpvs_studio.gui.update_dialog",
    "fpvs_studio.gui.update_lifecycle",
    "fpvs_studio.gui.components",
    "fpvs_studio.gui.design_system",
}
forbidden_packages = (
    "fpvs_studio.app",
    "fpvs_studio.core",
    "fpvs_studio.engines",
    "fpvs_studio.preprocessing",
    "fpvs_studio.runtime",
    "fpvs_studio.triggers",
    "psychopy",
    "psychtoolbox",
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "sounddevice",
    "pyglet",
    "openpyxl",
    "PIL",
)

a = Analysis(
    [str(src_root / "fpvs_studio" / "updater_main.py")],
    pathex=[str(src_root)],
    binaries=[],
    datas=copy_metadata("fpvs-studio") + [(str(app_icon), "fpvs_studio/assets")],
    hiddenimports=["fpvs_studio.gui.updater_window"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(Path(SPECPATH) / "updater_qt_runtime.py")],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "numpy",
        # components exposes these unrelated authoring-page classes lazily;
        # updater surfaces use only its direct dialog/theme primitives.
        "fpvs_studio.gui.window_layout",
    ],
    noarchive=False,
)

# The standard Qt hook eagerly imports QtCore to register an embedded qt.conf.
# Our PyPI PySide6 wheel configures itself on GUI import; worker/check processes
# need only the environment paths from the custom, GUI-neutral runtime hook.
a.scripts = [script for script in a.scripts if script[0] != "pyi_rth_pyside6"]

unexpected = sorted(
    name
    for name, _source, _kind in a.pure
    if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden_packages)
    or (name.startswith("fpvs_studio.gui.") and name not in allowed_gui_modules)
)
if unexpected:
    raise RuntimeError("Updater collected Studio/runtime dependencies: " + ", ".join(unexpected))

# Match the main application's safeguard against unrelated ICU DLLs on host PATH.
a.binaries = [
    binary
    for binary in a.binaries
    if not (
        len(PureWindowsPath(binary[0]).parts) == 1
        and (
            PureWindowsPath(binary[0]).name.lower() == "icuuc.dll"
            or (
                PureWindowsPath(binary[0]).name.lower().startswith("icudt")
                and PureWindowsPath(binary[0]).name.lower().endswith(".dll")
            )
        )
    )
]
pyz = PYZ(a.pure)

# Onefile carries its own Python/Qt so it remains usable when Studio's _internal
# directory is damaged. A staged copy can replace the installed updater itself.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FPVS Studio Updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon),
)
