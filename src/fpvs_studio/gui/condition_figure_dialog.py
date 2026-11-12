"""Select configured FPVS stimuli and export a condition figure."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from html import escape
from pathlib import Path

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QSignalBlocker,
    Qt,
    Slot,
)
from PySide6.QtGui import QImage, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.paths import to_project_relative_posix
from fpvs_studio.gui.components import (
    PathValueLabel,
    apply_dialog_theme,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.design_system import elide_middle
from fpvs_studio.gui.designer_sources import load_designer_thumbnails
from fpvs_studio.gui.window_layout import SectionCard
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.support.error_explanations import describe_error
from fpvs_studio.tools.condition_figure import (
    ConditionFigureResult,
    ConditionFigureSpec,
    condition_figure_slot_roles,
    render_condition_figure,
)
from fpvs_studio.tools.condition_figure_project import (
    ConditionFigureSources,
    condition_figure_candidates,
    load_condition_figure_sources,
    validate_condition_figure_destination,
)

LOGGER = logging.getLogger(__name__)
_PREVIEW_SIZE = 112
_SLOT_TITLES = ("Base 1", "Base 2", "Base 3", "Base 4", "Oddball")
_NO_EXAMPLE = "No example"


@dataclass(frozen=True)
class _FigurePreview:
    spec: ConditionFigureSpec
    images: dict[Path, QImage]


@dataclass(frozen=True)
class _LoadedCondition:
    condition_id: str
    sources: ConditionFigureSources
    preview: _FigurePreview


class _StimulusChoices(QAbstractListModel):
    """Let all Base selectors read one pool without populating duplicate rows."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.stimuli: tuple[Path | str, ...] = ()

    def set_stimuli(self, stimuli: tuple[Path | str, ...]) -> None:
        self.beginResetModel()
        self.stimuli = stimuli
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None,
    ) -> int:
        return 0 if parent is not None and parent.isValid() else len(self.stimuli)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        row = index.row()
        if not 0 <= row < len(self.stimuli):
            return None
        stimulus = self.stimuli[row]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return stimulus.name if isinstance(stimulus, Path) else stimulus
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"<p>{escape(str(stimulus))}</p>"
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return str(stimulus)
        return None


def _preview_samples(spec: ConditionFigureSpec) -> tuple[Path | str | None, ...]:
    """Fit the first examples from each role into the five preview cells."""
    if spec.sequence_stimuli is None:
        return (*spec.base_stimuli, spec.oddball_stimulus)
    base: list[Path | str | None] = []
    oddballs: list[Path | str | None] = []
    for is_oddball, stimulus in zip(
        condition_figure_slot_roles(spec.oddball_every_n), spec.sequence_stimuli, strict=True,
    ):
        (oddballs if is_oddball else base).append(stimulus)
    base = base[:4]
    base.extend([None] * (4 - len(base)))
    oddball = oddballs[0] if oddballs else None
    return (*base, oddball)


def _prepare_preview(project_root: Path, spec: ConditionFigureSpec) -> _FigurePreview:
    """Decode only the chosen images. QPixmaps are constructed by the receiver."""
    images: dict[Path, QImage] = {}
    for stimulus in dict.fromkeys(_preview_samples(spec)):
        if not isinstance(stimulus, Path):
            continue
        try:
            relative_path = to_project_relative_posix(project_root, stimulus)
            images[stimulus] = load_designer_thumbnails(
                project_root, {"base": ("", (relative_path,))},
            )["base"][0]
        except (OSError, ValueError) as error:
            LOGGER.warning("Condition figure thumbnail unavailable: %s", error)
    return _FigurePreview(spec, images)


def _load_condition(
    project: ProjectFile, project_root: Path, condition_id: str,
) -> _LoadedCondition:
    sources = load_condition_figure_sources(project, project_root, condition_id)
    return _LoadedCondition(
        condition_id, sources, _prepare_preview(project_root, sources.automatic_spec()),
    )


def _choose_figure_path(parent: QWidget, suggested: Path) -> Path | None:
    dialog = QFileDialog(parent, "Export Condition Figure", str(suggested.parent))
    dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
    dialog.setNameFilter("PNG image (*.png)")
    dialog.setDefaultSuffix("png")
    dialog.selectFile(suggested.name)
    try:
        if dialog.exec() == QDialog.DialogCode.Accepted and (paths := dialog.selectedFiles()):
            return Path(paths[0])
        return None
    finally:
        dialog.deleteLater()


