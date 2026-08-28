"""Draft-based authoring dialog for condition pre/post participant tasks.

The widgets in this module intentionally edit GUI-local draft objects.  Core owns the
persisted task contracts and their final validation; adapters at the bottom of this
module are the only translation seam between those contracts and the editor.
"""

from __future__ import annotations

import copy
import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.assets import bundled_task_font_path
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskBranchOperator,
    TaskBranchRule,
    TaskDisplayItem,
    TaskFontFamily,
    TaskItemModality,
    TaskLayoutMode,
    TaskModule,
    TaskOccurrence,
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskSubmissionMode,
)
from fpvs_studio.core.task_models import (
    TaskStepKind as CoreTaskStepKind,
)
from fpvs_studio.gui.components import (
    mark_destructive_action,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.preview_cache import PreviewPixmapCache

if TYPE_CHECKING:
    from fpvs_studio.gui.document import ProjectDocument

TaskStepKind = Literal[
    "instruction",
    "study",
    "choice_grid",
    "questionnaire",
    "raw_key",
    "timed_feedback",
]
QuestionKind = Literal[
    "single_choice",
    "multiple_choice",
    "short_text",
    "long_text",
    "numeric",
    "rating",
]

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_REGISTERED_QT_TASK_FONTS: set[str] = set()
_MODULE_LABELS: tuple[tuple[str, TaskStepKind], ...] = (
    ("Instruction / Content", "instruction"),
    ("Study Display", "study"),
    ("Choice Grid", "choice_grid"),
    ("Questionnaire", "questionnaire"),
    ("Raw Key Response", "raw_key"),
    ("Timed Feedback", "timed_feedback"),
)


def _register_qt_task_font(font_family: str) -> None:
    """Make a packaged task font available to the authoring preview."""

    font_path = bundled_task_font_path(font_family)
    if font_path is None or font_family in _REGISTERED_QT_TASK_FONTS:
        return
    if font_path.is_file() and QFontDatabase.addApplicationFont(str(font_path)) >= 0:
        _REGISTERED_QT_TASK_FONTS.add(font_family)


_QUESTION_LABELS: tuple[tuple[str, QuestionKind], ...] = (
    ("Single Choice", "single_choice"),
    ("Multiple Choice", "multiple_choice"),
    ("Short Text", "short_text"),
    ("Long Text", "long_text"),
    ("Numeric", "numeric"),
    ("Rating Scale", "rating"),
)
_OCCURRENCE_LABELS = (
    ("Every condition occurrence", "every_entry"),
    ("First occurrence in the session", "first_occurrence"),
    ("Last occurrence in the session", "last_occurrence"),
)
_IMAGE_SUFFIXES = frozenset({".jpeg", ".jpg", ".png"})


@dataclass
class TaskOptionDraft:
    """One display item or response option in a task step."""

    option_id: str
    label: str = ""
    image_path: str | None = None
    source_path: Path | None = None
    selectable: bool = True
    correct: bool | None = None
    score: float | None = None
    x_degrees: float = 0.0
    y_degrees: float = 0.0
    width_degrees: float | None = None
    height_degrees: float | None = None
    unit: str = "degrees"


@dataclass
class TaskBranchRuleDraft:
    """One bounded conditional jump retained losslessly by the GUI draft."""

    rule_id: str
    question_id: str
    operator: str = "equals"
    expected_values: list[str] = field(default_factory=list)
    expected_numeric: float | None = None
    next_step_id: str = ""


@dataclass
class TaskQuestionDraft:
    """One neutral questionnaire question."""

    question_id: str
    kind: QuestionKind = "single_choice"
    prompt: str = "Question"
    required: bool = True
    options: list[TaskOptionDraft] = field(default_factory=list)
    minimum_selections: int | None = None
    maximum_selections: int | None = None
    minimum_value: float = 1.0
    maximum_value: float = 5.0
    step_value: float = 1.0
    randomize_options: bool = False
    minimum_label: str = ""
    maximum_label: str = ""
    maximum_text_length: int = 2_000
    branch_operator: str = "equals"
    branch_match_value: str = ""
    branch_target_step_id: str = ""
    branch_rule_id: str = ""
    validation_error: str = ""


@dataclass
class TaskStepDraft:
    """GUI-local draft for one ordered task step."""

    step_id: str
    kind: TaskStepKind = "instruction"
    title: str = "Instruction"
    prompt: str = ""
    font_family: str = TaskFontFamily.ARIAL.value
    prompt_x: float = 0.0
    prompt_y: float = 0.0
    prompt_unit: str = "degrees"
    prompt_height: float | None = None
    continue_key: str | None = "space"
    advance_keys: list[str] = field(default_factory=list)
    timeout_seconds: float | None = None
    duration_seconds: float | None = None
    layout_mode: str = "responsive_grid"
    columns: int | None = 4
    repeat_count: int = 1
    maximum_attempts: int = 1
    retry_on_invalid: bool = False
    retry_on_incorrect: bool = False
    complete_after_one_valid_choice: bool = True
    minimum_selections: int = 1
    maximum_selections: int = 1
    allow_duplicate_choices_across_repeats: bool = True
    randomize_options: bool = False
    submission_mode: str = "immediate"
    show_footer: bool = True
    require_response: bool = False
    options: list[TaskOptionDraft] = field(default_factory=list)
    questions: list[TaskQuestionDraft] = field(default_factory=list)
    branch_rules: list[TaskBranchRuleDraft] = field(default_factory=list)
    validation_error: str = ""


@dataclass
class TaskModuleDraft:
    """Reusable project task module plus one condition binding's occurrence rule."""

    module_id: str
    title: str
    occurrence: str = "every_entry"
    replaces_condition_start_gate: bool = False
    repeat_count: int = 1
    steps: list[TaskStepDraft] = field(default_factory=list)


@dataclass
class ConditionTaskFlowDraft:
    """GUI-local ordered task flow for one condition."""

    pre_modules: list[TaskModuleDraft] = field(default_factory=list)
    post_modules: list[TaskModuleDraft] = field(default_factory=list)


def _slug_base(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def _unique_id(prefix: str, existing: set[str]) -> str:
    base = _slug_base(prefix, "item")
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _split_keys(value: str) -> list[str]:
    return [item.strip().lower() for item in re.split(r"[,;\s]+", value) if item.strip()]


def _format_keys(keys: list[str]) -> str:
    return ", ".join(keys)


def _format_branch_values(values: list[str]) -> str:
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerow(values)
    return output.getvalue().removesuffix("\n")


def _parse_branch_values(value: str) -> list[str]:
    if not value:
        return []
    return next(csv.reader(io.StringIO(value, newline="")), [])


def _option_lines(options: list[TaskOptionDraft]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="|", lineterminator="\n")
    for option in options:
        correctness = (
            "correct" if option.correct is True else "incorrect" if option.correct is False else ""
        )
        score = "" if option.score is None else repr(option.score)
        writer.writerow(
            (
                option.option_id,
                option.label,
                "selectable" if option.selectable else "display-only",
                correctness,
                score,
                option.image_path or "",
            )
        )
    return output.getvalue().removesuffix("\n")


def _parse_option_lines(value: str) -> list[TaskOptionDraft]:
    options: list[TaskOptionDraft] = []
    existing: set[str] = set()
    reader = csv.reader(io.StringIO(value, newline=""), delimiter="|")
    for index, raw_parts in enumerate(reader, start=1):
        if not raw_parts or not any(part.strip() for part in raw_parts):
            continue
        parts = list(raw_parts)
        if len(parts) == 1:
            label = parts[0].strip()
            identifier = _unique_id(label or f"option-{index}", existing)
            parts = [identifier, label]
        identifier = parts[0].strip()
        label = parts[1] if len(parts) > 1 else identifier
        selectable = len(parts) < 3 or parts[2].strip().lower() not in {
            "display-only",
            "false",
            "no",
            "0",
        }
        correct: bool | None = None
        if len(parts) > 3:
            correctness = parts[3].strip().lower()
            if correctness in {"correct", "true", "yes", "1"}:
                correct = True
            elif correctness in {"incorrect", "false", "no", "0"}:
                correct = False
        score = None
        if len(parts) > 4 and parts[4].strip():
            try:
                score = float(parts[4].strip())
            except ValueError as exc:
                raise ValueError(
                    f"Question option line {index} has an invalid score: '{parts[4].strip()}'."
                ) from exc
        image_path = parts[5].strip() if len(parts) > 5 and parts[5].strip() else None
        options.append(
            TaskOptionDraft(
                option_id=identifier,
                label=label,
                selectable=selectable,
                correct=correct,
                score=score,
                image_path=image_path,
            )
        )
        existing.add(identifier)
    return options


def _default_question_draft(
    *,
    question_id: str = "question-1",
    kind: QuestionKind = "single_choice",
) -> TaskQuestionDraft:
    options: list[TaskOptionDraft] = []
    if kind in {"single_choice", "multiple_choice"}:
        options = [
            TaskOptionDraft(option_id="option-1", label="Option 1"),
            TaskOptionDraft(option_id="option-2", label="Option 2"),
        ]
    return TaskQuestionDraft(
        question_id=question_id,
        kind=kind,
        prompt="Question",
        options=options,
    )


def _new_task_step_draft(
    *,
    step_id: str,
    kind: str,
    title: str,
) -> TaskStepDraft:
    step = TaskStepDraft(
        step_id=step_id,
        kind=kind,  # type: ignore[arg-type]
        title=title,
        continue_key="space" if kind in {"instruction", "study"} else None,
        require_response=kind in {"choice_grid", "questionnaire", "raw_key"},
    )
    if kind == "questionnaire":
        step.questions = [_default_question_draft()]
        step.submission_mode = "explicit"
    elif kind == "raw_key":
        step.advance_keys = ["space"]
    elif kind == "timed_feedback":
        step.duration_seconds = 1.0
    return step


def condition_task_summary_from_draft(draft: ConditionTaskFlowDraft) -> str:
    """Return compact condition-row copy for one editable task flow."""

    pre_count = len(draft.pre_modules)
    post_count = len(draft.post_modules)
    if pre_count == 0 and post_count == 0:
        return "No pre/post tasks"
    return f"{pre_count} pre, {post_count} post"


class TaskParticipantPreview(QWidget):
    """Small non-runtime rendering of the selected participant task step."""

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("condition_task_participant_preview")
        self._project_root = Path(project_root)
        self._step: TaskStepDraft | None = None
        self._image_cache = PreviewPixmapCache()
        self._active_option_image_paths: dict[int, Path] = {}
        self._source_option_pixmaps: dict[int, QPixmap] = {}
        self._scaled_option_pixmaps: dict[int, QPixmap] = {}
        self._scaled_option_keys: dict[int, tuple[int, int, int]] = {}
        self.setMinimumSize(270, 300)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(300, 400)

    def set_step(self, step: TaskStepDraft | None) -> None:
        self._step = copy.deepcopy(step)
        if step is not None:
            _register_qt_task_font(step.font_family)
        self._reload_preview_images()
        self.update()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale_preview_images()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111111"))
        painter.setPen(QColor("#f4f4f4"))
        step = self._step
        if step is None:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select a task step")
            return
        font = painter.font()
        font.setFamily(step.font_family)
        painter.setFont(font)

        title_rect = QRectF(16, 12, self.width() - 32, 34)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, step.title or "Untitled step")
        prompt_rect = QRectF(18, 48, self.width() - 36, 64)
        painter.drawText(
            prompt_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            step.prompt,
        )
        content_rect = QRectF(16, 116, self.width() - 32, self.height() - 150)
        if step.kind in {"study", "choice_grid"}:
            self._paint_options(painter, content_rect, step)
        elif step.kind == "questionnaire":
            self._paint_questions(painter, content_rect, step)
        elif step.kind == "raw_key":
            keys = _format_keys(step.advance_keys) or "No keys configured"
            painter.drawText(
                content_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                f"Accepted keys\n{keys}",
            )
        elif step.kind == "timed_feedback":
            painter.drawText(
                content_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                f"{step.prompt}\n\nVisible for {(step.duration_seconds or 0):g} s",
            )
        else:
            accepted_keys = list(step.advance_keys)
            if step.continue_key and step.continue_key not in accepted_keys:
                accepted_keys.insert(0, step.continue_key)
            painter.drawText(
                content_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Press " + (_format_keys(accepted_keys) or "a configured key"),
            )

        painter.setPen(QColor("#a8a8a8"))
        painter.drawText(
            QRectF(10, self.height() - 28, self.width() - 20, 20),
            Qt.AlignmentFlag.AlignCenter,
            "Authoring preview - runtime display remains fullscreen",
        )

    def _paint_options(
        self,
        painter: QPainter,
        bounds: QRectF,
        step: TaskStepDraft,
    ) -> None:
        if not step.options:
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Add display items")
            return
        if not self._preview_images_are_current():
            self._reload_preview_images()
        for index, (option, rect) in enumerate(
            zip(step.options, self._option_rects(bounds, step), strict=True)
        ):
            self._paint_option(
                painter,
                rect,
                option,
                self._scaled_option_pixmaps.get(index),
            )

    def _paint_option(
        self,
        painter: QPainter,
        rect: QRectF,
        option: TaskOptionDraft,
        pixmap: QPixmap | None,
    ) -> None:
        pen_color = "#f4f4f4" if option.selectable else "#707070"
        painter.setPen(QPen(QColor(pen_color), 1.0))
        painter.drawRect(rect)
        if pixmap is not None and not pixmap.isNull():
            target_x = rect.center().x() - pixmap.width() / 2
            painter.drawPixmap(int(target_x), int(rect.y() + 3), pixmap)
        painter.drawText(
            QRectF(rect.x() + 3, rect.bottom() - 22, rect.width() - 6, 20),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            option.label or option.option_id,
        )

    @staticmethod
    def _option_rects(bounds: QRectF, step: TaskStepDraft) -> list[QRectF]:
        if step.layout_mode == "exact":
            rects: list[QRectF] = []
            for option in step.options:
                scale = (
                    bounds.height()
                    if option.unit == "window_height_fraction"
                    else min(bounds.width() / 22.0, bounds.height() / 13.0)
                )
                default_size = 0.2 if option.unit == "window_height_fraction" else 3.0
                width = max(12.0, (option.width_degrees or default_size) * scale)
                height = max(12.0, (option.height_degrees or default_size) * scale)
                center_x = bounds.center().x() + option.x_degrees * scale
                center_y = bounds.center().y() - option.y_degrees * scale
                rects.append(
                    QRectF(center_x - width / 2, center_y - height / 2, width, height)
                )
            return rects

        columns = max(1, min(step.columns or len(step.options), len(step.options)))
        rows = (len(step.options) + columns - 1) // columns
        cell_width = bounds.width() / columns
        cell_height = bounds.height() / max(1, rows)
        return [
            QRectF(
                bounds.x() + column * cell_width + 4,
                bounds.y() + row * cell_height + 4,
                cell_width - 8,
                cell_height - 8,
            )
            for row, column in (divmod(index, columns) for index in range(len(step.options)))
        ]

    def _reload_preview_images(self) -> None:
        active_image_paths: dict[int, Path] = {}
        source_pixmaps: dict[int, QPixmap] = {}
        if self._step is not None:
            for index, option in enumerate(self._step.options):
                image_path = self._preview_image_path(option)
                if image_path is None:
                    continue
                active_image_paths[index] = image_path
                pixmap = self._image_cache.load(image_path)
                if not pixmap.isNull():
                    source_pixmaps[index] = pixmap
        self._image_cache.retain(active_image_paths.values())
        self._active_option_image_paths = active_image_paths
        self._source_option_pixmaps = source_pixmaps
        self._rescale_preview_images()

    def _preview_images_are_current(self) -> bool:
        current_paths: dict[int, Path] = {}
        if self._step is not None:
            current_paths = {
                index: image_path
                for index, option in enumerate(self._step.options)
                if (image_path := self._preview_image_path(option)) is not None
            }
        return current_paths == self._active_option_image_paths and all(
            self._image_cache.is_current(path) for path in current_paths.values()
        )

    def _rescale_preview_images(self) -> None:
        step = self._step
        if step is None or not step.options:
            self._scaled_option_pixmaps = {}
            self._scaled_option_keys = {}
            return
        bounds = QRectF(16, 116, self.width() - 32, self.height() - 150)
        scaled_pixmaps: dict[int, QPixmap] = {}
        scaled_keys: dict[int, tuple[int, int, int]] = {}
        for index, rect in enumerate(self._option_rects(bounds, step)):
            source = self._source_option_pixmaps.get(index)
            if source is None:
                continue
            width = max(1, int(rect.width() - 6))
            height = max(1, int(rect.height() - 24))
            key = (source.cacheKey(), width, height)
            scaled = self._scaled_option_pixmaps.get(index)
            if scaled is None or self._scaled_option_keys.get(index) != key:
                scaled = source.scaled(
                    width,
                    height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            scaled_pixmaps[index] = scaled
            scaled_keys[index] = key
        self._scaled_option_pixmaps = scaled_pixmaps
        self._scaled_option_keys = scaled_keys

    def _preview_image_path(self, option: TaskOptionDraft) -> Path | None:
        if option.source_path is not None and option.source_path.is_file():
            return option.source_path
        if not option.image_path:
            return None
        candidate = self._project_root / Path(option.image_path)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(self._project_root.resolve(strict=True))
        except (OSError, RuntimeError, ValueError):
            return None
        return resolved if resolved.is_file() else None

    @staticmethod
    def _paint_questions(
        painter: QPainter,
        bounds: QRectF,
        step: TaskStepDraft,
    ) -> None:
        if not step.questions:
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter, "Add questionnaire items")
            return
        y = bounds.y()
        row_height = max(54.0, min(84.0, bounds.height() / len(step.questions)))
        for question in step.questions[:5]:
            marker = "*" if question.required else ""
            text = f"{question.prompt}{marker}\n{question.kind.replace('_', ' ').title()}"
            rect = QRectF(bounds.x(), y, bounds.width(), row_height - 6)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
                | Qt.TextFlag.TextWordWrap,
                text,
            )
            y += row_height


