"""In-window image folder optimizer for FPVS-ready PNG stimuli."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from fpvs_studio.gui.components import (
    NonHomePageShell,
    PathValueLabel,
    SectionCard,
    StatusBadgeLabel,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.window_helpers import _show_error_dialog
from fpvs_studio.gui.workers import ProgressTask
from fpvs_studio.preprocessing.normalization import (
    ImageFolderOptimizationResult,
    optimize_image_folder_for_fpvs,
)


class ImageResizerPage(QWidget):
    """Standalone Studio-native image resizer page."""

    def __init__(
        self,
        *,
        on_return_home: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("image_resizer_page")
        self._on_return_home = on_return_home
        self._source_dir: Path | None = None
        self._output_dir: Path | None = None
        self._output_was_user_selected = False
        self._active_task: ProgressTask | None = None

        self.shell = NonHomePageShell(
            title="Image Resizer",
            subtitle="Optimize a folder of images into FPVS-ready square PNG copies.",
            width_preset="wide",
            parent=self,
        )

        setup_card = SectionCard(
            title="Optimize Images for FPVS",
            subtitle="Choose a source folder and Studio will create resized PNG copies.",
            object_name="image_resizer_setup_card",
            parent=self,
        )
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.source_value = PathValueLabel(setup_card)
        self.source_value.setObjectName("image_resizer_source_value")
        self.source_button = QPushButton("Choose Source Folder", setup_card)
        self.source_button.setObjectName("image_resizer_source_button")
        self.source_button.clicked.connect(self._choose_source_folder)
        mark_secondary_action(self.source_button)
        form.addRow("Source folder", _path_picker_row(self.source_value, self.source_button))

        self.output_value = PathValueLabel(setup_card)
        self.output_value.setObjectName("image_resizer_output_value")
        self.output_button = QPushButton("Choose Output Folder", setup_card)
        self.output_button.setObjectName("image_resizer_output_button")
        self.output_button.clicked.connect(self._choose_output_folder)
        mark_secondary_action(self.output_button)
        form.addRow("Output folder", _path_picker_row(self.output_value, self.output_button))

        self.size_combo = QComboBox(setup_card)
        self.size_combo.setObjectName("image_resizer_size_combo")
        self.size_combo.addItem("512 x 512", userData=512)
        self.size_combo.addItem("256 x 256", userData=256)
        self.size_combo.addItem("1024 x 1024", userData=1024)
        form.addRow("Output size", self.size_combo)
        setup_card.body_layout.addLayout(form)

        self.optimize_button = QPushButton("Optimize Images for FPVS", setup_card)
        self.optimize_button.setObjectName("image_resizer_optimize_button")
        self.optimize_button.clicked.connect(self._start_optimization)
        mark_primary_action(self.optimize_button)
        self.return_home_button = QPushButton("Return Home", setup_card)
        self.return_home_button.setObjectName("image_resizer_return_home_button")
        self.return_home_button.clicked.connect(self._return_home)
        mark_secondary_action(self.return_home_button)
        button_row = QHBoxLayout()
        button_row.addWidget(self.return_home_button)
        button_row.addStretch(1)
        button_row.addWidget(self.optimize_button)
        setup_card.body_layout.addLayout(button_row)

        result_card = SectionCard(
            title="Results",
            subtitle="Optimization results appear here after the batch finishes.",
            object_name="image_resizer_result_card",
            parent=self,
        )
        self.status_badge = StatusBadgeLabel(parent=result_card)
        self.status_badge.setObjectName("image_resizer_status_badge")
        self.status_badge.set_state("pending", "Choose source and output folders")
        self.result_label = QLabel("No images optimized yet.", result_card)
        self.result_label.setObjectName("image_resizer_result_label")
        self.result_label.setWordWrap(True)
        result_card.body_layout.addWidget(self.status_badge)
        result_card.body_layout.addWidget(self.result_label)

        self.shell.add_content_widget(setup_card)
        self.shell.add_content_widget(result_card)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)
        self._refresh_paths()
        self._refresh_enabled_state()

    @Slot()
    def _return_home(self) -> None:
        if self._on_return_home is not None:
            self._on_return_home()

    @Slot()
    def _choose_source_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Source Image Folder",
            str(self._source_dir or Path.home()),
        )
        if not directory:
            return
        self._set_source_dir(Path(directory))

    @Slot()
    def _choose_output_folder(self) -> None:
        start_dir = self._output_dir or self._suggested_output_dir() or Path.home()
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Output Folder",
            str(start_dir),
        )
        if not directory:
            return
        self._set_output_dir(Path(directory), user_selected=True)

    def _set_source_dir(self, source_dir: Path) -> None:
        self._source_dir = source_dir
        if not self._output_was_user_selected:
            suggested_output = self._suggested_output_dir()
            if suggested_output is not None:
                self._set_output_dir(suggested_output, user_selected=False)
        self._refresh_paths()
        self._refresh_enabled_state()

    def _set_output_dir(self, output_dir: Path, *, user_selected: bool) -> None:
        self._output_dir = output_dir
        if user_selected:
            self._output_was_user_selected = True
        self._refresh_paths()
        self._refresh_enabled_state()

    def _suggested_output_dir(self) -> Path | None:
        if self._source_dir is None:
            return None
        folder_name = self._source_dir.name or "fpvs-optimized-images"
        if self._source_dir.parent == self._source_dir:
            return self._source_dir / "fpvs-optimized-images"
        return self._source_dir.parent / f"{folder_name}-fpvs-optimized"

    def _refresh_paths(self) -> None:
        source_text = str(self._source_dir) if self._source_dir is not None else "Not selected"
        output_text = str(self._output_dir) if self._output_dir is not None else "Not selected"
        self.source_value.set_path_text(source_text, max_length=82)
        self.output_value.set_path_text(output_text, max_length=82)

    def _refresh_enabled_state(self) -> None:
        self.optimize_button.setEnabled(self._can_optimize())

    def _can_optimize(self) -> bool:
        if self._source_dir is None or self._output_dir is None:
            return False
        if not self._source_dir.exists() or not self._source_dir.is_dir():
            return False
        return self._source_dir.resolve() != self._output_dir.resolve(strict=False)

    @Slot()
    def _start_optimization(self) -> None:
        if self._source_dir is None or self._output_dir is None:
            return
        target_size = int(self.size_combo.currentData() or 512)
        source_dir = self._source_dir
        output_dir = self._output_dir
        task = ProgressTask(
            parent_widget=self,
            label="Optimizing images for FPVS...",
            callback=lambda: optimize_image_folder_for_fpvs(
                input_dir=source_dir,
                output_dir=output_dir,
                target_size=target_size,
            ),
            window_title="Optimizing Images",
        )
        self._active_task = task
        self.optimize_button.setEnabled(False)
        self.status_badge.set_state("info", "Optimizing images")
        task.succeeded.connect(self._on_optimization_succeeded)
        task.failed.connect(self._on_optimization_failed)
        task.finished.connect(self._on_optimization_finished)
        task.start()

    @Slot(object)
    def _on_optimization_succeeded(self, result: object) -> None:
        if not isinstance(result, ImageFolderOptimizationResult):
            self.status_badge.set_state("error", "Optimization failed")
            self.result_label.setText("Studio received an unexpected optimizer result.")
            return
        if result.failed_files:
            self.status_badge.set_state("warning", "Optimization finished with failures")
        else:
            self.status_badge.set_state("ready", "Optimization complete")
        self.result_label.setText(_format_result(result))

    @Slot(object)
    def _on_optimization_failed(self, error: object) -> None:
        exception = error if isinstance(error, Exception) else RuntimeError(str(error))
        self.status_badge.set_state("error", "Optimization failed")
        self.result_label.setText("No output paths were changed.")
        _show_error_dialog(self, "Image Resizer Error", exception)

    @Slot()
    def _on_optimization_finished(self) -> None:
        self._active_task = None
        self._refresh_enabled_state()


def _path_picker_row(path_label: PathValueLabel, button: QPushButton) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)
    layout.addWidget(path_label, 1)
    layout.addWidget(button)
    return row


def _format_result(result: ImageFolderOptimizationResult) -> str:
    parts = [
        (
            f"Optimized {result.processed_count} image(s) to "
            f"{result.target_size} x {result.target_size} PNG."
        ),
        f"Output folder: {result.output_dir}",
    ]
    if result.skipped_files:
        parts.append(f"Skipped {len(result.skipped_files)} file(s).")
    if result.failed_files:
        parts.append(f"Failed {len(result.failed_files)} file(s).")
    return "\n".join(parts)
