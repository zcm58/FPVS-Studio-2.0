"""Registered visible Qt coverage; safe tiers do not import this module."""

import json
from hashlib import sha256
from pathlib import Path
from threading import Event

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea
from tests.gui.helpers import (
    ImmediateProgressTask,
    assert_visible_children_within_parent,
    open_created_project,
)

from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.gui import image_equalizer_dialog as gui
from fpvs_studio.gui.packaged_smoke import _verification_palette
from fpvs_studio.gui.update_lifecycle import update_lifecycle
from fpvs_studio.preprocessing import equalization
from fpvs_studio.preprocessing.equalization import FolderPair, ImageEqualizationCancelled


def _source(root: Path, name: str) -> Path:
    source = root / name
    source.mkdir()
    Image.fromarray(np.tile(np.arange(32, 224, dtype=np.uint8), (24, 1))).save(
        source / "stimulus.png",
    )
    return source


@pytest.fixture
def live_dialog(qtbot, qapp):
    original_auto_quit = qapp.quitOnLastWindowClosed()
    qapp.setQuitOnLastWindowClosed(False)
    dialog = gui.ImageEqualizerDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    yield dialog
    dialog._cancel.set()
    qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
    qtbot.waitUntil(lambda: not update_lifecycle().has_active_jobs, timeout=10000)
    qapp.setQuitOnLastWindowClosed(original_auto_quit)


@pytest.mark.parametrize("cancel_first", [False, True])
def test_real_worker_batch_and_cancel_rollback(qtbot, live_dialog, tmp_path, monkeypatch,
                                             cancel_first):
    dialog = live_dialog
    sources = [_source(tmp_path, "base"), _source(tmp_path, "oddball")]
    for source in sources:
        Image.fromarray(np.tile(np.arange(40, 160, dtype=np.uint8), (48, 1))).save(
            source / "second.png",
        )
    outputs = [tmp_path / "base-equalized", tmp_path / "oddball-equalized"]
    dialog._pairs = [FolderPair(source, output)
                     for source, output in zip(sources, outputs, strict=True)]
    dialog._refresh_pairs()
    original_hashes = {path: sha256(path.read_bytes()).hexdigest()
                       for source in sources for path in source.iterdir()}
    if cancel_first:
        entered, release = Event(), Event()
        read_grayscale = equalization._read_grayscale
        output_paths = {filesystem_path(output) for output in outputs}

        def pause_after_write(path):
            if path.parent in output_paths:
                entered.set()
                assert release.wait(5), "Cancellation must reach the real worker"
            return read_grayscale(path)

        monkeypatch.setattr(equalization, "_read_grayscale", pause_after_write)
        try:
            qtbot.mouseClick(dialog.run_button, Qt.MouseButton.LeftButton)
            qtbot.waitUntil(entered.is_set, timeout=5000)
            assert not dialog.close_button.isEnabled()
            task = dialog._active_task
            cancel_button = task._dialog.findChild(QPushButton)
            assert cancel_button.text() == "Cancel"
            qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
            assert dialog._cancel.is_set()
        finally:
            release.set()
        qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
        assert "cancelled" in dialog.status_label.text().lower()
        assert all(output.is_dir() and not list(output.iterdir()) for output in outputs)
        assert dialog.run_button.isEnabled()
        monkeypatch.setattr(equalization, "_read_grayscale", read_grayscale)

    qtbot.mouseClick(dialog.run_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog._active_task is None, timeout=10000)
    assert dialog._result is not None
    assert "Saved 4 grayscale PNGs across 2 folders" in dialog.status_label.text()
    targets = []
    for output in outputs:
        report = json.loads((output / equalization.REPORT_NAME).read_text(encoding="utf-8"))
        targets.append(report["target_standard_deviation"])
        assert len(list(output.glob("*.png"))) == 2
        for path in output.glob("*.png"):
            with Image.open(path) as image:
                assert image.mode == "L"
                pixels = np.asarray(image, dtype=np.float64)
            assert abs(pixels.mean() - equalization.TARGET_MEAN) <= 0.501
            assert abs(pixels.std() - targets[-1]) <= 0.501
    assert targets[0] == targets[1]
    assert {path: sha256(path.read_bytes()).hexdigest() for path in original_hashes} == (
        original_hashes
    )