class TaskOptionTable(QTableWidget):
    """Editable task items with exact-degree geometry and choice metadata."""

    changed = Signal()

    _HEADERS = (
        "ID",
        "Text / Label",
        "Image",
        "Selectable",
        "Correct",
        "Score",
        "X",
        "Y",
        "Width",
        "Height",
        "Units",
    )

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(0, len(self._HEADERS), parent)
        self.setObjectName("condition_task_option_table")
        self.setHorizontalHeaderLabels(self._HEADERS)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setMinimumHeight(190)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.setColumnWidth(0, 105)
        self.setColumnWidth(1, 150)
        self.setColumnWidth(2, 145)
        for column in range(3, 10):
            self.setColumnWidth(column, 74)
        self.setColumnWidth(10, 135)
        self._project_root = Path(project_root)
        self._syncing = False
        self.itemChanged.connect(self._emit_changed)

    def set_options(self, options: list[TaskOptionDraft]) -> None:
        self._syncing = True
        try:
            self.setRowCount(0)
            for option in options:
                self._append_option(option)
        finally:
            self._syncing = False

    def options(self) -> list[TaskOptionDraft]:
        result: list[TaskOptionDraft] = []
        for row in range(self.rowCount()):
            result.append(
                TaskOptionDraft(
                    option_id=self._text(row, 0),
                    label=self._text(row, 1),
                    image_path=self._image_path(row),
                    source_path=self._source_path(row),
                    selectable=self._checked(row, 3),
                    correct=self._optional_checked(row, 4),
                    score=self._optional_float(row, 5),
                    x_degrees=self._float(row, 6),
                    y_degrees=self._float(row, 7),
                    width_degrees=self._optional_float(row, 8),
                    height_degrees=self._optional_float(row, 9),
                    unit=self._unit(row),
                )
            )
        return result

    def add_text_option(self) -> None:
        existing = {option.option_id for option in self.options()}
        option_id = _unique_id("item", existing)
        self._append_option(TaskOptionDraft(option_id=option_id, label="Item"))
        self.selectRow(self.rowCount() - 1)
        self.changed.emit()

    def add_image_option(self, parent: QWidget) -> None:
        filename, _selected_filter = QFileDialog.getOpenFileName(
            parent,
            "Choose Task Image",
            str(self._project_root / "stimuli"),
            "Images (*.png *.jpg *.jpeg)",
        )
        if not filename:
            return
        source = Path(filename)
        if source.suffix.lower() not in _IMAGE_SUFFIXES:
            return
        existing = {option.option_id for option in self.options()}
        option_id = _unique_id(source.stem, existing)
        option = TaskOptionDraft(
            option_id=option_id,
            label=source.stem.replace("_", " ").replace("-", " ").title(),
            source_path=source,
        )
        self._append_option(option)
        self.selectRow(self.rowCount() - 1)
        self.changed.emit()

    def replace_selected_image(self, parent: QWidget) -> None:
        row = self.currentRow()
        if row < 0:
            return
        filename, _selected_filter = QFileDialog.getOpenFileName(
            parent,
            "Choose Task Image",
            str(self._project_root / "stimuli"),
            "Images (*.png *.jpg *.jpeg)",
        )
        if not filename:
            return
        source = Path(filename)
        if source.suffix.lower() not in _IMAGE_SUFFIXES:
            return
        item = self.item(row, 2)
        if item is None:
            item = QTableWidgetItem()
            self.setItem(row, 2, item)
        item.setText(source.name)
        item.setToolTip(str(source))
        item.setData(Qt.ItemDataRole.UserRole, str(source))
        self.changed.emit()

    def remove_selected(self) -> None:
        row = self.currentRow()
        if row < 0:
            return
        self.removeRow(row)
        self.changed.emit()

    def move_selected(self, offset: int) -> None:
        row = self.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.rowCount():
            return
        options = self.options()
        options[row], options[target] = options[target], options[row]
        self.set_options(options)
        self.selectRow(target)
        self.changed.emit()

    def _append_option(self, option: TaskOptionDraft) -> None:
        row = self.rowCount()
        self.insertRow(row)
        values = (
            option.option_id,
            option.label,
            Path(option.image_path).name if option.image_path else "",
            "",
            "",
            "" if option.score is None else repr(option.score),
            repr(option.x_degrees),
            repr(option.y_degrees),
            "" if option.width_degrees is None else repr(option.width_degrees),
            "" if option.height_degrees is None else repr(option.height_degrees),
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column in {3, 4}:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                if column == 4:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserTristate)
                    state = (
                        Qt.CheckState.Checked
                        if option.correct is True
                        else Qt.CheckState.Unchecked
                        if option.correct is False
                        else Qt.CheckState.PartiallyChecked
                    )
                else:
                    state = Qt.CheckState.Checked if option.selectable else Qt.CheckState.Unchecked
                item.setCheckState(state)
            if column == 2:
                item.setToolTip(option.image_path or str(option.source_path or ""))
                if option.source_path is not None:
                    item.setData(Qt.ItemDataRole.UserRole, str(option.source_path))
                item.setData(Qt.ItemDataRole.UserRole + 1, option.image_path)
            self.setItem(row, column, item)
        unit_combo = QComboBox(self)
        unit_combo.addItem("Degrees", "degrees")
        unit_combo.addItem("Window-height fraction", "window_height_fraction")
        unit_combo.setCurrentIndex(max(0, unit_combo.findData(option.unit)))
        unit_combo.currentIndexChanged.connect(self._emit_changed)
        self.setCellWidget(row, 10, unit_combo)

    def _emit_changed(self, *_args: object) -> None:
        if not self._syncing:
            self.changed.emit()

    def _text(self, row: int, column: int) -> str:
        item = self.item(row, column)
        return item.text().strip() if item is not None else ""

    def _checked(self, row: int, column: int) -> bool:
        item = self.item(row, column)
        return item is not None and item.checkState() == Qt.CheckState.Checked

    def _optional_checked(self, row: int, column: int) -> bool | None:
        item = self.item(row, column)
        if item is None or item.checkState() == Qt.CheckState.PartiallyChecked:
            return None
        return item.checkState() == Qt.CheckState.Checked

    def _float(self, row: int, column: int) -> float:
        value = self._text(row, column)
        if not value:
            return 0.0
        try:
            return float(value)
        except ValueError as exc:
            raise self._number_error(row, column, value) from exc

    def _optional_float(self, row: int, column: int) -> float | None:
        value = self._text(row, column)
        if not value:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise self._number_error(row, column, value) from exc

    def _number_error(self, row: int, column: int, value: str) -> ValueError:
        identifier = self._text(row, 0) or f"row {row + 1}"
        field_name = self._HEADERS[column]
        return ValueError(
            f"Display item '{identifier}' has an invalid {field_name} value: '{value}'."
        )

    def _source_path(self, row: int) -> Path | None:
        item = self.item(row, 2)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return Path(value) if isinstance(value, str) and value else None

    def _image_path(self, row: int) -> str | None:
        item = self.item(row, 2)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole + 1)
        return value if isinstance(value, str) and value else None

    def _unit(self, row: int) -> str:
        widget = self.cellWidget(row, 10)
        if isinstance(widget, QComboBox):
            value = widget.currentData()
            if isinstance(value, str):
                return value
        return "degrees"


