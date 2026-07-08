"""In-window image folder optimizer for FPVS-ready PNG stimuli."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui import folder_actions
from fpvs_studio.gui.components import (
    NonHomePageShell,
    PathValueLabel,
    StatusBadgeLabel,
    apply_image_resizer_theme,
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
        self._successful_output_dir: Path | None = None
        self._active_task: ProgressTask | None = None

        self.shell = NonHomePageShell(
            title="Image Resizer",
            subtitle="Optimize a folder of images into FPVS-ready square PNG copies.",
            width_preset="full",
            parent=self,
        )

        workbench = QWidget(self)
        workbench.setObjectName("image_resizer_workbench")
        workbench_layout = QHBoxLayout(workbench)
        workbench_layout.setContentsMargins(16, 8, 16, 8)
        workbench_layout.setSpacing(22)

        controls_panel = QWidget(workbench)
        controls_panel.setObjectName("image_resizer_controls_panel")
        controls_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)
        controls_heading = QLabel("Optimize Images for FPVS", controls_panel)
        controls_heading.setObjectName("image_resizer_controls_heading")
        controls_intro = QLabel(
            "Choose a source folder and Studio will create resized PNG copies.",
            controls_panel,
        )
        controls_intro.setObjectName("image_resizer_controls_copy")
        controls_intro.setWordWrap(True)
        controls_layout.addWidget(controls_heading)
        controls_layout.addWidget(controls_intro)

        form = QGridLayout()
        form.setContentsMargins(0, 10, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(12)
        form.setColumnStretch(0, 0)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 0)

        self.source_value = PathValueLabel(controls_panel)
        self.source_value.setObjectName("image_resizer_source_value")
        self.source_button = QPushButton("Choose Source Folder", controls_panel)
        self.source_button.setObjectName("image_resizer_source_button")
        self.source_button.clicked.connect(self._choose_source_folder)
        mark_secondary_action(self.source_button)
        _add_field_row(
            form,
            0,
            "Source folder",
            self.source_value,
            self.source_button,
            controls_panel,
        )

        self.output_value = PathValueLabel(controls_panel)
        self.output_value.setObjectName("image_resizer_output_value")
        self.output_button = QPushButton("Choose Output Folder", controls_panel)
        self.output_button.setObjectName("image_resizer_output_button")
        self.output_button.clicked.connect(self._choose_output_folder)
        mark_secondary_action(self.output_button)
        _add_field_row(
            form,
            1,
            "Output folder",
            self.output_value,
            self.output_button,
            controls_panel,
        )

        self.size_combo = QComboBox(controls_panel)
        self.size_combo.setObjectName("image_resizer_size_combo")
        self.size_combo.addItem("512 x 512", userData=512)
        self.size_combo.addItem("256 x 256", userData=256)
        self.size_combo.addItem("1024 x 1024", userData=1024)
        size_label = _field_label("Output size", controls_panel)
        form.addWidget(size_label, 2, 0)
        form.addWidget(self.size_combo, 2, 1, 1, 2)
        controls_layout.addLayout(form)

        self.optimize_button = QPushButton("Optimize Images for FPVS", controls_panel)
        self.optimize_button.setObjectName("image_resizer_optimize_button")
        self.optimize_button.clicked.connect(self._start_optimization)
        mark_primary_action(self.optimize_button)
        self.return_home_button = QPushButton("Return Home", controls_panel)
        self.return_home_button.setObjectName("image_resizer_return_home_button")
        self.return_home_button.clicked.connect(self._return_home)
        mark_secondary_action(self.return_home_button)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 8, 0, 0)
        button_row.addWidget(self.return_home_button)
        button_row.addStretch(1)
        button_row.addWidget(self.optimize_button)
        controls_layout.addLayout(button_row)
        controls_layout.addStretch(1)

        separator = QFrame(workbench)
        separator.setObjectName("image_resizer_column_separator")
        separator.setFrameShape(QFrame.Shape.VLine)

        results_panel = QWidget(workbench)
        results_panel.setObjectName("image_resizer_results_panel")
        results_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.setSpacing(12)
        results_heading = QLabel("Results", results_panel)
        results_heading.setObjectName("image_resizer_results_heading")
        results_intro = QLabel(
            "Optimization results appear here after the batch finishes.",
            results_panel,
        )
        results_intro.setObjectName("image_resizer_results_copy")
        results_intro.setWordWrap(True)
        results_layout.addWidget(results_heading)
        results_layout.addWidget(results_intro)

        self.status_badge = StatusBadgeLabel(parent=results_panel)
        self.status_badge.setObjectName("image_resizer_status_badge")
        self.status_badge.set_state("pending", "Choose source and output folders")
        self.result_label = QLabel("No images optimized yet.", results_panel)
        self.result_label.setObjectName("image_resizer_result_label")
        self.result_label.setWordWrap(True)
        results_layout.addWidget(self.status_badge)
        results_layout.addWidget(self.result_label)
        results_layout.addStretch(1)
        self.open_output_button = QPushButton("Open Output Folder", results_panel)
        self.open_output_button.setObjectName("image_resizer_open_output_button")
        self.open_output_button.clicked.connect(self._open_output_folder)
        mark_secondary_action(self.open_output_button)
        self.copy_output_button = QPushButton("Copy Output Folder", results_panel)
        self.copy_output_button.setObjectName("image_resizer_copy_output_button")
        self.copy_output_button.clicked.connect(self._copy_output_folder)
        mark_secondary_action(self.copy_output_button)
        result_action_row = QHBoxLayout()
        result_action_row.setContentsMargins(0, 0, 0, 0)
        result_action_row.addStretch(1)
        result_action_row.addWidget(self.open_output_button)
        result_action_row.addWidget(self.copy_output_button)
        results_layout.addLayout(result_action_row)

        workbench_layout.addWidget(controls_panel, 3)
        workbench_layout.addWidget(separator)
        workbench_layout.addWidget(results_panel, 2)
        self.shell.add_content_widget(workbench, stretch=1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)
        apply_image_resizer_theme(self)
        self._refresh_paths()
        self._refresh_output_actions()
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
        self._successful_output_dir = None
        if not self._output_was_user_selected:
            suggested_output = self._suggested_output_dir()
            if suggested_output is not None:
                self._set_output_dir(suggested_output, user_selected=False)
        self._refresh_paths()
        self._refresh_enabled_state()

    def _set_output_dir(self, output_dir: Path, *, user_selected: bool) -> None:
        self._output_dir = output_dir
        self._successful_output_dir = None
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
        self.source_value.set_path_text(source_text, max_length=118)
        self.output_value.set_path_text(output_text, max_length=118)

    def _refresh_enabled_state(self) -> None:
        reason = self._disabled_reason()
        self.optimize_button.setEnabled(reason is None)
        if self._active_task is not None or self._successful_output_dir is not None:
            return
        if reason is None:
            self.status_badge.set_state("ready", "Ready to optimize")
            self.result_label.setText("Ready to optimize the selected source folder.")
        else:
            self.status_badge.set_state("pending", "Optimize unavailable")
            self.result_label.setText(reason)

    def _can_optimize(self) -> bool:
        return self._disabled_reason() is None

    def _disabled_reason(self) -> str | None:
        if self._source_dir is None or self._output_dir is None:
            return "Select a source folder and an output folder to optimize images."
        if not self._source_dir.exists():
            return "The selected source folder no longer exists."
        if not self._source_dir.is_dir():
            return "The selected source path is not a folder."
        if self._source_dir.resolve() == self._output_dir.resolve(strict=False):
            return "The output folder must be different from the source folder."
        return None

    def _refresh_output_actions(self) -> None:
        has_output = self._successful_output_dir is not None
        self.open_output_button.setEnabled(has_output)
        self.copy_output_button.setEnabled(has_output)
        self.open_output_button.setVisible(has_output)
        self.copy_output_button.setVisible(has_output)

    @Slot()
    def _start_optimization(self) -> None:
        if self._source_dir is None or self._output_dir is None:
            return
        self._successful_output_dir = None
        self._refresh_output_actions()
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
            self._successful_output_dir = None
            self._refresh_output_actions()
            return
        self._successful_output_dir = result.output_dir
        if result.failed_files:
            self.status_badge.set_state("warning", "Optimization finished with failures")
        else:
            self.status_badge.set_state("ready", "Optimization complete")
        self.result_label.setText(_format_result(result))
        self._refresh_output_actions()

    @Slot(object)
    def _on_optimization_failed(self, error: object) -> None:
        exception = error if isinstance(error, Exception) else RuntimeError(str(error))
        self.status_badge.set_state("error", "Optimization failed")
        self.result_label.setText("No output paths were changed.")
        self._successful_output_dir = None
        self._refresh_output_actions()
        _show_error_dialog(self, "Image Resizer Error", exception)

    @Slot()
    def _on_optimization_finished(self) -> None:
        self._active_task = None
        self._refresh_enabled_state()

    @Slot()
    def _open_output_folder(self) -> None:
        if self._successful_output_dir is not None:
            folder_actions.open_folder(self._successful_output_dir)

    @Slot()
    def _copy_output_folder(self) -> None:
        if self._successful_output_dir is not None:
            QApplication.clipboard().setText(str(self._successful_output_dir))


def _field_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("imageResizerFieldLabel", "true")
    return label


def _add_field_row(
    form: QGridLayout,
    row: int,
    label_text: str,
    path_label: PathValueLabel,
    button: QPushButton,
    parent: QWidget,
) -> None:
    form.addWidget(_field_label(label_text, parent), row, 0)
    form.addWidget(path_label, row, 1)
    form.addWidget(button, row, 2)


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
