"""Optional grayscale stimulus preparation, independent of an open project."""

from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui import folder_actions
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
    mark_text_role,
)
from fpvs_studio.gui.window_helpers import _coerce_exception, _show_error_dialog
from fpvs_studio.gui.workers import ProgressSignalBridge, ProgressTask
from fpvs_studio.preprocessing.equalization import (
    TARGET_MEAN,
    FolderPair,
    ImageEqualizationCancelled,
    ImageEqualizationResult,
    equalize_image_folders,
)


class ImageEqualizerDialog(QDialog):
    """One folder table and one automatic batch action, with retained results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Image Equalizer")
        self.setMinimumSize(960, 640)
        self.resize(1120, 720)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self._pairs: list[FolderPair] = []
        self._active_task: ProgressTask | None = None
        self._result: ImageEqualizationResult | None = None
        self._terminal_received = False
        self._cancel = Event()
        self._progress = ProgressSignalBridge(self)
        self._progress.stage_changed.connect(self._on_progress)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        header = DialogHeader(
            "Image Equalizer",
            "Match grayscale brightness and contrast across all folders. Save new PNG copies.",
            parent=self,
        )
        self.summary_label = header.subtitle_label
        self.summary_label.setToolTip(
            "Matches whole-image mean intensity and RMS contrast using one automatic target. "
            "Resize or crop first. Monitor calibration is handled outside this tool. "
            "Color images become grayscale. Originals are preserved."
        )
        layout.addWidget(header)
        layout.addSpacing(8)

        self.folder_table = QTableWidget(0, 2, self)
        self.folder_table.setObjectName("image_equalizer_folder_pairs")
        self.folder_table.setAccessibleName("Input and output folder pairs")
        self.folder_table.setHorizontalHeaderLabels(["Input folder", "Output folder"])
        self.folder_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.folder_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        self.folder_table.verticalHeader().hide()
        self.folder_table.verticalHeader().setDefaultSectionSize(36)
        self.folder_table.setShowGrid(False)
        self.folder_table.setAlternatingRowColors(True)
        self.folder_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.folder_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.folder_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.folder_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.folder_table.setMinimumHeight(160)
        self.folder_table.itemSelectionChanged.connect(self._refresh_actions)
        self.folder_table.cellDoubleClicked.connect(self._edit_output_cell)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.add_button = QPushButton("Add Input Folder…", self)
        self.add_button.setToolTip(
            "Read images directly inside a folder; subfolders are skipped. "
            "Studio suggests a new output folder beside it."
        )
        self.add_button.clicked.connect(self._add_folder)
        self.output_button = QPushButton("Change Output…", self)
        self.output_button.clicked.connect(self._choose_output)
        self.remove_button = QPushButton("Remove Pair", self)
        self.remove_button.clicked.connect(self._remove_pair)
        self.open_button = QPushButton("Open Output", self)
        self.open_button.clicked.connect(self._open_output)
        for button in (self.add_button, self.output_button, self.remove_button, self.open_button):
            mark_secondary_action(button)
            if button is self.open_button:
                row.addStretch(1)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(self.folder_table, 1)
        self.status_label = QLabel("Add the folders you want to equalize together.", self)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        mark_text_role(self.status_label, "body")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setMinimumHeight(self.status_label.fontMetrics().lineSpacing() * 4)
        layout.addWidget(self.status_label)

        self.run_button = QPushButton("Equalize Images", self)
        self.run_button.clicked.connect(self._start)
        mark_primary_action(self.run_button)
        self.close_button = QPushButton("Close", self)
        self.close_button.clicked.connect(self.reject)
        mark_secondary_action(self.close_button)
        footer = QHBoxLayout()
        footer.addWidget(self.close_button)
        footer.addStretch(1)
        footer.addWidget(self.run_button)
        layout.addLayout(footer)
        focus_order = (
            self.add_button, self.output_button, self.remove_button, self.open_button,
            self.folder_table, self.close_button, self.run_button,
        )
        for first, second in zip(focus_order, focus_order[1:], strict=False):
            QWidget.setTabOrder(first, second)
        self.add_button.setFocus()
        apply_dialog_theme(self)
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        busy = self._active_task is not None
        selected = self.folder_table.currentRow() >= 0
        self.folder_table.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.output_button.setEnabled(not busy and selected)
        self.remove_button.setEnabled(not busy and selected)
        self.run_button.setEnabled(not busy and bool(self._pairs))
        self.close_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy and selected and self._result is not None)

    def _refresh_pairs(self) -> None:
        self._result = None
        self.status_label.setToolTip("")
        self.folder_table.setRowCount(len(self._pairs))
        for row, pair in enumerate(self._pairs):
            for column, path in enumerate((pair.input_dir, pair.output_dir)):
                text = str(path)
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
                self.folder_table.setItem(row, column, item)
        self.status_label.setText(
            "All folders will share one matching target. Output folders must be new or empty."
            if self._pairs else "Add the folders you want to equalize together."
        )
        self._refresh_actions()

    @Slot()
    def _add_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Add Input Image Folder")
        if not selected:
            return
        source = Path(selected)
        output = (source.with_name(f"{source.name}-equalized") if source.name
                  else source / "equalized")
        self._pairs.append(FolderPair(source, output))
        self._refresh_pairs()
        self.folder_table.selectRow(len(self._pairs) - 1)

    @Slot()
    def _choose_output(self) -> None:
        row = self.folder_table.currentRow()
        if row < 0:
            return
        pair = self._pairs[row]
        selected = QFileDialog.getExistingDirectory(
            self, "Choose Empty Output Folder", str(pair.output_dir.parent),
        )
        if selected:
            self._pairs[row] = FolderPair(pair.input_dir, Path(selected))
            self._refresh_pairs()
            self.folder_table.selectRow(row)

    @Slot(int, int)
    def _edit_output_cell(self, _row: int, column: int) -> None:
        if column == 1:
            self._choose_output()

    @Slot()
    def _remove_pair(self) -> None:
        row = self.folder_table.currentRow()
        if row >= 0:
            del self._pairs[row]
            self._refresh_pairs()

    @Slot()
    def _start(self) -> None:
        if self._active_task is not None or not self._pairs:
            return
        pairs = tuple(self._pairs)
        self._cancel = cancel = Event()
        progress = self._progress.stage_changed.emit
        self._result = None
        self.status_label.setToolTip("")
        task = ProgressTask(
            parent_widget=self,
            label="Analyzing and equalizing images…",
            callback=lambda: equalize_image_folders(
                pairs, cancel_flag=cancel.is_set, progress=progress,
            ),
            window_title="Image Equalizer",
            cancel_callback=cancel.set,
        )
        self._active_task = task
        self._terminal_received = False
        self.status_label.setText("Analyzing images…")
        self._refresh_actions()
        task.succeeded.connect(self._on_success)
        task.failed.connect(self._on_failure)
        task.finished.connect(self._on_finished)
        task.start()

    @Slot(str)
    def _on_progress(self, message: str) -> None:
        if self._active_task is not None:
            self.status_label.setText(message)

    @Slot(object)
    def _on_success(self, value: object) -> None:
        self._terminal_received = True
        if not isinstance(value, ImageEqualizationResult):
            self._on_failure(RuntimeError("Studio received an unexpected equalization result."))
            return
        self._result = value
        lines = [f"Saved {len(value.images)} grayscale PNGs across {len(value.reports)} folders."]
        lines.append("Matching statistics saved in image-equalizer-report.json in each folder.")
        if value.contrast_reduced:
            lines.append("Shared contrast was reduced to avoid clipping; see the report.")
        if value.skipped_files:
            lines.append(f"Skipped {len(value.skipped_files)} non-image files or subfolders.")
        self.status_label.setText("\n".join(lines))
        self.status_label.setToolTip(
            f"Target mean: {TARGET_MEAN:g} / 255. "
            f"Target RMS contrast: {value.target_standard_deviation / TARGET_MEAN:.6f}."
        )

    @Slot(object)
    def _on_failure(self, error: object) -> None:
        self._terminal_received = True
        if isinstance(error, ImageEqualizationCancelled):
            self.status_label.setText(str(error))
            return
        self.status_label.setText(
            "Batch failed. Review the error, adjust the folders and try again."
        )
        _show_error_dialog(self, "Image Equalizer Error", _coerce_exception(error))

    @Slot()
    def _on_finished(self) -> None:
        if not self._terminal_received:
            # Cancellation can arrive after the backend commits its report but
            # before ProgressTask delivers success. Do not claim rollback then.
            self.status_label.setText("Processing finished. Check outputs for a completed report.")
        self._active_task = None
        self._refresh_actions()

    @Slot()
    def _open_output(self) -> None:
        row = self.folder_table.currentRow()
        if self._result is not None and row >= 0:
            folder_actions.open_folder(self._pairs[row].output_dir)

    def reject(self) -> None:
        if self._active_task is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._active_task is not None:
            event.ignore()
        else:
            super().closeEvent(event)