@pytest.mark.parametrize("size", [(960, 640), (1120, 720)])
@pytest.mark.parametrize("dark", [False, True])
def test_states_fit_with_long_accessible_paths(qtbot, qapp, size, dark, monkeypatch, request):
    original_palette = qapp.palette()
    request.addfinalizer(lambda: qapp.setPalette(original_palette))
    qapp.setPalette(_verification_palette(dark=dark))
    dialog = gui.ImageEqualizerDialog()
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    assert not dialog.run_button.isEnabled()
    long_path = Path("C:/Research/" + "Long experiment folder name/" * 10 + "Base")
    dialog._pairs = [
        FolderPair(long_path, long_path.parent / "Equalized"),
        FolderPair(long_path.parent / "Oddball", long_path.parent / "Oddball-equalized"),
    ]
    dialog._refresh_pairs()
    dialog.folder_table.selectRow(0)
    monkeypatch.setattr(gui, "_show_error_dialog", lambda *args: None)
    for state in ("ready", "busy", "failed", "cancelled", "success"):
        if state == "busy":
            dialog._active_task = object()
            dialog._on_progress("Analyzed 9999 of 10000 images…")
        else:
            dialog._active_task = None
            if state == "failed":
                dialog._on_failure(ValueError(str(long_path)))
            elif state == "cancelled":
                dialog._on_failure(ImageEqualizationCancelled("Cancelled. No outputs retained."))
            elif state == "success":
                dialog._on_success(gui.ImageEqualizationResult(
                    (), (long_path,), 10, 20, (long_path,), 2,
                ))
        dialog._refresh_actions()
        QApplication.processEvents()
        assert dialog.size().toTuple() == size
        assert_visible_children_within_parent(dialog)
        assert not dialog.findChildren(QScrollArea)
        table = dialog.folder_table
        assert table.x() == dialog.add_button.x() == dialog.status_label.x()
        assert dialog.add_button.geometry().bottom() < table.y()
        assert table.geometry().bottom() < dialog.status_label.y()
        assert table.width() == dialog.width() - 48
        for button in dialog.findChildren(QPushButton):
            if button.isVisible():
                assert button.contentsRect().width() >= button.fontMetrics().horizontalAdvance(
                    button.text(),
                )
        label = dialog.status_label
        assert label.height() >= label.heightForWidth(label.width())
        assert dialog.summary_label.height() >= dialog.summary_label.heightForWidth(
            dialog.summary_label.width(),
        )
        assert dialog.folder_table.item(0, 0).toolTip() == str(long_path)
        assert dialog.folder_table.item(0, 0).data(Qt.ItemDataRole.AccessibleTextRole) == str(
            long_path,
        )


def test_folder_dialog_cancel_edit_remove_and_batch(qtbot, tmp_path, monkeypatch):
    dialog = gui.ImageEqualizerDialog()
    qtbot.addWidget(dialog)
    first, second = _source(tmp_path, "base"), _source(tmp_path, "odd")
    selections = iter(["", str(first), str(second), "", str(tmp_path / "chosen")])
    monkeypatch.setattr(gui.QFileDialog, "getExistingDirectory", lambda *args: next(selections))
    dialog._add_folder()
    assert dialog._pairs == []
    dialog._add_folder()
    dialog._add_folder()
    assert len(dialog._pairs) == 2
    assert dialog._pairs[0].output_dir.name == "base-equalized"
    original = tuple(dialog._pairs)
    dialog._choose_output()
    assert tuple(dialog._pairs) == original
    dialog._choose_output()
    assert dialog._pairs[1].output_dir == tmp_path / "chosen"
    monkeypatch.setattr(gui, "ProgressTask", ImmediateProgressTask)
    dialog._start()
    assert dialog._active_task is None
    assert dialog._result is not None
    assert len(dialog._result.images) == 2
    assert "Saved 2 grayscale PNGs" in dialog.status_label.text()
    assert dialog.open_button.isEnabled()
    dialog._remove_pair()
    assert len(dialog._pairs) == 1
    assert dialog._result is None
    assert not dialog.open_button.isEnabled()


def test_busy_lifetime_cancel_and_failure_recovery(qtbot, tmp_path, monkeypatch):
    class HeldTask(ImmediateProgressTask):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.cancel_callback = kwargs["cancel_callback"]

        def start(self):
            pass

    dialog = gui.ImageEqualizerDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    source = _source(tmp_path, "input")
    dialog._pairs = [FolderPair(source, tmp_path / "output")]
    dialog._refresh_pairs()
    monkeypatch.setattr(gui, "ProgressTask", HeldTask)
    dialog._start()
    task = dialog._active_task
    assert task is not None
    assert not dialog.add_button.isEnabled()
    assert not dialog.run_button.isEnabled()
    dialog.reject()
    dialog.close()
    assert dialog.isVisible()
    task.cancel_callback()
    assert dialog._cancel.is_set()
    task.failed.emit(ImageEqualizationCancelled("Cancelled. No outputs retained."))
    task.finished.emit()
    assert dialog.run_button.isEnabled()
    assert "Cancelled" in dialog.status_label.text()
    errors = []
    monkeypatch.setattr(gui, "_show_error_dialog", lambda *args: errors.append(args))
    dialog._start()
    dialog._active_task.failed.emit(ValueError("Choose an empty output folder."))
    dialog._active_task.finished.emit()
    assert errors
    assert "Batch failed" in dialog.status_label.text()
    assert dialog._pairs[0].input_dir == source


def test_project_tools_menu_opens_image_equalizer(qtbot, controller, tmp_path):
    _, window = open_created_project(controller, qtbot, tmp_path, "Equalizer Menu")
    assert window.image_equalizer_action in window.tools_menu.actions()
    assert window._image_equalizer_dialog is None
    window.image_equalizer_action.trigger()
    assert window._image_equalizer_dialog.isVisible()
    window._image_equalizer_dialog.close()
    qtbot.waitUntil(lambda: not controller._update_lifecycle.has_active_jobs, timeout=15000)
