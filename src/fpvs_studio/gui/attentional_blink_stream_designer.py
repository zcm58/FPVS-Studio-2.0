"""A compact, condition-based editor for the native digit/letter AB stream."""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import ValidationError
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QHideEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.attentional_blink_stream import (
    AttentionalBlinkStreamDescription,
    attentional_blink_burst_grid,
    describe_attentional_blink_stream,
    iter_attentional_blink_stream_cycles,
    validate_attentional_blink_stream_symbols,
)
from fpvs_studio.core.models import AttentionalBlinkStreamSettings
from fpvs_studio.gui.components import (
    ColorPickerButton,
    apply_attentional_blink_stream_theme,
    mark_error_text,
    mark_secondary_action,
)
from fpvs_studio.gui.condition_task_dialog import ConditionTaskDialog
from fpvs_studio.gui.design_system import resolve_studio_theme
from fpvs_studio.gui.document import ProjectDocument


def is_letter_stream_project(document: ProjectDocument) -> bool:
    """The stream form never replaces an existing within-slot image design."""
    conditions = document.project.conditions
    return bool(conditions) and all(
        isinstance(condition.attentional_blink, AttentionalBlinkStreamSettings)
        for condition in conditions
    )


def _characters(text: str) -> list[str]:
    return list("".join(text.split()).upper())