class QuestionnaireEditor(QWidget):
    """Ordered questionnaire item editor covering all neutral response types."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("condition_task_questionnaire_editor")
        self._questions: list[TaskQuestionDraft] = []
        self._syncing = False

        self.question_list = QListWidget(self)
        self.question_list.setObjectName("condition_task_question_list")
        self.question_list.setMinimumHeight(130)
        self.question_list.currentRowChanged.connect(self._load_selected)

        self.add_kind_combo = QComboBox(self)
        self.add_kind_combo.setObjectName("condition_task_add_question_kind_combo")
        for label, kind in _QUESTION_LABELS:
            self.add_kind_combo.addItem(label, kind)
        self.add_button = QPushButton("Add Question", self)
        self.add_button.setObjectName("condition_task_add_question_button")
        self.add_button.clicked.connect(self._add_question)
        mark_secondary_action(self.add_button)
        self.up_button = QPushButton("Up", self)
        self.up_button.setObjectName("condition_task_question_up_button")
        self.up_button.clicked.connect(lambda: self._move_question(-1))
        mark_secondary_action(self.up_button)
        self.down_button = QPushButton("Down", self)
        self.down_button.setObjectName("condition_task_question_down_button")
        self.down_button.clicked.connect(lambda: self._move_question(1))
        mark_secondary_action(self.down_button)
        self.remove_button = QPushButton("Remove", self)
        self.remove_button.setObjectName("condition_task_remove_question_button")
        self.remove_button.clicked.connect(self._remove_question)
        mark_destructive_action(self.remove_button)

        list_actions = QGridLayout()
        list_actions.setContentsMargins(0, 0, 0, 0)
        list_actions.setSpacing(6)
        list_actions.addWidget(self.add_kind_combo, 0, 0, 1, 2)
        list_actions.addWidget(self.add_button, 0, 2)
        list_actions.addWidget(self.up_button, 1, 0)
        list_actions.addWidget(self.down_button, 1, 1)
        list_actions.addWidget(self.remove_button, 1, 2)

        list_column = QWidget(self)
        list_layout = QVBoxLayout(list_column)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        list_layout.addWidget(self.question_list, 1)
        list_layout.addLayout(list_actions)

        self.question_id_edit = QLineEdit(self)
        self.question_id_edit.setObjectName("condition_task_question_id_edit")
        self.question_kind_combo = QComboBox(self)
        self.question_kind_combo.setObjectName("condition_task_question_kind_combo")
        for label, kind in _QUESTION_LABELS:
            self.question_kind_combo.addItem(label, kind)
        self.question_prompt_edit = QTextEdit(self)
        self.question_prompt_edit.setObjectName("condition_task_question_prompt_edit")
        self.question_prompt_edit.setFixedHeight(72)
        self.required_checkbox = QCheckBox("Response required", self)
        self.required_checkbox.setObjectName("condition_task_question_required_checkbox")
        self.options_edit = QTextEdit(self)
        self.options_edit.setObjectName("condition_task_question_options_edit")
        self.options_edit.setFixedHeight(84)
        self.options_edit.setPlaceholderText(
            "id | label | selectable/display-only | correct | optional score | "
            "optional project image path"
        )
        self.randomize_question_options_checkbox = QCheckBox(
            "Randomize option order for this question",
            self,
        )
        self.randomize_question_options_checkbox.setObjectName(
            "condition_task_question_randomize_options_checkbox"
        )
        self.minimum_selections_spin = QSpinBox(self)
        self.minimum_selections_spin.setObjectName(
            "condition_task_question_minimum_selections_spin"
        )
        self.minimum_selections_spin.setRange(-1, 1000)
        self.minimum_selections_spin.setSpecialValueText("Default")
        self.maximum_selections_spin = QSpinBox(self)
        self.maximum_selections_spin.setObjectName(
            "condition_task_question_maximum_selections_spin"
        )
        self.maximum_selections_spin.setRange(0, 1000)
        self.maximum_selections_spin.setSpecialValueText("Default")
        self.minimum_value_spin = self._number_spin("condition_task_question_minimum_value_spin")
        self.maximum_value_spin = self._number_spin("condition_task_question_maximum_value_spin")
        self.step_value_spin = self._number_spin(
            "condition_task_question_step_value_spin",
            minimum=0.000001,
        )
        self.minimum_label_edit = QLineEdit(self)
        self.minimum_label_edit.setObjectName("condition_task_question_minimum_label_edit")
        self.maximum_label_edit = QLineEdit(self)
        self.maximum_label_edit.setObjectName("condition_task_question_maximum_label_edit")
        self.maximum_text_length_spin = QSpinBox(self)
        self.maximum_text_length_spin.setObjectName(
            "condition_task_question_maximum_text_length_spin"
        )
        self.maximum_text_length_spin.setRange(1, 16_384)
        self.branch_operator_combo = QComboBox(self)
        self.branch_operator_combo.setObjectName("condition_task_question_branch_operator_combo")
        for label, operator in (
            ("Equals", "equals"),
            ("Does not equal", "not_equals"),
            ("Contains", "contains"),
            ("Greater than", "greater_than"),
            ("Less than", "less_than"),
            ("Was answered", "answered"),
        ):
            self.branch_operator_combo.addItem(label, operator)
        self.branch_match_edit = QLineEdit(self)
        self.branch_match_edit.setObjectName("condition_task_question_branch_match_edit")
        self.branch_match_edit.setPlaceholderText("optional option ID or exact value")
        self.branch_target_edit = QLineEdit(self)
        self.branch_target_edit.setObjectName("condition_task_question_branch_target_edit")
        self.branch_target_edit.setPlaceholderText("optional target step ID")

        self.question_form = QFormLayout()
        self.question_form.setContentsMargins(0, 0, 0, 0)
        self.question_form.setHorizontalSpacing(10)
        self.question_form.setVerticalSpacing(6)
        self.question_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.question_form.addRow("Question ID", self.question_id_edit)
        self.question_form.addRow("Response type", self.question_kind_combo)
        self.question_form.addRow("Prompt", self.question_prompt_edit)
        self.question_form.addRow("", self.required_checkbox)
        self.options_label = QLabel("Options", self)
        self.question_form.addRow(self.options_label, self.options_edit)
        self.question_form.addRow("", self.randomize_question_options_checkbox)
        self.selection_range_row = self._two_field_row(
            "Minimum", self.minimum_selections_spin, "Maximum", self.maximum_selections_spin
        )
        self.selection_range_label = QLabel("Selections", self)
        self.question_form.addRow(self.selection_range_label, self.selection_range_row)
        self.value_range_row = self._three_field_row(
            "Min",
            self.minimum_value_spin,
            "Max",
            self.maximum_value_spin,
            "Step",
            self.step_value_spin,
        )
        self.value_range_label = QLabel("Value range", self)
        self.question_form.addRow(self.value_range_label, self.value_range_row)
        self.scale_labels_row = self._two_field_row(
            "Minimum label",
            self.minimum_label_edit,
            "Maximum label",
            self.maximum_label_edit,
        )
        self.scale_labels_label = QLabel("Scale labels", self)
        self.question_form.addRow(self.scale_labels_label, self.scale_labels_row)
        self.text_limit_label = QLabel("Maximum characters", self)
        self.question_form.addRow(self.text_limit_label, self.maximum_text_length_spin)
        branch_row = self._two_field_row(
            "If answer",
            self.branch_operator_combo,
            "value",
            self.branch_match_edit,
        )
        self.question_form.addRow("Conditional route", branch_row)
        self.question_form.addRow("Then go to step ID", self.branch_target_edit)

        editor_panel = QGroupBox("Selected question", self)
        editor_panel.setObjectName("condition_task_selected_question_group")
        editor_panel.setLayout(self.question_form)
        # The questionnaire lives inside the module editor's vertical scroll area.
        # Stack its list and editor so every field can shrink to the dialog's
        # documented minimum width without introducing hidden horizontal overflow.
        content = QVBoxLayout(self)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)
        content.addWidget(list_column)
        content.addWidget(editor_panel)

        for widget_signal in (
            self.question_id_edit.textChanged,
            self.question_kind_combo.currentIndexChanged,
            self.question_prompt_edit.textChanged,
            self.required_checkbox.toggled,
            self.options_edit.textChanged,
            self.randomize_question_options_checkbox.toggled,
            self.minimum_selections_spin.valueChanged,
            self.maximum_selections_spin.valueChanged,
            self.minimum_value_spin.valueChanged,
            self.maximum_value_spin.valueChanged,
            self.step_value_spin.valueChanged,
            self.minimum_label_edit.textChanged,
            self.maximum_label_edit.textChanged,
            self.maximum_text_length_spin.valueChanged,
            self.branch_operator_combo.currentIndexChanged,
            self.branch_match_edit.textChanged,
            self.branch_target_edit.textChanged,
        ):
            widget_signal.connect(self._store_selected)
        self.question_kind_combo.currentIndexChanged.connect(self._refresh_type_fields)
        self._set_editor_enabled(False)

    @staticmethod
    def _number_spin(object_name: str, *, minimum: float = -1_000_000.0) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(minimum, 1_000_000.0)
        spin.setDecimals(6)
        spin.setSingleStep(1.0)
        return spin

    @staticmethod
    def _two_field_row(
        first_label: str,
        first: QWidget,
        second_label: str,
        second: QWidget,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(QLabel(first_label, row))
        layout.addWidget(first, 1)
        layout.addWidget(QLabel(second_label, row))
        layout.addWidget(second, 1)
        return row

    @staticmethod
    def _three_field_row(
        first_label: str,
        first: QWidget,
        second_label: str,
        second: QWidget,
        third_label: str,
        third: QWidget,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for label, widget in (
            (first_label, first),
            (second_label, second),
            (third_label, third),
        ):
            layout.addWidget(QLabel(label, row))
            layout.addWidget(widget, 1)
        return row

    def set_questions(self, questions: list[TaskQuestionDraft]) -> None:
        self._questions = copy.deepcopy(questions)
        self._refresh_list(select_row=0 if self._questions else -1)

    def questions(self) -> list[TaskQuestionDraft]:
        self._store_selected(emit_changed=False)
        return copy.deepcopy(self._questions)

    def _add_question(self) -> None:
        kind = str(self.add_kind_combo.currentData())
        existing = {question.question_id for question in self._questions}
        question_id = _unique_id("question", existing)
        question = _default_question_draft(
            question_id=question_id,
            kind=kind,  # type: ignore[arg-type]
        )
        self._questions.append(question)
        self._refresh_list(select_row=len(self._questions) - 1)
        self.changed.emit()

    def _remove_question(self) -> None:
        row = self.question_list.currentRow()
        if row < 0:
            return
        self._questions.pop(row)
        self._refresh_list(select_row=min(row, len(self._questions) - 1))
        self.changed.emit()

    def _move_question(self, offset: int) -> None:
        row = self.question_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= len(self._questions):
            return
        self._store_selected()
        self._questions[row], self._questions[target] = (
            self._questions[target],
            self._questions[row],
        )
        self._refresh_list(select_row=target)
        self.changed.emit()

    def _refresh_list(self, *, select_row: int) -> None:
        self._syncing = True
        try:
            self.question_list.clear()
            for question in self._questions:
                label = next(label for label, kind in _QUESTION_LABELS if kind == question.kind)
                item = QListWidgetItem(f"{question.prompt or question.question_id}\n{label}")
                item.setData(Qt.ItemDataRole.UserRole, question.question_id)
                self.question_list.addItem(item)
            self.question_list.setCurrentRow(select_row)
        finally:
            self._syncing = False
        self._load_selected(select_row)

    def _load_selected(self, row: int) -> None:
        if self._syncing:
            return
        question = self._questions[row] if 0 <= row < len(self._questions) else None
        self._syncing = True
        try:
            self._set_editor_enabled(question is not None)
            if question is None:
                self.question_id_edit.clear()
                self.question_prompt_edit.clear()
                self.options_edit.clear()
                return
            self.question_id_edit.setText(question.question_id)
            self.question_kind_combo.setCurrentIndex(
                self.question_kind_combo.findData(question.kind)
            )
            self.question_prompt_edit.setPlainText(question.prompt)
            self.required_checkbox.setChecked(question.required)
            self.options_edit.setPlainText(_option_lines(question.options))
            self.randomize_question_options_checkbox.setChecked(question.randomize_options)
            self.minimum_selections_spin.setValue(
                question.minimum_selections if question.minimum_selections is not None else -1
            )
            self.maximum_selections_spin.setValue(
                question.maximum_selections if question.maximum_selections is not None else 0
            )
            self.minimum_value_spin.setValue(question.minimum_value)
            self.maximum_value_spin.setValue(question.maximum_value)
            self.step_value_spin.setValue(question.step_value)
            self.minimum_label_edit.setText(question.minimum_label)
            self.maximum_label_edit.setText(question.maximum_label)
            self.maximum_text_length_spin.setValue(question.maximum_text_length)
            self.branch_operator_combo.setCurrentIndex(
                self.branch_operator_combo.findData(question.branch_operator)
            )
            self.branch_match_edit.setText(question.branch_match_value)
            self.branch_target_edit.setText(question.branch_target_step_id)
        finally:
            self._syncing = False
        self._refresh_type_fields()

    def _store_selected(
        self,
        *_args: object,
        emit_changed: bool = True,
    ) -> None:
        if self._syncing:
            return
        row = self.question_list.currentRow()
        if row < 0 or row >= len(self._questions):
            return
        question = self._questions[row]
        kind = str(self.question_kind_combo.currentData())
        question.question_id = self.question_id_edit.text().strip()
        question.kind = kind  # type: ignore[assignment]
        question.prompt = self.question_prompt_edit.toPlainText()
        question.required = self.required_checkbox.isChecked()
        try:
            question.options = _parse_option_lines(self.options_edit.toPlainText())
        except ValueError as error:
            question.validation_error = str(error)
        else:
            question.validation_error = ""
        question.randomize_options = self.randomize_question_options_checkbox.isChecked()
        minimum_selections = self.minimum_selections_spin.value()
        maximum_selections = self.maximum_selections_spin.value()
        question.minimum_selections = None if minimum_selections < 0 else minimum_selections
        question.maximum_selections = None if maximum_selections == 0 else maximum_selections
        question.minimum_value = self.minimum_value_spin.value()
        question.maximum_value = self.maximum_value_spin.value()
        question.step_value = self.step_value_spin.value()
        question.minimum_label = self.minimum_label_edit.text()
        question.maximum_label = self.maximum_label_edit.text()
        question.maximum_text_length = self.maximum_text_length_spin.value()
        question.branch_operator = str(self.branch_operator_combo.currentData())
        question.branch_match_value = self.branch_match_edit.text().strip()
        question.branch_target_step_id = self.branch_target_edit.text().strip()
        item = self.question_list.item(row)
        label = next(label for label, item_kind in _QUESTION_LABELS if item_kind == kind)
        item.setText(f"{question.prompt or question.question_id}\n{label}")
        self._refresh_type_fields()
        if emit_changed:
            self.changed.emit()

    def _refresh_type_fields(self, *_args: object) -> None:
        kind = str(self.question_kind_combo.currentData())
        choice = kind in {"single_choice", "multiple_choice"}
        multiple = kind == "multiple_choice"
        numeric = kind in {"numeric", "rating"}
        rating = kind == "rating"
        text = kind in {"short_text", "long_text"}
        self.options_label.setVisible(choice)
        self.options_edit.setVisible(choice)
        self.randomize_question_options_checkbox.setVisible(choice)
        self.selection_range_label.setVisible(multiple)
        self.selection_range_row.setVisible(multiple)
        self.value_range_label.setVisible(numeric)
        self.value_range_row.setVisible(numeric)
        self.scale_labels_label.setVisible(rating)
        self.scale_labels_row.setVisible(rating)
        self.text_limit_label.setVisible(text)
        self.maximum_text_length_spin.setVisible(text)

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self.question_id_edit,
            self.question_kind_combo,
            self.question_prompt_edit,
            self.required_checkbox,
            self.options_edit,
            self.randomize_question_options_checkbox,
            self.minimum_selections_spin,
            self.maximum_selections_spin,
            self.minimum_value_spin,
            self.maximum_value_spin,
            self.step_value_spin,
            self.minimum_label_edit,
            self.maximum_label_edit,
            self.maximum_text_length_spin,
            self.branch_operator_combo,
            self.branch_match_edit,
            self.branch_target_edit,
        ):
            widget.setEnabled(enabled)


class TaskStepEditor(QWidget):
    """Type-specific editor for one task module draft."""

    changed = Signal(object)

    def __init__(self, project_root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("condition_task_step_editor")
        self._step: TaskStepDraft | None = None
        self._syncing = False

        self.step_id_edit = QLineEdit(self)
        self.step_id_edit.setObjectName("condition_task_step_id_edit")
        self.step_kind_combo = QComboBox(self)
        self.step_kind_combo.setObjectName("condition_task_step_kind_combo")
        for label, kind in _MODULE_LABELS:
            self.step_kind_combo.addItem(label, kind)
        self.title_edit = QLineEdit(self)
        self.title_edit.setObjectName("condition_task_step_title_edit")
        self.font_family_combo = QComboBox(self)
        self.font_family_combo.setObjectName("condition_task_font_family_combo")
        for font_family in TaskFontFamily:
            self.font_family_combo.addItem(font_family.value, font_family.value)
        self.prompt_edit = QTextEdit(self)
        self.prompt_edit.setObjectName("condition_task_prompt_edit")
        self.prompt_edit.setFixedHeight(72)
        self.prompt_geometry_checkbox = QCheckBox(
            "Use exact prompt position and height",
            self,
        )
        self.prompt_geometry_checkbox.setObjectName("condition_task_prompt_geometry_checkbox")
        self.prompt_unit_combo = QComboBox(self)
        self.prompt_unit_combo.setObjectName("condition_task_prompt_unit_combo")
        self.prompt_unit_combo.addItem("Degrees of visual angle", "degrees")
        self.prompt_unit_combo.addItem("Fraction of window height", "window_height_fraction")
        self.prompt_x_spin = self._geometry_spin("condition_task_prompt_x_spin")
        self.prompt_y_spin = self._geometry_spin("condition_task_prompt_y_spin")
        self.prompt_height_spin = self._geometry_spin(
            "condition_task_prompt_height_spin",
            minimum=0.0,
        )
        self.prompt_height_spin.setSpecialValueText("Automatic")
        prompt_geometry_row = QuestionnaireEditor._three_field_row(
            "X",
            self.prompt_x_spin,
            "Y",
            self.prompt_y_spin,
            "Height",
            self.prompt_height_spin,
        )
        self.prompt_geometry_row = prompt_geometry_row
        self.prompt_geometry_checkbox.toggled.connect(self._refresh_prompt_geometry)

        common_group = QGroupBox("Module", self)
        common_group.setObjectName("condition_task_common_group")
        common_form = QFormLayout(common_group)
        common_form.setContentsMargins(10, 8, 10, 8)
        common_form.setHorizontalSpacing(10)
        common_form.setVerticalSpacing(6)
        common_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        common_form.addRow("Stable ID", self.step_id_edit)
        common_form.addRow("Module type", self.step_kind_combo)
        common_form.addRow("Display title", self.title_edit)
        common_form.addRow("Font family", self.font_family_combo)
        common_form.addRow("Prompt / content", self.prompt_edit)
        common_form.addRow("", self.prompt_geometry_checkbox)
        common_form.addRow("Prompt units", self.prompt_unit_combo)
        common_form.addRow("Prompt geometry", prompt_geometry_row)

        self.maximum_attempts_spin = QSpinBox(self)
        self.maximum_attempts_spin.setObjectName("condition_task_maximum_attempts_spin")
        self.maximum_attempts_spin.setRange(1, 1000)
        self.retry_invalid_checkbox = QCheckBox("Retry invalid responses", self)
        self.retry_invalid_checkbox.setObjectName("condition_task_retry_invalid_checkbox")
        self.retry_incorrect_checkbox = QCheckBox("Retry incorrect responses", self)
        self.retry_incorrect_checkbox.setObjectName("condition_task_retry_incorrect_checkbox")
        attempt_group = QGroupBox("Attempts and retries", self)
        attempt_group.setObjectName("condition_task_attempt_group")
        attempt_form = QFormLayout(attempt_group)
        attempt_form.addRow("Maximum attempts", self.maximum_attempts_spin)
        attempt_form.addRow("", self.retry_invalid_checkbox)
        attempt_form.addRow("", self.retry_incorrect_checkbox)

        self.type_stack = QStackedWidget(self)
        self.type_stack.setObjectName("condition_task_type_stack")
        self._type_pages: dict[str, QWidget] = {}

        self.continue_key_edit = QLineEdit(self)
        self.continue_key_edit.setObjectName("condition_task_continue_key_edit")
        self.continue_key_edit.setPlaceholderText("space")
        self.advance_keys_edit = QLineEdit(self)
        self.advance_keys_edit.setObjectName("condition_task_advance_keys_edit")
        self.advance_keys_edit.setPlaceholderText("space, y, n, left, right")
        self.timeout_checkbox = QCheckBox("Enable response timeout", self)
        self.timeout_checkbox.setObjectName("condition_task_timeout_checkbox")
        self.timeout_spin = QDoubleSpinBox(self)
        self.timeout_spin.setObjectName("condition_task_timeout_spin")
        self.timeout_spin.setRange(0.001, 86_400.0)
        self.timeout_spin.setDecimals(3)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setEnabled(False)
        self.timeout_checkbox.toggled.connect(self.timeout_spin.setEnabled)
        self.auto_advance_checkbox = QCheckBox("Also allow timed auto-advance", self)
        self.auto_advance_checkbox.setObjectName("condition_task_auto_advance_checkbox")
        self.auto_advance_spin = QDoubleSpinBox(self)
        self.auto_advance_spin.setObjectName("condition_task_auto_advance_spin")
        self.auto_advance_spin.setRange(0.001, 86_400.0)
        self.auto_advance_spin.setDecimals(3)
        self.auto_advance_spin.setSuffix(" s")
        self.auto_advance_spin.setEnabled(False)
        self.auto_advance_checkbox.toggled.connect(self.auto_advance_spin.setEnabled)
        self.advance_group = QGroupBox("Advance and timing", self)
        self.advance_group.setObjectName("condition_task_advance_group")
        advance_form = QFormLayout(self.advance_group)
        advance_form.addRow("Primary continue key", self.continue_key_edit)
        advance_form.addRow("Additional accepted keys", self.advance_keys_edit)
        advance_form.addRow("", self.timeout_checkbox)
        advance_form.addRow("Timeout", self.timeout_spin)
        advance_form.addRow("", self.auto_advance_checkbox)
        advance_form.addRow("Auto-advance", self.auto_advance_spin)
        instruction_page = QWidget(self)
        instruction_layout = QVBoxLayout(instruction_page)
        instruction_layout.setContentsMargins(0, 0, 0, 0)
        instruction_note = QLabel(
            "Show participant-facing content, then continue by key or optional auto-advance.",
            instruction_page,
        )
        instruction_note.setWordWrap(True)
        instruction_layout.addWidget(instruction_note)
        instruction_layout.addStretch(1)
        self._add_type_page("instruction", instruction_page)

        self.layout_mode_combo = QComboBox(self)
        self.layout_mode_combo.setObjectName("condition_task_layout_mode_combo")
        self.layout_mode_combo.addItem("Responsive grid", "responsive_grid")
        self.layout_mode_combo.addItem("Exact PsychoPy layout", "exact")
        self.columns_spin = QSpinBox(self)
        self.columns_spin.setObjectName("condition_task_grid_columns_spin")
        self.columns_spin.setRange(0, 12)
        self.columns_spin.setSpecialValueText("Auto")
        self.option_table = TaskOptionTable(project_root, self)
        self.add_text_item_button = QPushButton("Add Text Item", self)
        self.add_text_item_button.setObjectName("condition_task_add_text_item_button")
        self.add_text_item_button.clicked.connect(self.option_table.add_text_option)
        mark_secondary_action(self.add_text_item_button)
        self.add_image_item_button = QPushButton("Add Image...", self)
        self.add_image_item_button.setObjectName("condition_task_add_image_item_button")
        self.add_image_item_button.clicked.connect(lambda: self.option_table.add_image_option(self))
        mark_secondary_action(self.add_image_item_button)
        self.replace_image_button = QPushButton("Replace Image...", self)
        self.replace_image_button.setObjectName("condition_task_replace_image_button")
        self.replace_image_button.clicked.connect(
            lambda: self.option_table.replace_selected_image(self)
        )
        mark_secondary_action(self.replace_image_button)
        self.remove_item_button = QPushButton("Remove Item", self)
        self.remove_item_button.setObjectName("condition_task_remove_item_button")
        self.remove_item_button.clicked.connect(self.option_table.remove_selected)
        mark_destructive_action(self.remove_item_button)
        self.item_up_button = QPushButton("Move Up", self)
        self.item_up_button.setObjectName("condition_task_item_up_button")
        self.item_up_button.clicked.connect(lambda: self.option_table.move_selected(-1))
        mark_secondary_action(self.item_up_button)
        self.item_down_button = QPushButton("Move Down", self)
        self.item_down_button.setObjectName("condition_task_item_down_button")
        self.item_down_button.clicked.connect(lambda: self.option_table.move_selected(1))
        mark_secondary_action(self.item_down_button)
        item_actions = QGridLayout()
        item_actions.setContentsMargins(0, 0, 0, 0)
        item_actions.setSpacing(6)
        item_actions.addWidget(self.add_text_item_button, 0, 0)
        item_actions.addWidget(self.add_image_item_button, 0, 1)
        item_actions.addWidget(self.replace_image_button, 0, 2)
        item_actions.addWidget(self.item_up_button, 1, 0)
        item_actions.addWidget(self.item_down_button, 1, 1)
        item_actions.addWidget(self.remove_item_button, 1, 2)

        self.repeat_count_spin = QSpinBox(self)
        self.repeat_count_spin.setObjectName("condition_task_repeat_count_spin")
        self.repeat_count_spin.setRange(1, 1000)
        self.one_choice_checkbox = QCheckBox(
            "End each repetition after one valid selectable choice",
            self,
        )
        self.one_choice_checkbox.setObjectName("condition_task_one_choice_checkbox")
        self.choice_minimum_spin = QSpinBox(self)
        self.choice_minimum_spin.setObjectName("condition_task_choice_minimum_spin")
        self.choice_minimum_spin.setRange(0, 1000)
        self.choice_maximum_spin = QSpinBox(self)
        self.choice_maximum_spin.setObjectName("condition_task_choice_maximum_spin")
        self.choice_maximum_spin.setRange(1, 1000)
        self.duplicate_choices_checkbox = QCheckBox(
            "Allow the same choice across repetitions",
            self,
        )
        self.duplicate_choices_checkbox.setObjectName("condition_task_duplicate_choices_checkbox")
        self.randomize_options_checkbox = QCheckBox("Randomize display-item order", self)
        self.randomize_options_checkbox.setObjectName("condition_task_randomize_options_checkbox")
        self.submission_mode_combo = QComboBox(self)
        self.submission_mode_combo.setObjectName("condition_task_submission_mode_combo")
        self.submission_mode_combo.addItem("Complete immediately", "immediate")
        self.submission_mode_combo.addItem("Require a Submit action", "explicit")
        common_form.addRow("Response completion", self.submission_mode_combo)
        self.submission_mode_label = common_form.labelForField(self.submission_mode_combo)
        self.show_footer_checkbox = QCheckBox(
            "Show participant key / response footer",
            self,
        )
        self.show_footer_checkbox.setObjectName("condition_task_show_footer_checkbox")
        common_form.addRow("", self.show_footer_checkbox)
        choice_behavior = QGroupBox("Choice behavior", self)
        choice_behavior.setObjectName("condition_task_choice_behavior_group")
        choice_form = QFormLayout(choice_behavior)
        choice_form.addRow("Repetitions", self.repeat_count_spin)
        choice_form.addRow("", self.one_choice_checkbox)
        choice_form.addRow(
            "Selection limits",
            QuestionnaireEditor._two_field_row(
                "Minimum",
                self.choice_minimum_spin,
                "Maximum",
                self.choice_maximum_spin,
            ),
        )
        choice_form.addRow("", self.duplicate_choices_checkbox)
        choice_form.addRow("", self.randomize_options_checkbox)
        feedback_note = QLabel(
            "Add a Timed Feedback step after this step for unconditional feedback. "
            "Set the module repeat count to repeat the complete choice + feedback group.",
            choice_behavior,
        )
        feedback_note.setObjectName("condition_task_choice_feedback_note")
        feedback_note.setWordWrap(True)
        choice_form.addRow("", feedback_note)
        self.choice_behavior_group = choice_behavior

        item_page = QWidget(self)
        item_layout = QVBoxLayout(item_page)
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(6)
        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel("Layout", item_page))
        layout_row.addWidget(self.layout_mode_combo, 1)
        layout_row.addWidget(QLabel("Columns", item_page))
        layout_row.addWidget(self.columns_spin)
        item_layout.addLayout(layout_row)
        exact_note = QLabel(
            "Exact mode uses center-origin coordinates. Choose degrees of visual angle "
            "or fraction of window height per item; positive Y is above center. Every "
            "item needs a height and every image needs a width.",
            item_page,
        )
        exact_note.setObjectName("condition_task_exact_layout_note")
        exact_note.setWordWrap(True)
        item_layout.addWidget(exact_note)
        item_layout.addWidget(self.option_table)
        item_layout.addLayout(item_actions)
        item_layout.addWidget(choice_behavior)
        self._add_type_page("study", item_page)
        self._type_pages["choice_grid"] = item_page

        self.questionnaire_editor = QuestionnaireEditor(self)
        self._add_type_page("questionnaire", self.questionnaire_editor)

        self.raw_keys_edit = QLineEdit(self)
        self.raw_keys_edit.setObjectName("condition_task_raw_keys_edit")
        self.raw_keys_edit.setPlaceholderText("y, n, left, right, space")
        self.raw_timeout_checkbox = QCheckBox("Enable response timeout", self)
        self.raw_timeout_checkbox.setObjectName("condition_task_raw_timeout_checkbox")
        self.raw_timeout_spin = QDoubleSpinBox(self)
        self.raw_timeout_spin.setObjectName("condition_task_raw_timeout_spin")
        self.raw_timeout_spin.setRange(0.001, 86_400.0)
        self.raw_timeout_spin.setDecimals(3)
        self.raw_timeout_spin.setSuffix(" s")
        self.raw_timeout_spin.setEnabled(False)
        self.raw_timeout_checkbox.toggled.connect(self.raw_timeout_spin.setEnabled)
        raw_page = QWidget(self)
        raw_form = QFormLayout(raw_page)
        raw_form.addRow("Accepted keys", self.raw_keys_edit)
        raw_form.addRow("", self.raw_timeout_checkbox)
        raw_form.addRow("Timeout", self.raw_timeout_spin)
        self._add_type_page("raw_key", raw_page)

        self.duration_spin = QDoubleSpinBox(self)
        self.duration_spin.setObjectName("condition_task_duration_spin")
        self.duration_spin.setRange(0.001, 86_400.0)
        self.duration_spin.setDecimals(3)
        self.duration_spin.setSuffix(" s")
        feedback_page = QWidget(self)
        feedback_form = QFormLayout(feedback_page)
        feedback_form.addRow("Fixed duration", self.duration_spin)
        self._add_type_page("timed_feedback", feedback_page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(common_group)
        layout.addWidget(attempt_group)
        layout.addWidget(self.type_stack)
        layout.addWidget(self.advance_group)
        layout.addStretch(1)

        for widget_signal in (
            self.step_id_edit.textChanged,
            self.step_kind_combo.currentIndexChanged,
            self.title_edit.textChanged,
            self.font_family_combo.currentIndexChanged,
            self.prompt_edit.textChanged,
            self.prompt_geometry_checkbox.toggled,
            self.prompt_unit_combo.currentIndexChanged,
            self.prompt_x_spin.valueChanged,
            self.prompt_y_spin.valueChanged,
            self.prompt_height_spin.valueChanged,
            self.maximum_attempts_spin.valueChanged,
            self.retry_invalid_checkbox.toggled,
            self.retry_incorrect_checkbox.toggled,
            self.advance_keys_edit.textChanged,
            self.continue_key_edit.textChanged,
            self.timeout_checkbox.toggled,
            self.timeout_spin.valueChanged,
            self.auto_advance_checkbox.toggled,
            self.auto_advance_spin.valueChanged,
            self.layout_mode_combo.currentIndexChanged,
            self.columns_spin.valueChanged,
            self.option_table.changed,
            self.repeat_count_spin.valueChanged,
            self.one_choice_checkbox.toggled,
            self.choice_minimum_spin.valueChanged,
            self.choice_maximum_spin.valueChanged,
            self.duplicate_choices_checkbox.toggled,
            self.randomize_options_checkbox.toggled,
            self.submission_mode_combo.currentIndexChanged,
            self.show_footer_checkbox.toggled,
            self.questionnaire_editor.changed,
            self.raw_keys_edit.textChanged,
            self.raw_timeout_checkbox.toggled,
            self.raw_timeout_spin.valueChanged,
            self.duration_spin.valueChanged,
        ):
            widget_signal.connect(self._store)
        self.step_kind_combo.currentIndexChanged.connect(self._refresh_kind_page)
        self.layout_mode_combo.currentIndexChanged.connect(self._refresh_layout_fields)
        self.setEnabled(False)

    def _add_type_page(self, kind: str, page: QWidget) -> None:
        self._type_pages[kind] = page
        self.type_stack.addWidget(page)

    def set_step(self, step: TaskStepDraft | None) -> None:
        self._step = copy.deepcopy(step) if step is not None else None
        self._syncing = True
        try:
            self.setEnabled(step is not None)
            if step is None:
                self.step_id_edit.clear()
                self.title_edit.clear()
                self.prompt_edit.clear()
                self.option_table.set_options([])
                self.questionnaire_editor.set_questions([])
                return
            self.step_id_edit.setText(step.step_id)
            self.step_kind_combo.setCurrentIndex(self.step_kind_combo.findData(step.kind))
            self.title_edit.setText(step.title)
            self.font_family_combo.setCurrentIndex(
                self.font_family_combo.findData(step.font_family)
            )
            self.prompt_edit.setPlainText(step.prompt)
            prompt_exact = (
                step.prompt_height is not None
                or bool(step.prompt_x or step.prompt_y)
                or step.prompt_unit != "degrees"
            )
            self.prompt_geometry_checkbox.setChecked(prompt_exact)
            self.prompt_unit_combo.setCurrentIndex(
                self.prompt_unit_combo.findData(step.prompt_unit)
            )
            self.prompt_x_spin.setValue(step.prompt_x)
            self.prompt_y_spin.setValue(step.prompt_y)
            self.prompt_height_spin.setValue(step.prompt_height or 0.0)
            self.maximum_attempts_spin.setValue(step.maximum_attempts)
            self.retry_invalid_checkbox.setChecked(step.retry_on_invalid)
            self.retry_incorrect_checkbox.setChecked(step.retry_on_incorrect)
            self.continue_key_edit.setText(step.continue_key or "")
            self.advance_keys_edit.setText(_format_keys(step.advance_keys))
            self.timeout_checkbox.setChecked(step.timeout_seconds is not None)
            self.timeout_spin.setValue(step.timeout_seconds or 1.0)
            self.auto_advance_checkbox.setChecked(
                step.duration_seconds is not None and step.kind in {"instruction", "study"}
            )
            self.auto_advance_spin.setValue(step.duration_seconds or 1.0)
            self.layout_mode_combo.setCurrentIndex(
                self.layout_mode_combo.findData(step.layout_mode)
            )
            self.columns_spin.setValue(step.columns or 0)
            self.option_table.set_options(step.options)
            self.repeat_count_spin.setValue(step.repeat_count)
            self.one_choice_checkbox.setChecked(step.complete_after_one_valid_choice)
            self.choice_minimum_spin.setValue(step.minimum_selections)
            self.choice_maximum_spin.setValue(step.maximum_selections)
            self.duplicate_choices_checkbox.setChecked(step.allow_duplicate_choices_across_repeats)
            self.randomize_options_checkbox.setChecked(step.randomize_options)
            self.submission_mode_combo.setCurrentIndex(
                self.submission_mode_combo.findData(step.submission_mode)
            )
            self.show_footer_checkbox.setChecked(step.show_footer)
            self.questionnaire_editor.set_questions(step.questions)
            self.raw_keys_edit.setText(_format_keys(step.advance_keys))
            self.raw_timeout_checkbox.setChecked(step.timeout_seconds is not None)
            self.raw_timeout_spin.setValue(step.timeout_seconds or 1.0)
            self.duration_spin.setValue(step.duration_seconds or 1.0)
        finally:
            self._syncing = False
        self._refresh_kind_page()
        self._refresh_layout_fields()
        self._refresh_prompt_geometry()

    def step(self) -> TaskStepDraft | None:
        self._store(emit_changed=False)
        return copy.deepcopy(self._step)

    def _store(self, *_args: object, emit_changed: bool = True) -> None:
        if self._syncing or self._step is None:
            return
        step = self._step
        kind = str(self.step_kind_combo.currentData())
        previous_kind = step.kind
        step.step_id = self.step_id_edit.text().strip()
        step.kind = kind  # type: ignore[assignment]
        if kind != previous_kind:
            step.require_response = kind in {
                "choice_grid",
                "questionnaire",
                "raw_key",
            }
            step.continue_key = "space" if kind in {"instruction", "study"} else None
        step.title = self.title_edit.text()
        step.font_family = str(self.font_family_combo.currentData())
        step.prompt = self.prompt_edit.toPlainText()
        if self.prompt_geometry_checkbox.isChecked():
            step.prompt_x = self.prompt_x_spin.value()
            step.prompt_y = self.prompt_y_spin.value()
            step.prompt_unit = str(self.prompt_unit_combo.currentData())
            step.prompt_height = self.prompt_height_spin.value() or None
        else:
            step.prompt_x = 0.0
            step.prompt_y = 0.0
            step.prompt_height = None
        step.maximum_attempts = self.maximum_attempts_spin.value()
        step.retry_on_invalid = self.retry_invalid_checkbox.isChecked()
        step.retry_on_incorrect = self.retry_incorrect_checkbox.isChecked()
        if kind == "raw_key":
            step.advance_keys = _split_keys(self.raw_keys_edit.text())
            step.timeout_seconds = (
                self.raw_timeout_spin.value() if self.raw_timeout_checkbox.isChecked() else None
            )
        else:
            continue_keys = _split_keys(self.continue_key_edit.text())
            step.continue_key = continue_keys[0] if continue_keys else None
            step.advance_keys = _split_keys(self.advance_keys_edit.text())
            step.timeout_seconds = (
                self.timeout_spin.value() if self.timeout_checkbox.isChecked() else None
            )
        step.layout_mode = str(self.layout_mode_combo.currentData())
        columns = self.columns_spin.value()
        step.columns = columns or None
        try:
            step.options = self.option_table.options()
        except ValueError as error:
            step.validation_error = str(error)
        else:
            step.validation_error = ""
        step.repeat_count = self.repeat_count_spin.value()
        step.complete_after_one_valid_choice = self.one_choice_checkbox.isChecked()
        step.minimum_selections = self.choice_minimum_spin.value()
        step.maximum_selections = self.choice_maximum_spin.value()
        step.allow_duplicate_choices_across_repeats = self.duplicate_choices_checkbox.isChecked()
        step.randomize_options = self.randomize_options_checkbox.isChecked()
        step.submission_mode = str(self.submission_mode_combo.currentData())
        step.show_footer = self.show_footer_checkbox.isChecked()
        step.questions = self.questionnaire_editor.questions()
        if kind == "timed_feedback":
            step.duration_seconds = self.duration_spin.value()
        elif kind in {"instruction", "study"} and self.auto_advance_checkbox.isChecked():
            step.duration_seconds = self.auto_advance_spin.value()
        elif kind in {"instruction", "study"}:
            step.duration_seconds = None
        self._refresh_kind_page()
        self._refresh_layout_fields()
        if emit_changed:
            self.changed.emit(copy.deepcopy(step))

    def _refresh_kind_page(self, *_args: object) -> None:
        kind = str(self.step_kind_combo.currentData())
        page = self._type_pages.get(kind)
        if page is not None:
            self.type_stack.setCurrentWidget(page)
        self.choice_behavior_group.setVisible(kind == "choice_grid")
        timed_advance = kind in {"instruction", "study"}
        self.advance_group.setVisible(timed_advance)
        self.retry_incorrect_checkbox.setVisible(kind in {"choice_grid", "questionnaire"})
        has_submission = kind in {"choice_grid", "questionnaire"}
        self.submission_mode_combo.setVisible(has_submission)
        if self.submission_mode_label is not None:
            self.submission_mode_label.setVisible(has_submission)

    def _refresh_layout_fields(self, *_args: object) -> None:
        responsive = self.layout_mode_combo.currentData() == "responsive_grid"
        self.columns_spin.setEnabled(responsive)

    def _refresh_prompt_geometry(self, *_args: object) -> None:
        enabled = self.prompt_geometry_checkbox.isChecked()
        self.prompt_unit_combo.setEnabled(enabled)
        self.prompt_geometry_row.setEnabled(enabled)

    @staticmethod
    def _geometry_spin(
        object_name: str,
        *,
        minimum: float = -1_000_000.0,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName(object_name)
        spin.setRange(minimum, 1_000_000.0)
        spin.setDecimals(6)
        spin.setSingleStep(0.25)
        return spin


class TaskModuleEditor(QWidget):
    """Edit one reusable module and its ordered sequence of participant steps."""

    changed = Signal(object)
    selection_changed = Signal(object)

    def __init__(
        self,
        project_root: Path,
        *,
        allow_replaces_start_gate: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("condition_task_module_editor")
        self._module: TaskModuleDraft | None = None
        self._syncing = False
        self._allow_replaces_start_gate = allow_replaces_start_gate

        self.module_id_edit = QLineEdit(self)
        self.module_id_edit.setObjectName("condition_task_module_id_edit")
        self.module_title_edit = QLineEdit(self)
        self.module_title_edit.setObjectName("condition_task_module_title_edit")
        self.occurrence_combo = QComboBox(self)
        self.occurrence_combo.setObjectName("condition_task_occurrence_combo")
        for label, occurrence in _OCCURRENCE_LABELS:
            self.occurrence_combo.addItem(label, occurrence)
        self.module_repeat_count_spin = QSpinBox(self)
        self.module_repeat_count_spin.setObjectName("condition_task_module_repeat_count_spin")
        self.module_repeat_count_spin.setRange(1, 1000)
        self.module_repeat_count_spin.setToolTip(
            "Repeat the complete ordered step group. For example, a choice followed by "
            "feedback repeated four times runs [choice, feedback] four times."
        )
        self.replaces_start_gate_checkbox = QCheckBox(
            "This module replaces the standard condition start screen",
            self,
        )
        self.replaces_start_gate_checkbox.setObjectName(
            "condition_task_replaces_start_gate_checkbox"
        )
        self.replaces_start_gate_checkbox.setToolTip(
            "Use when this pre-condition module already provides the participant's "
            "ready/reminder screen, avoiding a duplicate standard transition."
        )
        self.replaces_start_gate_checkbox.setVisible(allow_replaces_start_gate)
        module_form = QFormLayout()
        module_form.setContentsMargins(0, 0, 0, 0)
        module_form.setHorizontalSpacing(10)
        module_form.setVerticalSpacing(6)
        module_form.addRow("Reusable module ID", self.module_id_edit)
        module_form.addRow("Module name", self.module_title_edit)
        module_form.addRow("Run this module", self.occurrence_combo)
        module_form.addRow("Repeat complete module", self.module_repeat_count_spin)
        module_form.addRow("", self.replaces_start_gate_checkbox)

        module_group = QGroupBox("Module binding", self)
        module_group.setObjectName("condition_task_module_binding_group")
        module_group.setLayout(module_form)

        self.step_list = QListWidget(self)
        self.step_list.setObjectName("condition_task_module_step_list")
        self.step_list.setMinimumHeight(110)
        self.step_list.currentRowChanged.connect(self._load_selected_step)
        self.add_step_kind_combo = QComboBox(self)
        self.add_step_kind_combo.setObjectName("condition_task_add_step_kind_combo")
        for label, kind in _MODULE_LABELS:
            self.add_step_kind_combo.addItem(label, kind)
        self.add_step_button = QPushButton("Add Step", self)
        self.add_step_button.setObjectName("condition_task_add_step_button")
        self.add_step_button.clicked.connect(self._add_step)
        mark_secondary_action(self.add_step_button)
        self.step_up_button = QPushButton("Up", self)
        self.step_up_button.setObjectName("condition_task_step_up_button")
        self.step_up_button.clicked.connect(lambda: self._move_step(-1))
        mark_secondary_action(self.step_up_button)
        self.step_down_button = QPushButton("Down", self)
        self.step_down_button.setObjectName("condition_task_step_down_button")
        self.step_down_button.clicked.connect(lambda: self._move_step(1))
        mark_secondary_action(self.step_down_button)
        self.duplicate_step_button = QPushButton("Duplicate", self)
        self.duplicate_step_button.setObjectName("condition_task_duplicate_step_button")
        self.duplicate_step_button.clicked.connect(self._duplicate_step)
        mark_secondary_action(self.duplicate_step_button)
        self.remove_step_button = QPushButton("Remove", self)
        self.remove_step_button.setObjectName("condition_task_remove_step_button")
        self.remove_step_button.clicked.connect(self._remove_step)
        mark_destructive_action(self.remove_step_button)
        step_actions = QGridLayout()
        step_actions.setContentsMargins(0, 0, 0, 0)
        step_actions.setSpacing(6)
        step_actions.addWidget(self.add_step_kind_combo, 0, 0, 1, 2)
        step_actions.addWidget(self.add_step_button, 0, 2)
        step_actions.addWidget(self.duplicate_step_button, 1, 0)
        step_actions.addWidget(self.step_up_button, 1, 1)
        step_actions.addWidget(self.step_down_button, 1, 2)
        step_actions.addWidget(self.remove_step_button, 2, 0, 1, 3)

        steps_group = QGroupBox("Ordered steps", self)
        steps_group.setObjectName("condition_task_module_steps_group")
        steps_layout = QVBoxLayout(steps_group)
        steps_layout.setContentsMargins(8, 8, 8, 8)
        steps_layout.setSpacing(6)
        steps_layout.addWidget(self.step_list)
        steps_layout.addLayout(step_actions)

        self.step_editor = TaskStepEditor(project_root, self)
        self.step_editor.changed.connect(self._store_selected_step)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        layout.addWidget(module_group)
        layout.addWidget(steps_group)
        layout.addWidget(self.step_editor)
        layout.addStretch(1)

        for signal in (
            self.module_id_edit.textChanged,
            self.module_title_edit.textChanged,
            self.occurrence_combo.currentIndexChanged,
            self.module_repeat_count_spin.valueChanged,
            self.replaces_start_gate_checkbox.toggled,
        ):
            signal.connect(self._store_module_header)
        self.setEnabled(False)

    def set_module(self, module: TaskModuleDraft | None) -> None:
        self._module = copy.deepcopy(module) if module is not None else None
        self._syncing = True
        try:
            self.setEnabled(module is not None)
            if module is None:
                self.module_id_edit.clear()
                self.module_title_edit.clear()
                self.step_list.clear()
                self.step_editor.set_step(None)
                return
            self.module_id_edit.setText(module.module_id)
            self.module_title_edit.setText(module.title)
            self.occurrence_combo.setCurrentIndex(self.occurrence_combo.findData(module.occurrence))
            self.module_repeat_count_spin.setValue(module.repeat_count)
            self.replaces_start_gate_checkbox.setChecked(
                module.replaces_condition_start_gate if self._allow_replaces_start_gate else False
            )
        finally:
            self._syncing = False
        self._refresh_step_list(select_row=0 if module and module.steps else -1)

    def module(self) -> TaskModuleDraft | None:
        self._store_module_header(emit_changed=False)
        row = self.step_list.currentRow()
        selected = self.step_editor.step()
        if self._module is not None and selected is not None and 0 <= row < len(self._module.steps):
            self._module.steps[row] = selected
        return copy.deepcopy(self._module)

    def _store_module_header(
        self,
        *_args: object,
        emit_changed: bool = True,
    ) -> None:
        if self._syncing or self._module is None:
            return
        self._module.module_id = self.module_id_edit.text().strip()
        self._module.title = self.module_title_edit.text()
        self._module.occurrence = str(self.occurrence_combo.currentData())
        self._module.repeat_count = self.module_repeat_count_spin.value()
        self._module.replaces_condition_start_gate = (
            self._allow_replaces_start_gate and self.replaces_start_gate_checkbox.isChecked()
        )
        if emit_changed:
            self.changed.emit(copy.deepcopy(self._module))

    def _add_step(self) -> None:
        if self._module is None:
            return
        self._capture_selected_step()
        kind = str(self.add_step_kind_combo.currentData())
        existing = {step.step_id for step in self._module.steps}
        step_id = _unique_id(kind.replace("_", "-"), existing)
        title = next(label for label, item_kind in _MODULE_LABELS if item_kind == kind)
        step = _new_task_step_draft(step_id=step_id, kind=kind, title=title)
        self._module.steps.append(step)
        self._refresh_step_list(select_row=len(self._module.steps) - 1)
        self.changed.emit(copy.deepcopy(self._module))

    def _duplicate_step(self) -> None:
        if self._module is None:
            return
        row = self.step_list.currentRow()
        if row < 0:
            return
        self._capture_selected_step()
        duplicate = copy.deepcopy(self._module.steps[row])
        duplicate.step_id = _unique_id(
            f"{duplicate.step_id}-copy",
            {step.step_id for step in self._module.steps},
        )
        duplicate.title = f"{duplicate.title} Copy"
        self._module.steps.insert(row + 1, duplicate)
        self._refresh_step_list(select_row=row + 1)
        self.changed.emit(copy.deepcopy(self._module))

    def _remove_step(self) -> None:
        if self._module is None:
            return
        row = self.step_list.currentRow()
        if row < 0:
            return
        self._module.steps.pop(row)
        self._refresh_step_list(select_row=min(row, len(self._module.steps) - 1))
        self.changed.emit(copy.deepcopy(self._module))

    def _move_step(self, offset: int) -> None:
        if self._module is None:
            return
        row = self.step_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= len(self._module.steps):
            return
        self._capture_selected_step()
        self._module.steps[row], self._module.steps[target] = (
            self._module.steps[target],
            self._module.steps[row],
        )
        self._refresh_step_list(select_row=target)
        self.changed.emit(copy.deepcopy(self._module))

    def _capture_selected_step(self) -> None:
        if self._module is None:
            return
        row = self.step_list.currentRow()
        selected = self.step_editor.step()
        if selected is not None and 0 <= row < len(self._module.steps):
            self._module.steps[row] = selected

    def _refresh_step_list(self, *, select_row: int) -> None:
        self._syncing = True
        try:
            self.step_list.clear()
            for step in self._module.steps if self._module is not None else []:
                label = next(label for label, kind in _MODULE_LABELS if kind == step.kind)
                item = QListWidgetItem(f"{step.title or step.step_id}\n{label}")
                item.setData(Qt.ItemDataRole.UserRole, step.step_id)
                item.setToolTip(f"Stable ID: {step.step_id}")
                self.step_list.addItem(item)
            self.step_list.setCurrentRow(select_row)
        finally:
            self._syncing = False
        self._load_selected_step(select_row)

    def _load_selected_step(self, row: int) -> None:
        if self._syncing:
            return
        step = (
            self._module.steps[row]
            if self._module is not None and 0 <= row < len(self._module.steps)
            else None
        )
        self.step_editor.set_step(step)
        self.selection_changed.emit(copy.deepcopy(step))

    def _store_selected_step(self, step: TaskStepDraft) -> None:
        if self._syncing or self._module is None:
            return
        row = self.step_list.currentRow()
        if row < 0 or row >= len(self._module.steps):
            return
        self._module.steps[row] = copy.deepcopy(step)
        item = self.step_list.item(row)
        label = next(label for label, kind in _MODULE_LABELS if kind == step.kind)
        item.setText(f"{step.title or step.step_id}\n{label}")
        item.setData(Qt.ItemDataRole.UserRole, step.step_id)
        item.setToolTip(f"Stable ID: {step.step_id}")
        self.selection_changed.emit(copy.deepcopy(step))
        self.changed.emit(copy.deepcopy(self._module))


class TaskPhaseEditor(QWidget):
    """Ordered reusable-module bindings for one condition phase."""

    changed = Signal()
    selection_changed = Signal(object)

    def __init__(
        self,
        project_root: Path,
        *,
        phase_label: str,
        reserved_module_ids: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        prefix = phase_label.lower()
        self.setObjectName(f"condition_task_{prefix}_phase_editor")
        self._modules: list[TaskModuleDraft] = []
        self._syncing = False
        self._reserved_module_ids = set(reserved_module_ids or ())

        self.module_list = QListWidget(self)
        self.module_list.setObjectName(f"condition_task_{prefix}_module_list")
        self.module_list.setMinimumWidth(220)
        self.module_list.currentRowChanged.connect(self._load_selected)
        self.add_kind_combo = QComboBox(self)
        self.add_kind_combo.setObjectName(f"condition_task_{prefix}_add_kind_combo")
        for label, kind in _MODULE_LABELS:
            self.add_kind_combo.addItem(label, kind)
        self.add_button = QPushButton("Add Module", self)
        self.add_button.setObjectName(f"condition_task_{prefix}_add_button")
        self.add_button.clicked.connect(self._add_module)
        mark_secondary_action(self.add_button)
        self.duplicate_button = QPushButton("Duplicate", self)
        self.duplicate_button.setObjectName(f"condition_task_{prefix}_duplicate_button")
        self.duplicate_button.clicked.connect(self._duplicate_module)
        mark_secondary_action(self.duplicate_button)
        self.up_button = QPushButton("Up", self)
        self.up_button.setObjectName(f"condition_task_{prefix}_up_button")
        self.up_button.clicked.connect(lambda: self._move_module(-1))
        mark_secondary_action(self.up_button)
        self.down_button = QPushButton("Down", self)
        self.down_button.setObjectName(f"condition_task_{prefix}_down_button")
        self.down_button.clicked.connect(lambda: self._move_module(1))
        mark_secondary_action(self.down_button)
        self.remove_button = QPushButton("Remove", self)
        self.remove_button.setObjectName(f"condition_task_{prefix}_remove_button")
        self.remove_button.clicked.connect(self._remove_module)
        mark_destructive_action(self.remove_button)

        actions = QGridLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        actions.addWidget(self.add_kind_combo, 0, 0, 1, 2)
        actions.addWidget(self.add_button, 0, 2)
        actions.addWidget(self.duplicate_button, 1, 0)
        actions.addWidget(self.up_button, 1, 1)
        actions.addWidget(self.down_button, 1, 2)
        actions.addWidget(self.remove_button, 2, 0, 1, 3)

        list_panel = QWidget(self)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        list_layout.addWidget(self.module_list, 1)
        list_layout.addLayout(actions)

        self.module_editor = TaskModuleEditor(
            project_root,
            allow_replaces_start_gate=phase_label.casefold() == "pre",
            parent=self,
        )
        self.module_editor.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.module_editor.changed.connect(self._store_selected)
        self.module_editor.selection_changed.connect(self.selection_changed)
        scroll = QScrollArea(self)
        scroll.setObjectName(f"condition_task_{prefix}_editor_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.module_editor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(list_panel, 1)
        layout.addWidget(scroll, 3)

    def set_modules(self, modules: list[TaskModuleDraft]) -> None:
        self._modules = copy.deepcopy(modules)
        self._refresh_list(select_row=0 if self._modules else -1)

    def modules(self) -> list[TaskModuleDraft]:
        self._capture_editor()
        return copy.deepcopy(self._modules)

    def _add_module(self) -> None:
        kind = str(self.add_kind_combo.currentData())
        existing = {
            *self._reserved_module_ids,
            *(module.module_id for module in self._modules),
        }
        module_id = _unique_id(
            f"{self.objectName().removeprefix('condition_task_').removesuffix('_phase_editor')}-"
            f"{kind.replace('_', '-')}-module",
            existing,
        )
        step_id = _unique_id(kind.replace("_", "-"), set())
        label = next(label for label, item_kind in _MODULE_LABELS if item_kind == kind)
        step = _new_task_step_draft(step_id=step_id, kind=kind, title=label)
        module = TaskModuleDraft(module_id=module_id, title=label, steps=[step])
        self._modules.append(module)
        self._refresh_list(select_row=len(self._modules) - 1)
        self.changed.emit()

    def _duplicate_module(self) -> None:
        row = self.module_list.currentRow()
        if row < 0:
            return
        self._capture_editor()
        duplicate = copy.deepcopy(self._modules[row])
        duplicate.module_id = _unique_id(
            f"{duplicate.module_id}-copy",
            {
                *self._reserved_module_ids,
                *(module.module_id for module in self._modules),
            },
        )
        duplicate.title = f"{duplicate.title} Copy"
        self._modules.insert(row + 1, duplicate)
        self._refresh_list(select_row=row + 1)
        self.changed.emit()

    def _remove_module(self) -> None:
        row = self.module_list.currentRow()
        if row < 0:
            return
        self._modules.pop(row)
        self._refresh_list(select_row=min(row, len(self._modules) - 1))
        self.changed.emit()

    def _move_module(self, offset: int) -> None:
        row = self.module_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= len(self._modules):
            return
        self._capture_editor()
        self._modules[row], self._modules[target] = (
            self._modules[target],
            self._modules[row],
        )
        self._refresh_list(select_row=target)
        self.changed.emit()

    def _capture_editor(self) -> None:
        row = self.module_list.currentRow()
        module = self.module_editor.module()
        if module is not None and 0 <= row < len(self._modules):
            self._modules[row] = module

    def _refresh_list(self, *, select_row: int) -> None:
        self._syncing = True
        try:
            self.module_list.clear()
            for module in self._modules:
                suffix = "step" if len(module.steps) == 1 else "steps"
                item = QListWidgetItem(
                    f"{module.title or module.module_id}\n"
                    f"{module.repeat_count}x · {len(module.steps)} {suffix}"
                )
                item.setData(Qt.ItemDataRole.UserRole, module.module_id)
                item.setToolTip(f"Reusable module ID: {module.module_id}")
                self.module_list.addItem(item)
            self.module_list.setCurrentRow(select_row)
        finally:
            self._syncing = False
        self._load_selected(select_row)

    def _load_selected(self, row: int) -> None:
        if self._syncing:
            return
        module = self._modules[row] if 0 <= row < len(self._modules) else None
        self.module_editor.set_module(module)
        step = module.steps[0] if module is not None and module.steps else None
        self.selection_changed.emit(copy.deepcopy(step))

    def _store_selected(self, module: TaskModuleDraft) -> None:
        if self._syncing:
            return
        row = self.module_list.currentRow()
        if row < 0 or row >= len(self._modules):
            return
        self._modules[row] = copy.deepcopy(module)
        suffix = "step" if len(module.steps) == 1 else "steps"
        item = self.module_list.item(row)
        item.setText(
            f"{module.title or module.module_id}\n"
            f"{module.repeat_count}x · {len(module.steps)} {suffix}"
        )
        item.setData(Qt.ItemDataRole.UserRole, module.module_id)
        item.setToolTip(f"Reusable module ID: {module.module_id}")
        self.changed.emit()


@dataclass(frozen=True)
class PendingTaskAssetCopy:
    """One validated source-to-project copy performed only when Apply succeeds."""

    source: Path
    relative_target: str


def condition_task_flow_from_document(
    document: ProjectDocument,
    condition_id: str,
) -> ConditionTaskFlowDraft:
    """Build a detached GUI draft from one condition and project-owned modules."""

    condition = document.get_condition(condition_id)
    if condition is None:
        raise ValueError(f"Unknown condition '{condition_id}'.")
    modules = {module.task_id: module for module in document.project.task_modules}

    def bound_modules(bindings: list[TaskBinding]) -> list[TaskModuleDraft]:
        drafts: list[TaskModuleDraft] = []
        for binding in bindings:
            module = modules.get(binding.task_id)
            if module is None:
                raise ValueError(
                    f"Condition '{condition.name}' references missing task module "
                    f"'{binding.task_id}'."
                )
            drafts.append(_module_to_draft(module, binding))
        return drafts

    return ConditionTaskFlowDraft(
        pre_modules=bound_modules(condition.pre_task_bindings),
        post_modules=bound_modules(condition.post_task_bindings),
    )


def condition_task_summary(document: ProjectDocument, condition_id: str) -> str:
    """Return a compact saved-task summary for the Conditions step."""

    condition = document.get_condition(condition_id)
    if condition is None:
        return "No condition selected"
    pre_count = len(condition.pre_task_bindings)
    post_count = len(condition.post_task_bindings)
    if pre_count == 0 and post_count == 0:
        return "No pre/post tasks"
    return f"{pre_count} pre, {post_count} post"


def _module_to_draft(module: TaskModule, binding: TaskBinding) -> TaskModuleDraft:
    return TaskModuleDraft(
        module_id=module.task_id,
        title=module.name,
        occurrence=binding.occurrence.value,
        replaces_condition_start_gate=binding.replaces_condition_start_gate,
        repeat_count=module.repeat_count,
        steps=[_step_to_draft(step) for step in module.steps],
    )


def _step_to_draft(step: TaskStep) -> TaskStepDraft:
    options = [
        TaskOptionDraft(
            option_id=item.item_id,
            label=item.text or Path(item.image_path or item.item_id).stem,
            image_path=item.image_path,
            selectable=item.selectable,
            correct=item.correct,
            score=item.score,
            x_degrees=item.x,
            y_degrees=item.y,
            width_degrees=item.width,
            height_degrees=item.height,
            unit=item.unit.value,
        )
        for item in step.items
    ]
    branch_rules = [
        TaskBranchRuleDraft(
            rule_id=rule.rule_id,
            question_id=rule.question_id,
            operator=rule.operator.value,
            expected_values=list(rule.expected_values),
            expected_numeric=rule.expected_numeric,
            next_step_id=rule.next_step_id,
        )
        for rule in step.branch_rules
    ]
    branch_by_question: dict[str, list[TaskBranchRuleDraft]] = {}
    for rule in branch_rules:
        branch_by_question.setdefault(rule.question_id, []).append(rule)
    questions: list[TaskQuestionDraft] = []
    for question in step.questions:
        rules = branch_by_question.get(question.question_id, [])
        primary_rule: TaskBranchRuleDraft | None = rules[0] if rules else None
        branch_value = ""
        branch_target = ""
        branch_operator = "equals"
        if primary_rule is not None:
            branch_target = primary_rule.next_step_id
            branch_operator = primary_rule.operator
            if primary_rule.expected_numeric is not None:
                branch_value = repr(primary_rule.expected_numeric)
            elif primary_rule.expected_values:
                branch_value = _format_branch_values(primary_rule.expected_values)
        questions.append(
            TaskQuestionDraft(
                question_id=question.question_id,
                kind=question.kind.value,
                prompt=question.prompt,
                required=question.required,
                options=[
                    TaskOptionDraft(
                        option_id=option.option_id,
                        label=option.label,
                        image_path=option.image_path,
                        selectable=option.selectable,
                        correct=option.correct,
                        score=option.score,
                    )
                    for option in question.options
                ],
                minimum_selections=question.min_selections,
                maximum_selections=question.max_selections,
                minimum_value=question.min_value if question.min_value is not None else 1.0,
                maximum_value=question.max_value if question.max_value is not None else 5.0,
                step_value=question.step if question.step is not None else 1.0,
                randomize_options=question.randomize_options,
                minimum_label=question.min_label or "",
                maximum_label=question.max_label or "",
                maximum_text_length=question.max_text_length,
                branch_operator=branch_operator,
                branch_match_value=branch_value,
                branch_target_step_id=branch_target,
                branch_rule_id=(
                    primary_rule.rule_id if primary_rule is not None else ""
                ),
            )
        )
    return TaskStepDraft(
        step_id=step.step_id,
        kind=step.kind.value,
        title=step.heading,
        prompt=step.text,
        font_family=step.font_family.value,
        prompt_x=step.prompt_x,
        prompt_y=step.prompt_y,
        prompt_unit=step.prompt_unit.value,
        prompt_height=step.prompt_height,
        continue_key=step.continue_key,
        advance_keys=list(step.allowed_keys),
        timeout_seconds=step.timeout_seconds,
        duration_seconds=step.duration_seconds,
        layout_mode=step.layout_mode.value,
        columns=step.columns,
        repeat_count=step.repeat_count,
        maximum_attempts=step.max_attempts,
        retry_on_invalid=step.retry_on_invalid,
        retry_on_incorrect=step.retry_on_incorrect,
        complete_after_one_valid_choice=(
            step.kind == CoreTaskStepKind.CHOICE_GRID
            and step.min_selections == 1
            and step.max_selections == 1
        ),
        minimum_selections=step.min_selections,
        maximum_selections=step.max_selections,
        allow_duplicate_choices_across_repeats=(step.allow_duplicate_selections_across_repeats),
        randomize_options=step.randomize_options,
        submission_mode=step.submission_mode.value,
        show_footer=step.show_footer,
        require_response=step.require_response,
        options=options,
        questions=questions,
        branch_rules=branch_rules,
    )


def build_condition_task_models(
    draft: ConditionTaskFlowDraft,
    *,
    project_root: Path,
) -> tuple[list[TaskModule], list[TaskBinding], list[TaskBinding], list[PendingTaskAssetCopy]]:
    """Validate a GUI draft and return persisted models plus deferred asset copies."""

    planned = copy.deepcopy(draft)
    copies = _plan_task_assets(planned, project_root=project_root)
    all_modules = [*planned.pre_modules, *planned.post_modules]
    module_by_id: dict[str, TaskModule] = {}
    for module_draft in all_modules:
        model = _module_from_draft(module_draft)
        existing = module_by_id.get(model.task_id)
        if existing is not None and existing != model:
            raise ValueError(
                f"Reusable module ID '{model.task_id}' has conflicting definitions. "
                "Use a distinct module ID or make both bindings identical."
            )
        module_by_id[model.task_id] = model
    pre_bindings = [
        TaskBinding(
            task_id=module.module_id,
            occurrence=TaskOccurrence(module.occurrence),
            replaces_condition_start_gate=module.replaces_condition_start_gate,
        )
        for module in planned.pre_modules
    ]
    post_bindings = [
        TaskBinding(
            task_id=module.module_id,
            occurrence=TaskOccurrence(module.occurrence),
            replaces_condition_start_gate=False,
        )
        for module in planned.post_modules
    ]
    return list(module_by_id.values()), pre_bindings, post_bindings, copies


def _plan_task_assets(
    draft: ConditionTaskFlowDraft,
    *,
    project_root: Path,
) -> list[PendingTaskAssetCopy]:
    copies: list[PendingTaskAssetCopy] = []
    reserved: set[str] = set()
    source_targets: dict[tuple[str, Path], str] = {}
    root = project_root.resolve(strict=True)

    def plan_option(module: TaskModuleDraft, option: TaskOptionDraft) -> None:
        if option.source_path is None and option.image_path:
            candidate = root / Path(option.image_path)
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, RuntimeError, ValueError) as exc:
                raise ValueError(
                    f"Task image is missing or outside the project: {option.image_path}"
                ) from exc
            if not resolved.is_file():
                raise ValueError(f"Task image is not a file: {option.image_path}")
            parts = PurePosixPath(option.image_path).parts
            if len(parts) < 4 or parts[:3] != (
                "stimuli",
                "task-assets",
                module.module_id,
            ):
                option.source_path = resolved
                option.image_path = None
        if option.source_path is None:
            return
        try:
            source = option.source_path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"Task image is missing: {option.source_path}") from exc
        if not source.is_file() or source.suffix.lower() not in _IMAGE_SUFFIXES:
            raise ValueError(f"Task image is missing or unsupported: {source}")
        key = (module.module_id, source)
        existing_target = source_targets.get(key)
        if existing_target is None:
            base = Path("stimuli") / "task-assets" / module.module_id
            relative = (base / source.name).as_posix()
            if relative.casefold() in reserved:
                raise ValueError(
                    f"More than one task image would use '{relative}'. Rename one "
                    "source image before importing it."
                )
            existing_target = relative
            source_targets[key] = relative
            reserved.add(relative.casefold())
            target = root / Path(relative)
            if not target.exists() or target.resolve() != source:
                copies.append(
                    PendingTaskAssetCopy(
                        source=source,
                        relative_target=relative,
                    )
                )
        option.image_path = existing_target
        option.source_path = None

    for module in [*draft.pre_modules, *draft.post_modules]:
        if not _ID_RE.fullmatch(module.module_id):
            continue
        for step in module.steps:
            for option in step.options:
                plan_option(module, option)
            for question in step.questions:
                for option in question.options:
                    plan_option(module, option)
    return copies


def _module_from_draft(module: TaskModuleDraft) -> TaskModule:
    return TaskModule(
        task_id=module.module_id,
        name=module.title,
        repeat_count=module.repeat_count,
        steps=[_step_from_draft(step) for step in module.steps],
    )


def _step_from_draft(step: TaskStepDraft) -> TaskStep:
    if step.validation_error:
        raise ValueError(step.validation_error)
    kind = CoreTaskStepKind(step.kind)
    items = [_display_item_from_draft(option) for option in step.options]
    questions = [_question_from_draft(question) for question in step.questions]
    branch_rules = _branch_rules_from_draft(step)
    allowed_keys = list(dict.fromkeys(step.advance_keys))
    continue_key = step.continue_key
    minimum = step.minimum_selections
    maximum = step.maximum_selections
    if kind == CoreTaskStepKind.CHOICE_GRID and step.complete_after_one_valid_choice:
        minimum = maximum = 1
    if kind != CoreTaskStepKind.CHOICE_GRID:
        minimum = maximum = 1
    duration = step.duration_seconds
    columns = step.columns if step.layout_mode == "responsive_grid" else None
    return TaskStep(
        step_id=step.step_id,
        kind=kind,
        heading=step.title,
        text=step.prompt,
        font_family=TaskFontFamily(step.font_family),
        prompt_x=step.prompt_x,
        prompt_y=step.prompt_y,
        prompt_unit=PresentationUnit(step.prompt_unit),
        prompt_height=step.prompt_height,
        layout_mode=TaskLayoutMode(step.layout_mode),
        columns=columns,
        items=items,
        questions=questions if kind == CoreTaskStepKind.QUESTIONNAIRE else [],
        continue_key=continue_key,
        allowed_keys=allowed_keys,
        duration_seconds=duration,
        timeout_seconds=step.timeout_seconds,
        repeat_count=step.repeat_count,
        max_attempts=step.maximum_attempts,
        retry_on_invalid=step.retry_on_invalid,
        retry_on_incorrect=step.retry_on_incorrect,
        randomize_options=step.randomize_options,
        submission_mode=TaskSubmissionMode(step.submission_mode),
        show_footer=step.show_footer,
        require_response=step.require_response,
        min_selections=minimum,
        max_selections=maximum,
        allow_duplicate_selections_across_repeats=(step.allow_duplicate_choices_across_repeats),
        branch_rules=branch_rules,
    )


def _display_item_from_draft(option: TaskOptionDraft) -> TaskDisplayItem:
    image = option.image_path is not None
    selectable = option.selectable
    return TaskDisplayItem(
        item_id=option.option_id,
        modality=TaskItemModality.IMAGE if image else TaskItemModality.TEXT,
        text=None if image else option.label,
        image_path=option.image_path if image else None,
        x=option.x_degrees,
        y=option.y_degrees,
        width=option.width_degrees,
        height=option.height_degrees,
        unit=PresentationUnit(option.unit),
        selectable=selectable,
        correct=option.correct if selectable else None,
        score=option.score if selectable else None,
    )


def _question_from_draft(question: TaskQuestionDraft) -> TaskQuestion:
    if question.validation_error:
        raise ValueError(question.validation_error)
    kind = TaskQuestionKind(question.kind)
    choice = kind in {
        TaskQuestionKind.SINGLE_CHOICE,
        TaskQuestionKind.MULTIPLE_CHOICE,
    }
    numeric = kind in {TaskQuestionKind.NUMERIC, TaskQuestionKind.RATING}
    options = (
        [
            TaskOption(
                option_id=option.option_id,
                label=option.label,
                image_path=option.image_path,
                selectable=option.selectable,
                correct=option.correct if option.selectable else None,
                score=option.score if option.selectable else None,
            )
            for option in question.options
        ]
        if choice
        else []
    )
    minimum = question.minimum_selections if choice else None
    maximum = question.maximum_selections if choice else None
    if kind == TaskQuestionKind.SINGLE_CHOICE:
        if minimum is not None and minimum > 1:
            raise ValueError("Single-choice minimum selections cannot exceed one.")
        if maximum is not None and maximum != 1:
            raise ValueError("Single-choice maximum selections must be one when set.")
    return TaskQuestion(
        question_id=question.question_id,
        kind=kind,
        prompt=question.prompt,
        required=question.required,
        options=options,
        randomize_options=question.randomize_options,
        min_selections=minimum,
        max_selections=maximum,
        min_value=question.minimum_value if numeric else None,
        max_value=question.maximum_value if numeric else None,
        step=question.step_value if numeric else None,
        min_label=question.minimum_label or None,
        max_label=question.maximum_label or None,
        max_text_length=question.maximum_text_length,
    )


def _branch_rules_from_draft(step: TaskStepDraft) -> list[TaskBranchRule]:
    """Merge editable primary routes into the lossless rule collection."""

    rule_drafts = {rule.rule_id: copy.deepcopy(rule) for rule in step.branch_rules}
    rule_order = [rule.rule_id for rule in step.branch_rules]
    for question in step.questions:
        rule_id = question.branch_rule_id
        if not question.branch_target_step_id:
            if rule_id:
                rule_drafts.pop(rule_id, None)
                rule_order = [item for item in rule_order if item != rule_id]
            continue
        if not rule_id:
            rule_id = _unique_id(
                f"{question.question_id}-route",
                set(rule_drafts),
            )
            rule_order.append(rule_id)
        operator = TaskBranchOperator(question.branch_operator)
        expected_numeric = None
        expected_values: list[str] = []
        if operator in {
            TaskBranchOperator.GREATER_THAN,
            TaskBranchOperator.LESS_THAN,
        }:
            try:
                expected_numeric = float(question.branch_match_value)
            except ValueError as exc:
                raise ValueError(
                    f"Question '{question.question_id}' needs a numeric branch value."
                ) from exc
        elif operator != TaskBranchOperator.ANSWERED:
            expected_values = _parse_branch_values(question.branch_match_value)
        rule_drafts[rule_id] = TaskBranchRuleDraft(
            rule_id=rule_id,
            question_id=question.question_id,
            operator=operator.value,
            expected_values=expected_values,
            expected_numeric=expected_numeric,
            next_step_id=question.branch_target_step_id,
        )
    return [
        TaskBranchRule(
            rule_id=rule_drafts[rule_id].rule_id,
            question_id=rule_drafts[rule_id].question_id,
            operator=TaskBranchOperator(rule_drafts[rule_id].operator),
            expected_values=rule_drafts[rule_id].expected_values,
            expected_numeric=rule_drafts[rule_id].expected_numeric,
            next_step_id=rule_drafts[rule_id].next_step_id,
        )
        for rule_id in rule_order
        if rule_id in rule_drafts
    ]


class ConditionTaskDialog(QDialog):
    """Reusable pre/post task authoring dialog for one selected condition."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        condition_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        condition = document.get_condition(condition_id)
        if condition is None:
            raise ValueError(f"Unknown condition '{condition_id}'.")
        self.setObjectName("condition_task_dialog")
        self.setWindowTitle(f"Pre/Post Tasks - {condition.name}")
        self.setModal(True)
        self.resize(1100, 700)
        self.setMinimumSize(1000, 640)
        self._document = document
        self._condition_id = condition_id
        initial = condition_task_flow_from_document(document, condition_id)

        header = QLabel(f"Participant tasks for {condition.name}", self)
        header.setObjectName("condition_task_dialog_header")
        header.setProperty("sectionCardRole", "title")
        helper = QLabel(
            "Build reusable modules before or after the timed FPVS stream. Module and "
            "step clocks remain separate from FPVS frames and triggers. Exact layouts "
            "use degrees of visual angle; responsive grids adapt to the participant display.",
            self,
        )
        helper.setObjectName("condition_task_dialog_helper")
        helper.setWordWrap(True)

        self.phase_tabs = QTabWidget(self)
        self.phase_tabs.setObjectName("condition_task_phase_tabs")
        self.pre_editor = TaskPhaseEditor(
            document.project_root,
            phase_label="Pre",
            reserved_module_ids={module.task_id for module in document.project.task_modules},
            parent=self.phase_tabs,
        )
        self.post_editor = TaskPhaseEditor(
            document.project_root,
            phase_label="Post",
            reserved_module_ids={module.task_id for module in document.project.task_modules},
            parent=self.phase_tabs,
        )
        self.pre_editor.set_modules(initial.pre_modules)
        self.post_editor.set_modules(initial.post_modules)
        self.phase_tabs.addTab(self.pre_editor, "Pre-condition")
        self.phase_tabs.addTab(self.post_editor, "Post-condition")

        preview_group = QGroupBox("Participant preview", self)
        preview_group.setObjectName("condition_task_preview_group")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(6)
        self.preview = TaskParticipantPreview(document.project_root, preview_group)
        self.preview_summary = QLabel(
            "Select a module step to preview its participant-facing content.",
            preview_group,
        )
        self.preview_summary.setObjectName("condition_task_preview_summary")
        self.preview_summary.setWordWrap(True)
        preview_layout.addWidget(self.preview, 1)
        preview_layout.addWidget(self.preview_summary)

        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)
        content.addWidget(self.phase_tabs, 4)
        content.addWidget(preview_group, 2)

        self.validation_label = QLabel(self)
        self.validation_label.setObjectName("condition_task_validation_label")
        self.validation_label.setWordWrap(True)
        mark_error_text(self.validation_label)
        self.validation_label.setVisible(False)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.setObjectName("condition_task_button_box")
        self.apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setText("Apply Tasks")
        mark_primary_action(self.apply_button)
        mark_secondary_action(self.button_box.button(QDialogButtonBox.StandardButton.Cancel))
        # QDialogButtonBox classifies StandardButton.Apply as ApplyRole, so it does
        # not emit accepted(). Connect the authored Apply action directly.
        self.apply_button.clicked.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(header)
        layout.addWidget(helper)
        layout.addLayout(content, 1)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.button_box)

        for editor in (self.pre_editor, self.post_editor):
            editor.selection_changed.connect(self._refresh_preview)
            editor.changed.connect(self._validate_draft)
        self.phase_tabs.currentChanged.connect(self._refresh_active_preview)
        self._refresh_active_preview()
        self._validate_draft()

    def draft(self) -> ConditionTaskFlowDraft:
        """Return the current detached editor state."""

        return ConditionTaskFlowDraft(
            pre_modules=self.pre_editor.modules(),
            post_modules=self.post_editor.modules(),
        )

    def accept(self) -> None:
        """Validate, import assets, and atomically update the selected condition."""

        try:
            modules, pre_bindings, post_bindings, asset_copies = build_condition_task_models(
                self.draft(),
                project_root=self._document.project_root,
            )
            self._document.set_condition_task_flow(
                self._condition_id,
                modules=modules,
                pre_bindings=pre_bindings,
                post_bindings=post_bindings,
                asset_copies=[
                    (copy_item.source, copy_item.relative_target) for copy_item in asset_copies
                ],
            )
        except Exception as error:
            self.validation_label.setText(str(error))
            self.validation_label.setVisible(True)
            self.apply_button.setEnabled(False)
            return
        super().accept()

    def _validate_draft(self) -> None:
        try:
            build_condition_task_models(
                self.draft(),
                project_root=self._document.project_root,
            )
        except Exception as error:
            self.validation_label.setText(str(error))
            self.validation_label.setVisible(True)
            self.apply_button.setEnabled(False)
        else:
            self.validation_label.clear()
            self.validation_label.setVisible(False)
            self.apply_button.setEnabled(True)

    def _refresh_active_preview(self, *_args: object) -> None:
        editor = self.pre_editor if self.phase_tabs.currentIndex() == 0 else self.post_editor
        module = editor.module_editor.module()
        step = None
        if module is not None:
            row = editor.module_editor.step_list.currentRow()
            if 0 <= row < len(module.steps):
                step = module.steps[row]
        self._refresh_preview(step)

    def _refresh_preview(self, step: TaskStepDraft | None) -> None:
        self.preview.set_step(step)
        if step is None:
            self.preview_summary.setText(
                "Select a module step to preview its participant-facing content."
            )
            return
        details = [step.kind.replace("_", " ").title()]
        if step.kind in {"study", "choice_grid"}:
            details.append("exact geometry" if step.layout_mode == "exact" else "responsive grid")
            details.append(f"{len(step.options)} items")
        elif step.kind == "questionnaire":
            details.append(f"{len(step.questions)} questions")
        self.preview_summary.setText(" · ".join(details))
