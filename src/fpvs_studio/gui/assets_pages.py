"""Asset import and readiness pages for the FPVS Studio main window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import StimulusVariant
from fpvs_studio.gui.design_system import PAGE_SECTION_GAP, elide_middle
from fpvs_studio.gui.document import ConditionStimulusRow, ProjectDocument
from fpvs_studio.gui.window_helpers import (
    _prefixed_object_name,
    _resolution_text,
    _show_error_dialog,
    _variant_label,
)
from fpvs_studio.gui.window_layout import NonHomePageShell, SectionCard
from fpvs_studio.gui.workers import ProgressTask


class AssetsPage(QWidget):
    """Stimuli manager page."""

    def __init__(self, document: ProjectDocument, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document
        self._variant_checkboxes: dict[StimulusVariant, QCheckBox] = {}
        self._active_task: ProgressTask | None = None
        self._active_task_error_title = "Asset Task Error"

        controls_row = QWidget(self)
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(PAGE_SECTION_GAP)

        variants_label = QLabel("Enabled Variants", controls_row)
        variants_label.setProperty("sectionCardRole", "subtitle")
        controls_layout.addWidget(variants_label)
        for variant in StimulusVariant:
            checkbox = QCheckBox(_variant_label(variant), controls_row)
            checkbox.setObjectName(f"variant_checkbox_{variant.value}")
            checkbox.stateChanged.connect(self._apply_supported_variants)
            if variant == StimulusVariant.ORIGINAL:
                checkbox.setEnabled(False)
            self._variant_checkboxes[variant] = checkbox
            controls_layout.addWidget(checkbox)
        controls_layout.addStretch(1)

        self.import_source_button = QPushButton("Import Selected Source Folder...", self)
        self.import_source_button.setObjectName("assets_import_source_button")
        self.import_source_button.clicked.connect(self._import_selected_source)
        self.refresh_button = QPushButton("Refresh Source Details", self)
        self.refresh_button.setObjectName("assets_refresh_button")
        self.refresh_button.clicked.connect(self._refresh_inspection)
        self.materialize_button = QPushButton("Build Supported Variants", self)
        self.materialize_button.setObjectName("materialize_assets_button")
        self.materialize_button.setProperty("primaryActionRole", "true")
        self.materialize_button.clicked.connect(self._materialize_assets)

        controls_layout.addWidget(self.import_source_button)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.materialize_button)

        self.assets_table = QTableWidget(0, 6, self)
        self.assets_table.setObjectName("assets_table")
        self.assets_table.setHorizontalHeaderLabels(
            ["Condition", "Role", "Source Path", "Items", "Resolution", "Available Variants"]
        )
        self.assets_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.assets_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.assets_table.itemSelectionChanged.connect(self._update_buttons)
        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setWordWrap(False)
        self.assets_table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.assets_table.setMinimumHeight(420)
        self.assets_table.verticalHeader().setVisible(False)
        header = self.assets_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.assets_table.setColumnWidth(0, 180)
        self.assets_table.setColumnWidth(5, 260)

        self.assets_status_text = QPlainTextEdit(self)
        self.assets_status_text.setObjectName("assets_status_text")
        self.assets_status_text.setReadOnly(True)
        self.assets_status_text.setMaximumBlockCount(200)
        self.assets_status_text.setMinimumHeight(72)
        self.assets_status_text.setMaximumHeight(96)
        self.assets_status_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.shell = NonHomePageShell(
            title="Stimuli Manager",
            subtitle=(
                "Manage condition-level stimulus sources, inspect imported sets, and "
                "prepare supported variants for the current project."
            ),
            layout_mode="single_column",
            width_preset="full",
            parent=self,
        )
        self.shell.add_content_widget(controls_row)
        self.shell.add_content_widget(self.assets_table, stretch=1)
        self.shell.add_content_widget(self.assets_status_text)
        self.shell.set_footer_text(
            "Select a condition-role row to import or refresh its stimulus source."
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.shell)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        supported_variants = set(self._document.project.settings.supported_variants)
        for variant, checkbox in self._variant_checkboxes.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(variant in supported_variants)

        rows = self._document.condition_rows()
        with QSignalBlocker(self.assets_table):
            self.assets_table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                self._set_table_item(row_index, 0, row.condition_name)
                self._set_table_item(
                    row_index, 1, row.role.title(), alignment=Qt.AlignmentFlag.AlignCenter
                )
                source_item = self._set_table_item(
                    row_index,
                    2,
                    elide_middle(row.stimulus_set.source_dir, 72),
                )
                source_item.setData(
                    Qt.ItemDataRole.UserRole,
                    (row.condition_id, row.role),
                )
                source_item.setToolTip(row.stimulus_set.source_dir)
                self._set_table_item(
                    row_index,
                    3,
                    str(row.stimulus_set.image_count),
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self._set_table_item(
                    row_index,
                    4,
                    _resolution_text(row.stimulus_set.resolution),
                    alignment=Qt.AlignmentFlag.AlignCenter,
                )
                self._set_table_item(
                    row_index,
                    5,
                    ", ".join(_variant_label(item) for item in row.stimulus_set.available_variants),
                )
        self._resize_table_columns()
        self.assets_status_text.setPlainText(self._build_status_text(rows))
        self._update_buttons()

    def _resize_table_columns(self) -> None:
        self.assets_table.resizeColumnToContents(0)
        condition_width = max(180, min(self.assets_table.columnWidth(0) + 24, 260))
        self.assets_table.setColumnWidth(0, condition_width)

        self.assets_table.resizeColumnToContents(5)
        variants_width = max(220, min(self.assets_table.columnWidth(5) + 24, 340))
        self.assets_table.setColumnWidth(5, variants_width)

    def _set_table_item(
        self,
        row: int,
        column: int,
        text: str,
        *,
        alignment: Qt.AlignmentFlag | None = None,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        item.setToolTip(text)
        if alignment is not None:
            item.setTextAlignment(alignment)
        self.assets_table.setItem(row, column, item)
        return item

    def _build_status_text(self, rows: list[ConditionStimulusRow]) -> str:
        manifest = self._document.manifest
        lines = [
            f"Stimulus source rows: {len(rows)}",
            "Enabled variants: "
            + ", ".join(
                _variant_label(item) for item in self._document.project.settings.supported_variants
            ),
        ]
        if manifest is None:
            lines.append("Catalog status: no tracked stimulus sets yet.")
        else:
            lines.append(
                "Catalog status: "
                f"{len(manifest.sets)} stimulus set(s), updated "
                f"{manifest.generated_at.isoformat(timespec='seconds')}."
            )
        validation = self._document.validation_report(
            refresh_hz=self._document.project.settings.display.preferred_refresh_hz or 60.0
        )
        if validation.issues:
            lines.append("")
            lines.append("Readiness issues:")
            lines.extend(f"- {issue.message}" for issue in validation.issues)
        return "\n".join(lines)

    def _selected_binding(self) -> tuple[str, str] | None:
        selected_items = self.assets_table.selectedItems()
        if not selected_items:
            return None
        item = self.assets_table.item(selected_items[0].row(), 2)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if (
            isinstance(value, tuple)
            and len(value) == 2
            and isinstance(value[0], str)
            and isinstance(value[1], str)
        ):
            return value
        return None

    def _update_buttons(self) -> None:
        is_busy = self._active_task is not None
        self.import_source_button.setEnabled(not is_busy and self._selected_binding() is not None)
        self.refresh_button.setEnabled(not is_busy)
        self.materialize_button.setEnabled(not is_busy)

    def _apply_supported_variants(self) -> None:
        variants = [
            variant
            for variant, checkbox in self._variant_checkboxes.items()
            if checkbox.isChecked()
        ]
        try:
            self._document.set_supported_variants(variants)
        except Exception as error:
            _show_error_dialog(self, "Stimulus Variants Error", error)
            self.refresh()

    def _import_selected_source(self) -> None:
        binding = self._selected_binding()
        if binding is None:
            return
        directory = QFileDialog.getExistingDirectory(
            self,
            "Choose Stimulus Source Folder",
            str(Path.home()),
        )
        if not directory:
            return
        condition_id, role = binding
        try:
            self._document.import_condition_stimulus_folder(
                condition_id,
                role=role,
                source_dir=Path(directory),
            )
        except Exception as error:
            _show_error_dialog(self, "Stimulus Import Error", error)

    def _refresh_inspection(self) -> None:
        self._run_with_progress(
            "Refreshing stimulus source details...",
            self._document.refresh_stimulus_inspection,
            error_title="Source Inspection Error",
        )

    def _materialize_assets(self) -> None:
        self._run_with_progress(
            "Building supported stimulus variants...",
            self._document.materialize_assets,
            error_title="Variant Build Error",
        )

    def _run_with_progress(
        self,
        label: str,
        callback: Callable[[], object],
        *,
        error_title: str,
    ) -> None:
        if self._active_task is not None:
            return
        self._active_task_error_title = error_title
        task = ProgressTask(parent_widget=self, label=label, callback=callback)
        self._active_task = task
        self._update_buttons()
        task.succeeded.connect(self._on_background_task_succeeded)
        task.failed.connect(self._on_background_task_failed)
        task.finished.connect(self._on_background_task_finished)
        task.start()

    def _on_background_task_succeeded(self, _result: object) -> None:
        self.refresh()

    def _on_background_task_failed(self, error: object) -> None:
        if isinstance(error, Exception):
            _show_error_dialog(self, self._active_task_error_title, error)
        else:
            _show_error_dialog(self, self._active_task_error_title, RuntimeError(str(error)))

    def _on_background_task_finished(self) -> None:
        self._active_task = None
        self._update_buttons()


class AssetsReadinessEditor(QWidget):
    """Compact assets readiness snapshot and actions."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        object_name_prefix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._variant_checkboxes: dict[StimulusVariant, QCheckBox] = {}
        self._active_task: ProgressTask | None = None
        self._active_task_error_title = "Asset Task Error"

        self.card = SectionCard(
            title="Assets Readiness",
            subtitle="Variant support, inspection status, and build actions.",
            object_name=_prefixed_object_name(object_name_prefix, "assets_readiness_card"),
            parent=self,
        )
        self.card.card_layout.setContentsMargins(12, 10, 12, 10)
        self.card.card_layout.setSpacing(8)
        self.card.body_layout.setSpacing(8)

        variants_row = QWidget(self.card)
        variants_layout = QHBoxLayout(variants_row)
        variants_layout.setContentsMargins(0, 0, 0, 0)
        variants_layout.setSpacing(6)
        for variant in StimulusVariant:
            checkbox = QCheckBox(_variant_label(variant), variants_row)
            checkbox.setObjectName(
                _prefixed_object_name(object_name_prefix, f"variant_checkbox_{variant.value}")
            )
            checkbox.stateChanged.connect(self._apply_supported_variants)
            if variant == StimulusVariant.ORIGINAL:
                checkbox.setEnabled(False)
            self._variant_checkboxes[variant] = checkbox
            variants_layout.addWidget(checkbox)
        variants_layout.addStretch(1)

        self.condition_rows_value = QLabel(self.card)
        self.condition_rows_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_condition_rows_value")
        )
        self.manifest_status_value = QLabel(self.card)
        self.manifest_status_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_manifest_status_value")
        )
        self.manifest_status_value.setWordWrap(True)
        self.materialization_status_value = QLabel(self.card)
        self.materialization_status_value.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_materialization_status_value")
        )
        self.materialization_status_value.setWordWrap(True)
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(6)
        summary_grid.addWidget(QLabel("Rows", self.card), 0, 0)
        summary_grid.addWidget(self.condition_rows_value, 0, 1)
        summary_grid.addWidget(QLabel("Manifest", self.card), 1, 0)
        summary_grid.addWidget(self.manifest_status_value, 1, 1)
        summary_grid.addWidget(QLabel("Build", self.card), 2, 0)
        summary_grid.addWidget(self.materialization_status_value, 2, 1)
        summary_grid.setColumnStretch(1, 1)

        self.refresh_button = QPushButton("Refresh Inspection", self.card)
        self.refresh_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "assets_refresh_button")
        )
        self.refresh_button.clicked.connect(self._refresh_inspection)
        self.materialize_button = QPushButton("Materialize Supported Variants", self.card)
        self.materialize_button.setObjectName(
            _prefixed_object_name(object_name_prefix, "materialize_assets_button")
        )
        self.materialize_button.clicked.connect(self._materialize_assets)

        actions_row = QWidget(self.card)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.refresh_button)
        actions_layout.addWidget(self.materialize_button)
        actions_layout.addStretch(1)

        self.card.body_layout.addWidget(variants_row)
        self.card.body_layout.addLayout(summary_grid)
        self.card.body_layout.addWidget(actions_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.card)

        self._document.project_changed.connect(self.refresh)
        self._document.manifest_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        supported_variants = set(self._document.project.settings.supported_variants)
        for variant, checkbox in self._variant_checkboxes.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(variant in supported_variants)

        rows = self._document.condition_rows()
        self.condition_rows_value.setText(f"Condition stimulus rows: {len(rows)}")
        manifest = self._document.manifest
        if manifest is None:
            self.manifest_status_value.setText("Manifest status: no manifest loaded yet.")
        else:
            self.manifest_status_value.setText(
                "Manifest status: "
                f"{len(manifest.sets)} set(s), generated {manifest.generated_at.isoformat()}."
            )
        refresh_hz = self._document.project.settings.display.preferred_refresh_hz or 60.0
        validation = self._document.validation_report(refresh_hz=refresh_hz)
        issue_count = len(validation.issues)
        if issue_count == 0:
            self.materialization_status_value.setText(
                "Materialization readiness: clear validation checks."
            )
        else:
            self.materialization_status_value.setText(
                f"Materialization readiness: {issue_count} validation issue(s) need attention."
            )

    def _apply_supported_variants(self) -> None:
        variants = [
            variant
            for variant, checkbox in self._variant_checkboxes.items()
            if checkbox.isChecked()
        ]
        try:
            self._document.set_supported_variants(variants)
        except Exception as error:
            _show_error_dialog(self, "Supported Variants Error", error)
            self.refresh()

    def _refresh_inspection(self) -> None:
        self._run_with_progress(
            "Refreshing source inspection...",
            self._document.refresh_stimulus_inspection,
            error_title="Inspection Error",
        )

    def _materialize_assets(self) -> None:
        self._run_with_progress(
            "Materializing project assets...",
            self._document.materialize_assets,
            error_title="Materialization Error",
        )

    def _run_with_progress(
        self,
        label: str,
        callback: Callable[[], object],
        *,
        error_title: str,
    ) -> None:
        if self._active_task is not None:
            return
        self._active_task_error_title = error_title
        task = ProgressTask(parent_widget=self, label=label, callback=callback)
        self._active_task = task
        self._update_task_buttons()
        task.succeeded.connect(self._on_background_task_succeeded)
        task.failed.connect(self._on_background_task_failed)
        task.finished.connect(self._on_background_task_finished)
        task.start()

    def _update_task_buttons(self) -> None:
        is_busy = self._active_task is not None
        self.refresh_button.setEnabled(not is_busy)
        self.materialize_button.setEnabled(not is_busy)

    def _on_background_task_succeeded(self, _result: object) -> None:
        self.refresh()

    def _on_background_task_failed(self, error: object) -> None:
        if isinstance(error, Exception):
            _show_error_dialog(self, self._active_task_error_title, error)
        else:
            _show_error_dialog(self, self._active_task_error_title, RuntimeError(str(error)))

    def _on_background_task_finished(self) -> None:
        self._active_task = None
        self._update_task_buttons()