class LetterStreamTimeline(QWidget):
    """Draw every core-described slot and mark the two target onsets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ab_stream_timeline")
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.description = describe_attentional_blink_stream()
        self.symbols: tuple[str, ...] = ()
        self.t1_color = "#00FF00"
        self.t2_color = "#FFFFFF"
        self.active_index: int | None = None

    def visible_slots(self) -> range:
        """Keep the target neighborhood readable for a full five-second burst."""
        description = self.description
        count = min(description.cycle_slots, max(15, description.lag + 9))
        start = max(0, min(description.t1_slot_index - 4, description.cycle_slots - count))
        return range(start, start + count)

    def slot_rect(self, index: int) -> QRectF:
        visible = self.visible_slots()
        count = len(visible)
        width = (self.width() - 16) / count
        return QRectF(8 + (index - visible.start) * width + 1, 54, width - 3, 60)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        theme = resolve_studio_theme(self.palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setPen(QColor(theme.text_muted))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Enter a valid rate, character pools and SOAs to preview the stream.",
            )
            painter.end()
            return
        caption_font = QFont(self.font())
        caption_font.setPointSize(9)
        character_font = QFont(self.font())
        character_font.setPointSize(20)
        character_font.setBold(True)
        for index in self.visible_slots():
            role = self.description.roles[index]
            rect = self.slot_rect(index)
            target = role != "base"
            painter.setBrush(QColor("#22262C"))
            border = (
                theme.primary
                if self.active_index == index
                else (self.t1_color if role == "t1" else theme.border)
            )
            painter.setPen(QPen(QColor(border), 2 if target else 1))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setFont(character_font)
            painter.setPen(
                QColor(
                    self.t1_color if role == "t1" else self.t2_color if role == "t2" else "#FFFFFF"
                )
            )
            symbol = self.symbols[index] if index < len(self.symbols) else "?"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)
            painter.setFont(caption_font)
            painter.setPen(QColor(theme.text_primary if target else theme.text_muted))
            painter.drawText(
                QRectF(rect.x() - 1, 118, rect.width() + 2, 21),
                Qt.AlignmentFlag.AlignCenter,
                role.upper() if target else str(index + 1),
            )
        t1 = self.slot_rect(self.description.t1_slot_index).left()
        t2 = self.slot_rect(self.description.t2_slot_index).left()
        painter.setPen(QPen(QColor(theme.primary), 1.5))
        painter.drawLine(int(t1), 31, int(t2), 31)
        painter.drawLine(int(t1), 27, int(t1), 50)
        painter.drawLine(int(t2), 27, int(t2), 50)
        painter.setFont(caption_font)
        painter.setPen(QColor(theme.text_primary))
        label_width = 138
        midpoint = (t1 + t2) / 2
        label_x = min(self.width() - label_width - 8, max(8, midpoint - label_width / 2))
        painter.drawText(
            QRectF(label_x, 2, label_width, 25),
            Qt.AlignmentFlag.AlignCenter,
            f"SOA {self.description.soa_ms:g} ms",
        )
        painter.setPen(QColor(theme.text_muted))
        painter.drawText(
            QRectF(8, 2, 360, 25), Qt.AlignmentFlag.AlignLeft,
            f"Characters {self.visible_slots().start + 1}–{self.visible_slots().stop} "
            f"of {self.description.cycle_slots}",
        )
        painter.end()


class AttentionalBlinkStreamDesigner(QWidget):
    """Edit shared sources and each condition's SOA; Next applies one atomic draft."""

    applied = Signal()
    draft_changed = Signal()
    busy_changed = Signal(bool)
    condition_selected = Signal(str)

    def __init__(
        self,
        document: ProjectDocument,
        *,
        condition_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._selected_id = condition_id
        self._refreshing = False
        self._applying = False
        self._baseline: tuple[object, ...] = ()
        self._condition_ids: list[str] = []
        self.soa_edits: dict[str, QLineEdit] = {}
        self._preview_index = -1
        self._preview_seed = 0
        self._preview_cycles: Iterator[tuple[str, ...]] = iter(())
        self.setObjectName("ab_stream_designer")
        self.setMinimumWidth(0)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = QHBoxLayout()
        self.heading_label = self._label("Stream design", "heading")
        heading.addWidget(self.heading_label)
        heading.addStretch(1)
        self.rate_caption = self._label("Presentation rate (Hz)", "secondary")
        self.rate_edit = QLineEdit(self)
        self.rate_edit.setObjectName("ab_presentation_rate")
        self.rate_edit.setAccessibleName("Presentation rate in Hz")
        self.rate_edit.setMaximumWidth(100)
        self.rate_edit.setToolTip(
            "Characters per second for all conditions. Enter a positive number. "
            "SOAs remain unchanged and must span whole characters; playback also "
            "requires whole display frames per character."
        )
        self.rate_caption.setBuddy(self.rate_edit)
        heading.addWidget(self.rate_caption)
        heading.addWidget(self.rate_edit)
        self.rate_label = self._label("100 ms per character", "secondary")
        heading.addWidget(self.rate_label)
        layout.addLayout(heading)
        self.burst_count_label = self._label("Bursts per SOA", "source")
        self.bursts_per_soa_spin = QSpinBox(self)
        self.bursts_per_soa_spin.setObjectName("ab_bursts_per_soa")
        self.bursts_per_soa_spin.setRange(1, 1000)
        self.bursts_per_soa_spin.setMaximumWidth(80)
        self.bursts_per_soa_spin.setAccessibleName("Bursts per SOA")
        self.bursts_per_soa_spin.setToolTip(
            "How many bursts to present for each SOA. All bursts are shuffled together. "
            "24 five-second bursts provide 120 seconds of EEG per SOA; answers add time."
        )
        self.burst_count_label.setBuddy(self.bursts_per_soa_spin)
        heading.addWidget(self.burst_count_label)
        heading.addWidget(self.bursts_per_soa_spin)
        self.burst_summary = self._label("", "secondary")
        self.burst_summary.setWordWrap(True)
        pools = QHBoxLayout()
        pools.setSpacing(20)
        self.base_edit = QLineEdit(self)
        self.t1_edit = QLineEdit(self)
        self.t2_edit = QLineEdit(self)
        self.t1_color_button = ColorPickerButton("#00FF00", title="Choose T1 color", parent=self)
        self.t2_color_button = ColorPickerButton("#FFFFFF", title="Choose T2 color", parent=self)
        for role, title, field, color in (
            ("base", "Distractor characters", self.base_edit, None),
            ("t1", "T1 · first target", self.t1_edit, self.t1_color_button),
            ("t2", "T2 · second target", self.t2_edit, self.t2_color_button),
        ):
            column = QVBoxLayout()
            column.setSpacing(5)
            column.setAlignment(Qt.AlignmentFlag.AlignTop)
            column.addWidget(self._label(title, "source"))
            field.setObjectName(f"ab_{role}_characters")
            field.setAccessibleName(title)
            field.setMinimumWidth(0)
            column.addWidget(field)
            if color is None:
                self.base_order_label = self._label(
                    "Random order · no immediate repeats", "secondary"
                )
                column.addWidget(self.base_order_label)
                field.setToolTip(
                    "These are the available characters, not their presentation order. "
                    "Playback samples them randomly, with no immediately repeated distractor."
                )
            else:
                row = QHBoxLayout()
                row.addWidget(self._label("Color", "secondary"))
                color.setObjectName(f"ab_{role}_color")
                color.setToolTip(
                    "Choose a color visually or enter an exact hex value. "
                    "Changing a target color also requires updating its recall question "
                    "and participant instructions."
                )
                row.addWidget(color)
                row.addStretch(1)
                column.addLayout(row)
            pools.addLayout(column, 1)
        layout.addLayout(pools)
        self.condition_heading = self._label(
            "Conditions · select an SOA", "source"
        )
        condition_heading = QHBoxLayout()
        condition_heading.addWidget(self.condition_heading)
        condition_heading.addStretch(1)
        condition_heading.addWidget(self.burst_summary)
        layout.addLayout(condition_heading)
        self.condition_table = QTableWidget(0, 3, self)
        self.condition_table.setObjectName("ab_stream_conditions")
        self.condition_table.setHorizontalHeaderLabels(
            ["Condition", "SOA (ms)", "Distractors between T1 and T2"]
        )
        self.condition_table.verticalHeader().hide()
        self.condition_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.condition_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.condition_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.condition_table.setShowGrid(False)
        self.condition_table.setAlternatingRowColors(True)
        # Reserve the styled header, three 36px SOA rows, and the table frame.
        self.condition_table.setMinimumHeight(150)
        self.condition_table.setMaximumHeight(150)
        header = self.condition_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.condition_table.setColumnWidth(1, 128)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        condition_header = self.condition_table.horizontalHeaderItem(0)
        assert condition_header is not None
        condition_header.setTextAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.condition_table.currentCellChanged.connect(self._selection_changed)
        layout.addWidget(self.condition_table)
        timeline_heading = QHBoxLayout()
        self.timeline_title = self._label("Target neighborhood · randomized", "heading")
        timeline_heading.addWidget(self.timeline_title)
        timeline_heading.addStretch(1)
        self.cycle_summary = self._label(
            "", "secondary"
        )
        timeline_heading.addWidget(self.cycle_summary)
        layout.addLayout(timeline_heading)
        self.timeline = LetterStreamTimeline(self)
        layout.addWidget(self.timeline, 1)
        self.separation_label = self._label("", "source")
        layout.addWidget(self.separation_label)
        preview_row = QHBoxLayout()
        self.preview_button = QPushButton("▶ Preview at ¼ speed", self)
        self.preview_button.setCheckable(True)
        mark_secondary_action(self.preview_button)
        self.preview_button.toggled.connect(self._toggle_preview)
        preview_row.addWidget(self.preview_button)
        self.shuffle_button = QPushButton("Shuffle example", self)
        self.shuffle_button.setObjectName("ab_shuffle_example")
        self.shuffle_button.setToolTip(
            "Show another random example. This does not change the experiment or its run seed."
        )
        mark_secondary_action(self.shuffle_button)
        self.shuffle_button.clicked.connect(self._shuffle_example)
        preview_row.addWidget(self.shuffle_button)
        self.preview_symbol = QLabel("", self)
        self.preview_symbol.setObjectName("ab_preview_symbol")
        self.preview_symbol.setFixedSize(46, 36)
        preview_row.addWidget(self.preview_symbol)
        self.preview_caption = self._label(
            "Randomized example; playback uses its run seed.", "secondary"
        )
        self.preview_caption.setWordWrap(True)
        preview_row.addWidget(self.preview_caption, 1)
        self.question_button = QPushButton("Recall questions…", self)
        self.question_button.setToolTip(
            "Inspect the participant recall questions and other tasks for this condition."
        )
        mark_secondary_action(self.question_button)
        self.question_button.clicked.connect(self._edit_question)
        preview_row.addWidget(self.question_button)
        layout.addLayout(preview_row)
        self.validation_label = QLabel(self)
        self.validation_label.setWordWrap(True)
        mark_error_text(self.validation_label)
        layout.addWidget(self.validation_label)
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._advance_preview)
        for field in (
            self.rate_edit,
            self.base_edit,
            self.t1_edit,
            self.t2_edit,
        ):
            field.textChanged.connect(self._draft_edited)
        for color_button in (self.t1_color_button, self.t2_color_button):
            color_button.color_changed.connect(self._draft_edited)
        self.bursts_per_soa_spin.valueChanged.connect(self._draft_edited)
        apply_attentional_blink_stream_theme(self)
        self.refresh()

    def _label(self, text: str, role: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("ab_" + "_".join(text.split()[:3]).lower())
        label.setProperty("abTextRole", role)
        return label

    def _snapshot(self) -> tuple[object, ...]:
        return (
            self.rate_edit.text(),
            self.bursts_per_soa_spin.value(),
            self.base_edit.text(),
            self.t1_edit.text(),
            self.t2_edit.text(),
            self.t1_color_button.color_hex(),
            self.t2_color_button.color_hex(),
            tuple((key, edit.text()) for key, edit in self.soa_edits.items()),
        )

    def refresh(self) -> None:
        if self._refreshing or (self.has_pending_design() and not self._applying):
            return
        self._refreshing = True
        try:
            conditions = self._document.ordered_conditions()
            if not conditions:
                self.condition_table.setRowCount(0)
                self._condition_ids.clear()
                self.soa_edits.clear()
                self._baseline = ()
                self.preview_button.setEnabled(False)
                self._stop_preview()
                return
            self._condition_ids = [condition.condition_id for condition in conditions]
            self.rate_edit.setText(str(self._document.project.settings.protocol.base_hz))
            session = self._document.project.settings.session
            self.bursts_per_soa_spin.setValue(session.block_count)
            self.burst_count_label.setText(
                "Bursts per SOA" if session.randomize_across_blocks else "Repeats per SOA"
            )
            self.soa_edits.clear()
            self.condition_table.setRowCount(len(conditions))
            first = conditions[0]
            for field, role in (
                (self.base_edit, "base"),
                (self.t1_edit, "oddball"),
                (self.t2_edit, "t2"),
            ):
                field.setText(
                    "".join(
                        self._document.get_condition_stimulus_set(first.condition_id, role).words
                    )
                )
            settings = first.attentional_blink
            assert isinstance(settings, AttentionalBlinkStreamSettings)
            self.t1_color_button.set_color(settings.t1_color)
            self.t2_color_button.set_color(settings.t2_color)
            for row, condition in enumerate(conditions):
                settings = condition.attentional_blink
                assert isinstance(settings, AttentionalBlinkStreamSettings)
                self.condition_table.setRowHeight(row, 36)
                item = QTableWidgetItem(condition.name)
                item.setToolTip(condition.name)
                self.condition_table.setItem(row, 0, item)
                edit = QLineEdit(str(settings.soa_ms), self.condition_table)
                edit.setAccessibleName(f"{condition.name} SOA in milliseconds")
                edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
                edit.textChanged.connect(self._draft_edited)
                self.soa_edits[condition.condition_id] = edit
                cell = QWidget(self.condition_table)
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(8, 3, 8, 3)
                cell_layout.addWidget(edit)
                self.condition_table.setCellWidget(row, 1, cell)
            if self._selected_id not in self._condition_ids:
                self._selected_id = first.condition_id
            self.condition_table.selectRow(self._condition_ids.index(self._selected_id))
            self._baseline = self._snapshot()
        finally:
            self._refreshing = False
        self._update_preview()

    def select_condition(self, condition_id: str) -> None:
        if condition_id in self._condition_ids:
            self.condition_table.selectRow(self._condition_ids.index(condition_id))

    def _selection_changed(self, row: int, *_args: int) -> None:
        if self._refreshing or not 0 <= row < len(self._condition_ids):
            return
        self._selected_id = self._condition_ids[row]
        self._stop_preview()
        self._update_preview()
        self.condition_selected.emit(self._selected_id)

    def _base_hz(self) -> float:
        try:
            return float(self.rate_edit.text())
        except ValueError:
            raise ValueError("Enter a presentation rate in Hz greater than zero.") from None

    def _description(self, condition_id: str) -> AttentionalBlinkStreamDescription:
        condition = self._document.get_condition(condition_id)
        if condition is None:
            raise ValueError("Choose a condition to inspect its sequence.")
        settings = condition.attentional_blink
        assert isinstance(settings, AttentionalBlinkStreamSettings)
        protocol = self._document.project.settings.protocol
        cycle_slots, t2_slot = protocol.oddball_every_n, settings.t2_slot_index
        if self._document.project.settings.session.randomize_across_blocks:
            cycle_slots, t2_slot = attentional_blink_burst_grid(self._base_hz())
        return describe_attentional_blink_stream(
            base_hz=self._base_hz(),
            cycle_slots=cycle_slots,
            soa_ms=float(self.soa_edits[condition_id].text()),
            t2_slot_index=t2_slot,
        )

    def validation_message(self) -> str:
        try:
            validate_attentional_blink_stream_symbols(
                _characters(self.base_edit.text()),
                _characters(self.t1_edit.text()),
                _characters(self.t2_edit.text()),
            )
            for condition_id in self._condition_ids:
                description = self._description(condition_id)
                AttentionalBlinkStreamSettings(
                    soa_ms=description.soa_ms,
                    t2_slot_index=description.t2_slot_index,
                    t1_color=self.t1_color_button.color_hex(),
                    t2_color=self.t2_color_button.color_hex(),
                )
        except ValidationError as error:
            return error.errors()[0]["msg"]
        except ValueError as error:
            return str(error).split("\n")[0]
        return ""

    def _draft_edited(self, *_args: object) -> None:
        if self._refreshing:
            return
        self._stop_preview()
        self._update_preview()
        self.draft_changed.emit()

    def _update_preview(self) -> None:
        message = self.validation_message()
        self.validation_label.setText(message)
        self.validation_label.setVisible(bool(message))
        self.preview_button.setEnabled(not message)
        self.shuffle_button.setEnabled(not message)
        self.timeline.setEnabled(not message)
        self.separation_label.setVisible(not message)
        for row, condition_id in enumerate(self._condition_ids):
            digit_text = "—"
            try:
                description = self._description(condition_id)
                digit_text = str(description.intervening_digits)
            except ValueError:
                # The validation label explains invalid SOAs beside the designer.
                pass
            digit_item = QTableWidgetItem(digit_text)
            digit_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.condition_table.setItem(row, 2, digit_item)
        if message:
            self.rate_label.setText("Timing needs correction")
            self.cycle_summary.clear()
            self.burst_summary.clear()
            return
        description = self._description(self._selected_id)
        self.timeline.description = description
        preview_available = self._preview_interval_ms() is not None
        self.preview_button.setEnabled(preview_available)
        self.preview_button.setToolTip(
            "" if preview_available else
            "This rate is outside the animated preview's timing range. "
            "The static timeline remains available."
        )
        if not preview_available:
            self.preview_caption.setText(self.preview_button.toolTip())
        self._preview_cycles = iter_attentional_blink_stream_cycles(
            description,
            base_words=_characters(self.base_edit.text()),
            t1_words=_characters(self.t1_edit.text()),
            t2_words=_characters(self.t2_edit.text()),
            random_seed=self._preview_seed,
        )
        self.timeline.symbols = next(self._preview_cycles)
        self.timeline.t1_color = self.t1_color_button.color_hex()
        self.timeline.t2_color = self.t2_color_button.color_hex()
        self.timeline.update()
        self.timeline.setAccessibleName(
            f"{description.cycle_slots} characters. "
            f"Presentation rate {description.base_hz:g} Hz; "
            f"{description.item_ms:g} milliseconds per character. "
            f"T1 in position {description.t1_slot_index + 1}; "
            f"T2 in position {description.t2_slot_index + 1}. "
            f"SOA {description.soa_ms:g} milliseconds; "
            f"{description.intervening_digits} distractors between T1 and T2."
            " Distractors and distinct targets are randomized for each burst."
        )
        self.rate_label.setText(
            f"{description.item_ms:g} ms per character"
        )
        self.cycle_summary.setText(
            f"{description.cycle_slots} characters · {description.cycle_ms / 1000:g} s"
        )
        repeats = self.bursts_per_soa_spin.value()
        seconds = description.cycle_ms / 1000 * repeats
        self.burst_summary.setText(
            f"{seconds:g} s EEG per SOA · {repeats * len(self._condition_ids)} total bursts"
            if self._document.project.settings.session.randomize_across_blocks
            else f"{repeats * len(self._condition_ids)} total condition presentations"
        )
        self.separation_label.setText(
            f"T1 onset → T2 onset: {description.soa_ms:g} ms  ·  "
            f"{description.intervening_digits} distractors between targets  ·  "
            f"{description.item_ms:g} ms per character"
        )

    def has_pending_design(self) -> bool:
        return bool(self._baseline) and self._snapshot() != self._baseline

    def is_busy(self) -> bool:
        return False

    def is_importing(self) -> bool:
        return False

    def apply_pending_design(self) -> bool:
        if self.validation_message():
            self._update_preview()
            return False
        if not self.has_pending_design():
            return True
        self._applying = True
        try:
            self._document.apply_attentional_blink_stream_design(
                _characters(self.base_edit.text()),
                _characters(self.t1_edit.text()),
                _characters(self.t2_edit.text()),
                {key: float(edit.text()) for key, edit in self.soa_edits.items()},
                t1_color=self.t1_color_button.color_hex(),
                t2_color=self.t2_color_button.color_hex(),
                base_hz=self._base_hz(),
                bursts_per_soa=self.bursts_per_soa_spin.value(),
            )
        except ValueError as error:
            self.validation_label.setText(str(error))
            self.validation_label.show()
            return False
        finally:
            self._applying = False
        self._baseline = self._snapshot()
        self.applied.emit()
        return True

    def _preview_interval_ms(self) -> int | None:
        interval = self.timeline.description.item_ms * 4
        # QTimer accepts positive signed 32-bit milliseconds for this animation.
        return round(interval) if 1 <= interval <= 2_147_483_647 else None

    def _toggle_preview(self, checked: bool) -> None:
        if not checked:
            self._stop_preview()
            return
        interval = self._preview_interval_ms()
        if interval is None:
            self._stop_preview()
            self.preview_caption.setText(self.preview_button.toolTip())
            return
        self._preview_index = -1
        self._advance_preview()
        self.preview_timer.start(interval)

    def _shuffle_example(self) -> None:
        self._stop_preview()
        self._preview_seed += 1
        self._update_preview()

    def _advance_preview(self) -> None:
        if self._preview_index == len(self.timeline.symbols) - 1:
            self.timeline.symbols = next(self._preview_cycles)
        self._preview_index = (self._preview_index + 1) % len(self.timeline.symbols)
        role = self.timeline.description.roles[self._preview_index]
        color = (
            self.timeline.t1_color if role == "t1"
            else self.timeline.t2_color if role == "t2"
            else "#FFFFFF"
        )
        self.preview_symbol.setText(
            f'<span style="color:{color}">{self.timeline.symbols[self._preview_index]}</span>'
        )
        self.preview_caption.setText(
            f"{'Distractor' if role == 'base' else role.upper()} · "
            f"character {self._preview_index + 1} of {len(self.timeline.symbols)} · "
            "¼ speed illustration, not a display timing test"
        )
        self.timeline.active_index = self._preview_index
        self.timeline.update()

    def _stop_preview(self) -> None:
        self.preview_timer.stop()
        self.preview_button.setChecked(False)
        self.preview_symbol.clear()
        self.preview_caption.setText("Randomized example; playback uses its run seed.")
        self.timeline.active_index = None
        self.timeline.update()

    def request_close(self) -> bool:
        self._stop_preview()
        return True

    def _edit_question(self) -> None:
        self._stop_preview()
        dialog = ConditionTaskDialog(
            self._document, condition_id=self._selected_id, parent=self,
        )
        dialog.exec()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        self._stop_preview()
        super().hideEvent(event)