class ConditionFigureDialog(QDialog):
    """Read the active project snapshot and write only a selected PNG destination."""

    def __init__(
        self, project: ProjectFile, project_root: Path, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("condition_figure_dialog")
        self.setWindowTitle("Condition Figure")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumSize(860, 520)
        self.resize(920, 560)
        self._project = project.model_copy(deep=True)
        self._project_root = project_root
        self._sources: ConditionFigureSources | None = None
        self._automatic_preview: _FigurePreview | None = None
        self._preview_spec: ConditionFigureSpec | None = None
        self._task: BackgroundTask | None = None
        self._load_pending = False
        self._preview_pending = False
        self._task_failure_title = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        form = QFormLayout()
        self.condition_combo = QComboBox(self)
        self.condition_combo.setAccessibleName("Condition")
        self.condition_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
        )
        self.condition_combo.setMinimumContentsLength(24)
        for condition in condition_figure_candidates(self._project):
            self.condition_combo.addItem(condition.name, condition.condition_id)
        form.addRow("Condition", self.condition_combo)
        self.mode_combo = QComboBox(self)
        self.mode_combo.setAccessibleName("Stimulus selection")
        self.mode_combo.addItems(["Automatic", "Manual"])
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.mode_combo)
        self.timing_label = QLabel(self)
        self.timing_label.setTextFormat(Qt.TextFormat.PlainText)
        mode_row.addWidget(self.timing_label)
        mode_row.addStretch(1)
        form.addRow("Stimulus selection", mode_row)
        layout.addLayout(form)

        card = SectionCard(title="Stimulus previews", framed=False, parent=self)
        card.card_layout.setContentsMargins(0, 0, 0, 0)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self._base_choices = _StimulusChoices(self)
        self._oddball_choices = _StimulusChoices(self)
        self.stimulus_combos = tuple(QComboBox(card) for _ in _SLOT_TITLES)
        self.preview_labels = tuple(QLabel(card) for _ in _SLOT_TITLES)
        for index, (title, combo, preview) in enumerate(zip(
            _SLOT_TITLES, self.stimulus_combos, self.preview_labels, strict=True,
        )):
            grid.setColumnStretch(index, 1)
            label = QLabel(title, card)
            label.setBuddy(combo)
            grid.addWidget(label, 0, index)
            preview.setAccessibleName(f"{title} preview")
            preview.setTextFormat(Qt.TextFormat.PlainText)
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setWordWrap(True)
            preview.setFixedHeight(_PREVIEW_SIZE + 4)
            preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            preview.setFrameShape(QFrame.Shape.StyledPanel)
            grid.addWidget(preview, 1, index)
            combo.setAccessibleName(title)
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
            )
            combo.setMinimumContentsLength(10)
            combo.setModel(self._oddball_choices if title == "Oddball" else self._base_choices)
            combo.currentIndexChanged.connect(self._selection_changed)
            grid.addWidget(combo, 2, index)
        card.body_layout.addLayout(grid)
        layout.addWidget(card)

        self.status_label = QLabel(self)
        self.status_label.setAccessibleName("Condition figure status")
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.status_label.setMinimumHeight(3 * self.status_label.fontMetrics().lineSpacing())
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.status_label)
        self.output_path_label = PathValueLabel(self)
        self.output_path_label.setTextFormat(Qt.TextFormat.PlainText)
        self.output_path_label.setAccessibleName("Exported figure path")
        self.output_path_label.hide()
        layout.addWidget(self.output_path_label)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = QPushButton("Close", self)
        self.close_button.setAutoDefault(False)
        mark_secondary_action(self.close_button)
        self.close_button.clicked.connect(self.reject)
        buttons.addWidget(self.close_button)
        self.export_button = QPushButton("Export PNG…", self)
        self.export_button.setAutoDefault(False)
        self.export_button.setToolTip("Save a 600-DPI PNG.")
        mark_primary_action(self.export_button)
        self.export_button.clicked.connect(self._export)
        buttons.addWidget(self.export_button)
        layout.addLayout(buttons)

        self.condition_combo.currentIndexChanged.connect(self._load_sources)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self._update_choice_details()
        self._refresh_controls()
        apply_dialog_theme(self)

    @property
    def has_active_task(self) -> bool:
        return self._task is not None

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not event.spontaneous():
            self._load_sources()

    def reject(self) -> None:
        if not self.has_active_task:
            super().reject()

    @Slot()
    def _load_sources(self) -> None:
        self._sources = None
        self._automatic_preview = None
        self._preview_spec = None
        self._preview_pending = False
        self.timing_label.clear()
        self.output_path_label.hide()
        self._set_pools((), ())
        for preview in self.preview_labels:
            preview.clear()
        self._update_choice_details()
        if self.has_active_task:
            self._load_pending = True
            return
        condition_id = self.condition_combo.currentData()
        if not isinstance(condition_id, str):
            self._show_status(
                "This project has no conditions with a standard FPVS base and oddball sequence."
                if self._project.conditions else "Add an FPVS condition in Setup > Conditions.",
            )
            self._refresh_controls()
            return
        project, root = self._project, self._project_root
        self._start_task(
            lambda: _load_condition(project, root, condition_id),
            self._sources_loaded, "Loading configured stimuli…", "Load condition stimuli",
        )

    @Slot(object)
    def _sources_loaded(self, result: object) -> None:
        if not isinstance(result, _LoadedCondition):
            self._task_failed(RuntimeError("Studio received an unexpected source result."))
            return
        if result.condition_id != self.condition_combo.currentData():
            return
        self._sources = result.sources
        self._automatic_preview = result.preview
        spec = result.preview.spec
        self._set_pools(result.sources.base_stimuli, result.sources.oddball_stimuli)
        oddball_hz = spec.base_hz / spec.oddball_every_n
        self.timing_label.setText(f"{spec.base_hz:g} Hz stimulus · {oddball_hz:g} Hz oddball")
        self._mode_changed()

    @Slot()
    def _mode_changed(self) -> None:
        if self._automatic_preview is not None:
            spec = self._automatic_preview.spec
            stimuli = (_preview_samples(spec) if self.mode_combo.currentIndex() == 0
                       else (*spec.base_stimuli, spec.oddball_stimulus))
            self._select_stimuli(stimuli)
        self._selection_changed()

    def _set_pools(self, base: tuple[Path | str, ...], oddball: tuple[Path | str, ...]) -> None:
        with ExitStack() as blockers:
            for combo in self.stimulus_combos:
                blockers.enter_context(QSignalBlocker(combo))
            self._base_choices.set_stimuli(base)
            self._oddball_choices.set_stimuli(oddball)

    def _select_stimuli(self, stimuli: tuple[Path | str | None, ...]) -> None:
        for combo, stimulus in zip(self.stimulus_combos, stimuli, strict=True):
            choices = self._oddball_choices if combo is self.stimulus_combos[-1] else (
                self._base_choices
            )
            with QSignalBlocker(combo):
                combo.setCurrentIndex(-1 if stimulus is None else choices.stimuli.index(stimulus))

    def _current_spec(self) -> ConditionFigureSpec | None:
        sources = self._sources
        if sources is None:
            return None
        if self.mode_combo.currentIndex() == 0:
            return self._automatic_preview.spec if self._automatic_preview is not None else None
        indices = [combo.currentIndex() for combo in self.stimulus_combos]
        if min(indices) < 0:
            return None
        return sources.make_spec(
            tuple(sources.base_stimuli[index] for index in indices[:-1]),
            sources.oddball_stimuli[indices[-1]],
        )

    @Slot()
    def _selection_changed(self) -> None:
        self._update_choice_details()
        self._refresh_controls()
        spec = self._current_spec()
        if spec is None or spec == self._preview_spec:
            return
        self.output_path_label.hide()
        cached = self._automatic_preview
        if cached is not None and _preview_samples(spec) == _preview_samples(cached.spec):
            self._show_preview(_FigurePreview(spec, cached.images))
            return
        if self.has_active_task:
            self._preview_pending = True
            return
        for preview in self.preview_labels:
            preview.clear()
        root = self._project_root
        self._start_task(
            lambda: _prepare_preview(root, spec), self._preview_loaded,
            "Preparing selected previews…", "Preview condition stimuli",
        )

    @Slot(object)
    def _preview_loaded(self, result: object) -> None:
        if isinstance(result, _FigurePreview) and result.spec == self._current_spec():
            self._show_preview(result)

    def _show_preview(self, result: _FigurePreview) -> None:
        self._preview_spec = result.spec
        unavailable = False
        for preview, stimulus in zip(
            self.preview_labels, _preview_samples(result.spec), strict=True,
        ):
            if isinstance(stimulus, Path):
                if (image := result.images.get(stimulus)) is None:
                    preview.setText("Preview unavailable")
                    unavailable = True
                else:
                    pixmap = QPixmap.fromImage(image).scaled(
                        _PREVIEW_SIZE, _PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    preview.setPixmap(pixmap)
            elif stimulus is not None:
                preview.setText(elide_middle(stimulus, 64))
            else:
                preview.setText(_NO_EXAMPLE)
        messages = []
        if unavailable:
            messages.append("Some selected images could not be previewed.")
        if result.spec.sequence_stimuli is not None and None in result.spec.sequence_stimuli:
            messages.append("Some slots have no unused stimulus.")
        self._show_status(" ".join(messages))

    def _update_choice_details(self) -> None:
        condition = self.condition_combo.currentText()
        self.condition_combo.setToolTip(f"<p>{escape(condition)}</p>" if condition else "")
        self.condition_combo.setAccessibleDescription(condition)
        for combo, preview in zip(self.stimulus_combos, self.preview_labels, strict=True):
            detail = combo.currentData(Qt.ItemDataRole.AccessibleTextRole) or ""
            tooltip = combo.currentData(Qt.ItemDataRole.ToolTipRole) or ""
            if self._automatic_preview is not None and combo.currentIndex() == -1:
                detail = _NO_EXAMPLE
            combo.setToolTip(tooltip)
            combo.setAccessibleDescription(detail)
            preview.setToolTip(tooltip)
            preview.setAccessibleDescription(detail)

    @Slot()
    def _export(self) -> None:
        spec = self._current_spec()
        if spec is None or self.has_active_task:
            return
        condition_id = self.condition_combo.currentData()
        output_path = _choose_figure_path(self, self._project_root / f"{condition_id}-figure.png")
        if output_path is None:
            return
        if output_path.suffix.lower() != ".png":
            self._show_status("Choose a filename ending in .png.")
            return
        project, root = self._project, self._project_root

        def export() -> ConditionFigureResult:
            validate_condition_figure_destination(project, root, output_path)
            return render_condition_figure(spec, output_path)

        self.output_path_label.hide()
        self._start_task(
            export, self._exported, "Exporting 600-DPI PNG…", "Export condition figure",
        )

    @Slot(object)
    def _exported(self, result: object) -> None:
        if not isinstance(result, ConditionFigureResult):
            self._task_failed(RuntimeError("Studio received an unexpected figure result."))
            return
        self.output_path_label.set_path_text(str(result.path))
        self.output_path_label.setToolTip(f"<p>{escape(str(result.path))}</p>")
        self.output_path_label.setAccessibleDescription(str(result.path))
        self.output_path_label.show()
        status = "Saved 600-DPI PNG."
        if result.warnings:
            status += f" {result.warnings[0]}"
        self._show_status(status, details="\n".join(result.warnings))

    def _start_task(
        self,
        callback: Callable[[], object],
        on_success: Callable[[object], None],
        status: str,
        failure_title: str,
    ) -> None:
        task = BackgroundTask(parent_widget=self, callback=callback)
        self._task = task
        self._task_failure_title = failure_title
        self._show_status(status)
        self._refresh_controls()
        task.succeeded.connect(on_success)
        task.failed.connect(self._task_failed)
        task.finished.connect(self._finish_task)
        try:
            task.start()
        except RuntimeError as error:
            self._task_failed(error)
            task.deleteLater()
            self._finish_task()

    @Slot(object)
    def _task_failed(self, error: object) -> None:
        if self._load_pending:
            return
        LOGGER.warning("%s failed: %s", self._task_failure_title, error)
        self._show_status(describe_error(self._task_failure_title, error), details=str(error))

    @Slot()
    def _finish_task(self) -> None:
        self._task = None
        if self._load_pending:
            self._load_pending = False
            self._load_sources()
        elif self._preview_pending:
            self._preview_pending = False
            self._selection_changed()
        self._refresh_controls()

    def _show_status(self, message: str, *, details: str = "") -> None:
        full = "\n\n".join(value for value in (message, details) if value)
        self.status_label.setText(elide_middle(message.replace("\n", " "), 218))
        tooltip = escape(full).replace("\n", "<br>")
        self.status_label.setToolTip(f"<p>{tooltip}</p>" if tooltip else "")
        self.status_label.setAccessibleDescription(full)

    def _refresh_controls(self) -> None:
        idle = not self.has_active_task
        has_sources = self._sources is not None
        self.condition_combo.setEnabled(idle and self.condition_combo.count() > 0)
        self.mode_combo.setEnabled(idle and has_sources)
        for combo in self.stimulus_combos:
            combo.setEnabled(idle and has_sources and self.mode_combo.currentIndex() == 1)
        self.export_button.setEnabled(idle and self._current_spec() is not None)
        self.close_button.setEnabled(idle)
