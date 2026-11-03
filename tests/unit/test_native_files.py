"""Native macOS file adapters are lazy and never fall back to permanent deletion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from tests.platform_adapters import set_module_platform

from fpvs_studio.gui import native_files


def _native_modules(monkeypatch, *, trash_result=True, open_result=True, error=None):
    requested = []
    trashed = []
    opened = []

    def trash(url, resulting_url, error_pointer):
        assert resulting_url is None and error_pointer is None
        if error is not None:
            raise error
        trashed.append(url)
        return trash_result, None, None

    def open_url(url):
        if error is not None:
            raise error
        opened.append(url)
        return open_result

    foundation = SimpleNamespace(
        NSURL=SimpleNamespace(fileURLWithPath_=lambda path: ("file-url", path)),
        NSFileManager=SimpleNamespace(defaultManager=lambda: SimpleNamespace(
            trashItemAtURL_resultingItemURL_error_=trash,
        )),
    )
    appkit = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: SimpleNamespace(
        openURL_=open_url,
    )))

    def load(name):
        requested.append(name)
        return {"Foundation": foundation, "AppKit": appkit}[name]

    set_module_platform(monkeypatch, native_files, "darwin")
    monkeypatch.setattr(native_files.importlib, "import_module", load)
    return requested, trashed, opened


def test_trash_passes_one_literal_file_url_and_no_permanent_delete(monkeypatch, tmp_path):
    item = tmp_path / "Researcher's project; unicode Ω"
    item.mkdir()
    sentinel = item / "retain.txt"
    sentinel.write_text("Owned data", encoding="utf-8")
    requested, trashed, opened = _native_modules(monkeypatch)
    native_files.move_to_macos_trash(item)
    assert requested == ["Foundation"]
    assert trashed == [("file-url", str(item.absolute()))]
    assert opened == []
    # The fake OS did not move anything; the adapter must not delete it itself.
    assert sentinel.read_text(encoding="utf-8") == "Owned data"


@pytest.mark.parametrize("error", [None, RuntimeError("private native details")])
def test_trash_denied_or_unavailable_keeps_item_and_reports_failure(monkeypatch, tmp_path, error):
    item = tmp_path / "project"
    item.mkdir()
    _native_modules(monkeypatch, trash_result=False, error=error)
    with pytest.raises(OSError, match="Trash") as failure:
        native_files.move_to_macos_trash(item)
    assert item.is_dir()
    assert "private" not in str(failure.value)


def test_missing_cocoa_does_not_delete_or_launch_a_fallback(monkeypatch, tmp_path):
    item = tmp_path / "project"
    item.mkdir()
    set_module_platform(monkeypatch, native_files, "darwin")

    def missing(_name):
        raise ImportError("private framework loader state")

    monkeypatch.setattr(native_files.importlib, "import_module", missing)
    with pytest.raises(OSError, match="Cocoa support"):
        native_files.move_to_macos_trash(item)
    assert item.is_dir()


def test_finder_opens_only_directory_file_url(monkeypatch, tmp_path):
    requested, trashed, opened = _native_modules(monkeypatch)
    native_files.open_macos_folder(tmp_path)
    assert requested == ["Foundation", "AppKit"]
    assert opened == [("file-url", str(tmp_path.absolute()))]
    assert trashed == []


@pytest.mark.parametrize("error", [None, RuntimeError("private native details")])
def test_finder_failure_stays_explicit(monkeypatch, tmp_path, error):
    _native_modules(monkeypatch, open_result=False, error=error)
    with pytest.raises(OSError, match="Finder") as failure:
        native_files.open_macos_folder(tmp_path)
    assert "private" not in str(failure.value)


@pytest.mark.parametrize("operation", ["move_to_macos_trash", "open_macos_folder"])
def test_mac_helpers_never_import_or_call_native_modules_on_other_platforms(
    monkeypatch, tmp_path, operation,
):
    set_module_platform(monkeypatch, native_files, "win32")

    def forbidden(_name):
        raise AssertionError("Native imports are forbidden on this platform")

    monkeypatch.setattr(native_files.importlib, "import_module", forbidden)
    with pytest.raises(OSError, match="macOS"):
        getattr(native_files, operation)(tmp_path)


def test_trash_missing_item_and_root_are_rejected_before_native_access(monkeypatch, tmp_path):
    requested, _, _ = _native_modules(monkeypatch)
    with pytest.raises(FileNotFoundError):
        native_files.move_to_macos_trash(tmp_path / "missing")
    with pytest.raises(OSError, match="filesystem root"):
        native_files.move_to_macos_trash(type(tmp_path)(tmp_path.anchor))
    assert requested == []


def test_finder_missing_directory_is_rejected_before_native_access(monkeypatch, tmp_path):
    requested, _, _ = _native_modules(monkeypatch)
    with pytest.raises(NotADirectoryError):
        native_files.open_macos_folder(tmp_path / "missing")
    assert requested == []
