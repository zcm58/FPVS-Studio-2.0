"""Image-backed cycle authoring with a custom within-slot attentional-blink design."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, cast

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QColor, QImage, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.attentional_blink import (
    AttentionalBlinkDescription,
    SlotRole,
    describe_attentional_blink,
    preview_attentional_blink,
)
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory
from fpvs_studio.core.experiment_categories import category_conflict_condition_ids
from fpvs_studio.core.experiment_design import describe_cycle, preview_cycle
from fpvs_studio.core.models import AttentionalBlinkSettings, StimulusSet
from fpvs_studio.core.run_spec import StimulusRole
from fpvs_studio.core.validation import APPROVED_MONITOR_REFRESH_RATES_HZ
from fpvs_studio.gui.components import (
    PathValueLabel,
    apply_experiment_designer_theme,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
)
from fpvs_studio.gui.designer_sources import import_designer_source, load_designer_thumbnails
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_widgets import (
    CycleCanvas,
    ExpandedSlotCanvas,
    SourceCard,
    TargetPairDetailHeader,
)
from fpvs_studio.gui.workers import BackgroundTask
from fpvs_studio.preprocessing.models import StimulusSetInspectionSummary

_LOG = logging.getLogger(__name__)


class _DesignerSpinBox(QDoubleSpinBox):
    """Validated numeric entry without arrow or wheel stepping."""

    def stepEnabled(self) -> QAbstractSpinBox.StepEnabledFlag:  # noqa: N802
        return QAbstractSpinBox.StepEnabledFlag.StepNone

    def textFromValue(self, value: float) -> str:  # noqa: N802
        return self.locale().toString(value, "f", self.decimals()).rstrip("0").rstrip(
            self.locale().decimalPoint()
        )


class ExperimentDesignerWidget(QWidget):
    """One category-specific editor shared by Setup and the standalone dialog."""

    applied = Signal()
    busy_changed = Signal(bool)
    draft_changed = Signal()
    closed = Signal()

    def __init__(
        self, document: ProjectDocument, *, condition_id: str,
        embedded: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._condition_id = condition_id
        condition = document.get_condition(condition_id)
        if condition is None:
            raise ValueError("Select an image condition before opening the designer.")
        if condition_id in category_conflict_condition_ids(document.project):
            raise ValueError("Separate this condition into an experiment of the matching category.")
        if document.project.experiment_category == ExperimentCategory.FPVS:
            raise ValueError("FPVS design is coming soon.")
        self._embedded = embedded
        self._applying = False
        self._reported_busy = False
        self._reported_importing = False
        self._refresh_pending = False
        self._duty_cycle_mode = condition.duty_cycle_mode
        self._mode = (
            "attentional_blink"
            if document.project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
            else "standard"
        )
        self._changing = True
        self._task: BackgroundTask | None = None
        self._thumbnail_task: BackgroundTask | None = None
        self._thumbnail_revision = 0
        self._thumbnail_pending = False
        self._close_requested = False
        self._source_error: str | None = None
        self._pixmaps: dict[str, list[QPixmap]] = {}
        self._source_counts: dict[str, int] = {}
        self._source_paths: dict[str, str] = {}
        self._description: AttentionalBlinkDescription | None = None
        self._last_notified_state: object = None
        self._preview_segments: list[tuple[str, float, int]] = []
        self._preview_index = 0
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._advance_preview)
        protocol = document.project.settings.protocol
        settings = condition.attentional_blink or AttentionalBlinkSettings()
        self.setObjectName("experiment_designer_widget")
        self.setProperty("designerCompact", True)
        self.setProperty("designerEmbedded", embedded)
        self.setMinimumWidth(740 if embedded else 1010)
        apply_experiment_designer_theme(self)
        layout = QVBoxLayout(self)
        if embedded:
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)
        header = QHBoxLayout()
        brand = self._label("FPVS Studio  |  Experiment Designer", "heading")
        header.addWidget(brand)
        self.condition_label = PathValueLabel(self)
        self.condition_label.setProperty("designerRole", "condition")
        self.condition_label.set_path_text(condition.name, max_length=54)
        self.condition_label.setMinimumWidth(0)
        self.condition_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(self.condition_label, 1)
        self.header_widget = QWidget(self)
        self.header_widget.setLayout(header)
        layout.addWidget(self.header_widget)
        self.header_widget.setVisible(not embedded)

        source_heading = QHBoxLayout()
        source_heading.setContentsMargins(0, 0, 0, 0)
        source_heading.setSpacing(18)
        source_heading.addWidget(self._label("Image sources", "sectionTitle"))
        source_heading.addWidget(self._label(
            "Drag an image pool onto the stream to add a slot.", "secondary"
        ))
        source_heading.addStretch(1)
        self.source_heading_widget = QWidget(self)
        self.source_heading_widget.setLayout(source_heading)
        layout.addWidget(self.source_heading_widget)
        self.source_shelf = QWidget(self)
        source_row = QHBoxLayout(self.source_shelf)
        source_row.setContentsMargins(0, 0, 0, 0)
        source_row.setSpacing(12)
        ab = self._mode == "attentional_blink"
        self.base_source = SourceCard(
            "base", "Base images", parent=self
        )
        self.t1_source = SourceCard(
            "t1", "T1 · First target" if ab else "Oddball images", parent=self
        )
        self.t2_source = SourceCard("t2", "T2 · Second target", parent=self)
        self.isi_source = SourceCard("isi", "ISI · Between targets", parent=self)
        self.isi_mode_group = QButtonGroup(self)
        self.isi_blank_button = self._button("Blank screen")
        self.isi_image_button = self._button("Image")
        isi_choices = QHBoxLayout()
        isi_choices.setSpacing(0)
        for button, mode in ((self.isi_blank_button, "blank"), (self.isi_image_button, "image")):
            button.setCheckable(True)
            button.setProperty("designerIsiChoice", mode)
            button.setAccessibleName(f"ISI appearance: {button.text()}")
            self.isi_mode_group.addButton(button)
            isi_choices.addWidget(button, 1)
        isi_layout = self.isi_source.layout()
        assert isinstance(isi_layout, QVBoxLayout)
        isi_layout.insertLayout(1, isi_choices)
        self.isi_blank_preview = self._label("Blank screen", "blankPreview")
        self.isi_blank_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.isi_blank_preview.setMinimumHeight(30)
        isi_layout.insertWidget(3, self.isi_blank_preview, 1)
        self.isi_blank_note = self._label("No image folder needed", "secondary")
        self.isi_blank_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        isi_layout.addWidget(self.isi_blank_note)
        for card, stretch in ((self.base_source, 1), (self.t1_source, 1),
                              (self.isi_source, 1), (self.t2_source, 1)):
            source_row.addWidget(card, stretch)
            card.folder_requested.connect(self._choose_source)
            card.add_requested.connect(self._add_source_role)
            card_layout = card.layout()
            assert card_layout is not None
            card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            if embedded:
                card_layout.setContentsMargins(0, 0, 0, 0)
                card_layout.setSpacing(3)
                card.tile.setMinimumHeight(30 if card.role == "isi" else 50)
                card.tile.setMaximumHeight(50)
        layout.addWidget(self.source_shelf)

        cycle_panel, cycle_layout = self._panel()
        cycle_header = QHBoxLayout()
        cycle_header.setSpacing(12)
        cycle_header.addWidget(self._label("Repeating stream", "sectionTitle"))
        self.summary_label = self._label("", "secondary")
        cycle_header.addWidget(self.summary_label, 1)
        cycle_header.addWidget(QLabel("Stream rate", self))
        self.rate_spin = self._spin(0.01, 500.0, 4.0, " Hz")
        self.rate_spin.setAccessibleName("Stream rate in hertz")
        self.rate_spin.setFixedWidth(82)
        cycle_header.addWidget(self.rate_spin)
        self.slot_length_label = self._label("250 ms per normal slot", "secondary")
        cycle_header.addWidget(self.slot_length_label)
        cycle_layout.addLayout(cycle_header)
        self.cycle_canvas = CycleCanvas(self)
        if embedded:
            self.cycle_canvas.setMinimumHeight(106)
            self.cycle_canvas.setMaximumHeight(148)
        cycle_layout.addWidget(self.cycle_canvas, 1)
        layout.addWidget(cycle_panel, 1)

        self.slot_panel, slot_layout = self._panel()
        slot_header = QHBoxLayout()
        slot_header.setContentsMargins(0, 10, 0, 0)
        slot_header.setSpacing(14)
        self.slot_title = self._label("Inside the target pair", "sectionTitle")
        slot_header.addWidget(self.slot_title)
        self.used_label = self._label("250 ms · Slot 4", "secondary")
        slot_header.addWidget(self.used_label)
        slot_header.addStretch(1)
        slot_header.addWidget(self._label("Duration to scale", "secondary"))
        self.slot_header_widget = TargetPairDetailHeader(self.cycle_canvas, self)
        self.slot_header_widget.setLayout(slot_header)
        slot_layout.addWidget(self.slot_header_widget)
        self.slot_canvas = ExpandedSlotCanvas(self)
        if embedded:
            self.slot_canvas.setMinimumHeight(100)
            self.slot_canvas.setMaximumHeight(104)
        self.slot_content = QStackedWidget(self)
        self.slot_content.setObjectName("designer_slot_content")
        self.slot_content.setMinimumHeight(self.slot_canvas.minimumHeight())
        self.slot_content.addWidget(self.slot_canvas)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        mark_error_text(self.status_label)
        if ab:
            self.slot_content.addWidget(self.status_label)
        slot_layout.addWidget(self.slot_content, 1)
        self.target_spin = self._spin(0.001, 10000, 50, " ms")
        self.target_spin.setAccessibleName("T1 duration in milliseconds")
        self.isi_spin = self._spin(0.001, 10000, 50, " ms")
        self.isi_spin.setAccessibleName("ISI separator duration in milliseconds")
        self.timing_controls = QFrame(self)
        self.timing_controls.setProperty("designerControls", "true")
        control_layout = QHBoxLayout(self.timing_controls)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(18)
        target_group = QVBoxLayout()
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("T1 duration", self))
        target_row.addWidget(self.target_spin)
        target_group.addLayout(target_row)
        control_layout.addLayout(target_group, 1)
        isi_group = QVBoxLayout()
        isi_row = QHBoxLayout()
        isi_row.addWidget(QLabel("ISI duration", self))
        isi_row.addWidget(self.isi_spin)
        isi_group.addLayout(isi_row)
        self.isi_spin.setToolTip(
            "The ISI image or blank screen separates T1 and T2 for this duration."
        )
        control_layout.addLayout(isi_group, 1)
        t2_group = QVBoxLayout()
        t2_row = QHBoxLayout()
        t2_row.addWidget(QLabel("T2 duration", self))
        self.t2_value = self._label("150 ms", "computed")
        self.t2_value.setAccessibleName("Calculated T2 duration")
        t2_row.addWidget(self.t2_value)
        t2_group.addLayout(t2_row)
        self.auto_label = self._label("Automatic", "secondary")
        t2_row.addWidget(self.auto_label)
        control_layout.addLayout(t2_group, 1)
        self.equation_label = self._label("", "secondary")
        self.equation_label.setWordWrap(True)
        slot_layout.addWidget(self.timing_controls)
        self.equation_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        slot_layout.addWidget(self.equation_label)
        layout.addWidget(self.slot_panel, 1)

        if not ab:
            layout.addWidget(self.status_label)
        footer = QHBoxLayout()
        self.preview_button = self._button("▶  Preview at ¼ speed")
        self.preview_button.setProperty("designerPreview", "true")
        self.preview_button.setCheckable(True)
        footer.addWidget(self.preview_button)
        self.details_button = self._button("Timing && display details ▾", quiet=True)
        self.details_button.setCheckable(True)
        footer.addWidget(self.details_button)
        footer.addStretch(1)
        self.close_button = self._button("Cancel")
        self.close_button.setVisible(not embedded)
        self.apply_button = self._button("Use this design")
        self.apply_button.setVisible(not embedded)
        mark_primary_action(self.apply_button)
        self.apply_button.setToolTip("Apply cadence to all conditions and this condition's design.")
        footer.addWidget(self.close_button)
        footer.addWidget(self.apply_button)
        layout.addLayout(footer)
        self._build_details(settings.t2_trigger_code)
        self._build_preview_window()

        self.cycle_canvas.changed.connect(self._refresh_preview)
        for spin in (self.rate_spin, self.target_spin, self.isi_spin):
            spin.valueChanged.connect(self._refresh_preview)
        self.isi_blank_button.toggled.connect(self._refresh_preview)
        self.refresh_combo.currentIndexChanged.connect(self._refresh_preview)
        self.t2_marker_spin.valueChanged.connect(self._refresh_preview)
        self.preview_button.toggled.connect(self._toggle_preview)
        self.details_button.toggled.connect(self._toggle_details)
        self.apply_button.clicked.connect(self._apply)
        self.close_button.clicked.connect(self.request_close)
        terminal = "target_pair" if self._mode == "attentional_blink" else "oddball"
        self.cycle_canvas.set_mode(self._mode)
        self.cycle_canvas.set_roles(["base"] * (protocol.oddball_every_n - 1) + [terminal])
        self.cycle_canvas.setCurrentRow(self.cycle_canvas.count() - 1)
        self.rate_spin.setValue(protocol.base_hz)
        self.target_spin.setValue(settings.t1_duration_ms)
        self.isi_spin.setValue(settings.isi_ms)
        self.set_isi_mode(settings.isi_mode)
        self._baseline = self._draft_state()
        self._changing = False
        self.refresh_sources()
        self._refresh_preview()

    def _label(self, text: str, role: str) -> QLabel:
        label = QLabel(text, self)
        label.setProperty("designerRole", role)
        return label

    def _button(self, text: str, *, quiet: bool = False) -> QPushButton:
        button = QPushButton(text, self)
        button.setAutoDefault(False)
        if quiet:
            button.setProperty("quietAction", "true")
        mark_secondary_action(button)
        return button

    def _spin(self, minimum: float, maximum: float, value: float, suffix: str) -> QDoubleSpinBox:
        spin = _DesignerSpinBox(self)
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setDecimals(3)
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        return spin

    def _panel(self) -> tuple[QFrame, QVBoxLayout]:
        panel = QFrame(self)
        panel.setProperty("designerPanel", "true")
        layout = QVBoxLayout(panel)
        if self._embedded:
            layout.setContentsMargins(0, 0, 0, 0)
        else:
            layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        return panel, layout

    def isi_mode(self) -> Literal["blank", "image"]:
        return "blank" if self.isi_blank_button.isChecked() else "image"

    def set_isi_mode(self, mode: str) -> None:
        if mode not in ("blank", "image"):
            raise ValueError("Choose a blank screen or an image for the ISI.")
        (self.isi_blank_button if mode == "blank" else self.isi_image_button).setChecked(True)

    def _build_details(self, marker: int) -> None:
        self.timing_details = QDialog(self)
        self.timing_details.setWindowTitle("Timing & display details")
        self.timing_details.setMinimumWidth(560)
        details = QVBoxLayout(self.timing_details)
        form = QFormLayout()
        self.refresh_combo = QComboBox(self.timing_details)
        self.refresh_combo.addItem("Choose preview refresh", None)
        for refresh in APPROVED_MONITOR_REFRESH_RATES_HZ:
            self.refresh_combo.addItem(f"{refresh:g} Hz", refresh)
        configured = self._document.project.settings.display.preferred_refresh_hz
        if configured is not None:
            self.refresh_combo.setCurrentIndex(self.refresh_combo.findData(configured))
        form.addRow("Preview display", self.refresh_combo)
        self.t2_marker_spin = QSpinBox(self.timing_details)
        self.t2_marker_spin.setRange(1, 255)
        self.t2_marker_spin.setValue(marker)
        if self._mode == "attentional_blink":
            form.addRow("T2 onset marker", self.t2_marker_spin)
        else:
            self.t2_marker_spin.hide()
        details.addLayout(form)
        self.details_summary_label = QLabel(self.timing_details)
        self.details_summary_label.setWordWrap(True)
        self.details_summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        details.addWidget(self.details_summary_label)
        note = QLabel(
            "Preview calculations do not measure or configure the display.\n"
            "Verify the actual display in Setup > Timing before playback.\n"
            "Cadence applies to all conditions. Folder changes are immediate.",
            self.timing_details,
        )
        note.setWordWrap(True)
        details.addWidget(note)
        done = QPushButton("Done", self.timing_details)
        done.clicked.connect(self.timing_details.accept)
        details.addWidget(done, 0, Qt.AlignmentFlag.AlignRight)
        self.timing_details.finished.connect(lambda: self.details_button.setChecked(False))

    def _build_preview_window(self) -> None:
        self.preview_window = QDialog(self)
        self.preview_window.setWindowTitle("Slowed design preview · 4× slower")
        self.preview_window.resize(360, 330)
        layout = QVBoxLayout(self.preview_window)
        self.preview_image = QLabel(self.preview_window)
        self.preview_image.setMinimumSize(280, 220)
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview_image, 1)
        self.preview_phase_label = QLabel(self.preview_window)
        self.preview_phase_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview_phase_label)
        self.preview_note = QLabel(self.preview_window)
        self.preview_note.setWordWrap(True)
        layout.addWidget(self.preview_note)
        self.preview_window.finished.connect(self._stop_preview)

    def _draft_state(self) -> tuple[tuple[str, ...], float, float, float, int, str]:
        return (self.cycle_canvas.roles(), self.rate_spin.value(), self.target_spin.value(),
                self.isi_spin.value(), self.t2_marker_spin.value(),
                self.isi_mode())

    def has_pending_design(self) -> bool:
        return self._draft_state() != self._baseline

    def is_busy(self) -> bool:
        return self._task is not None or self._thumbnail_task is not None

    def is_importing(self) -> bool:
        return self._task is not None

    def validation_message(self) -> str:
        if self.is_importing():
            return "Wait for the image folder to finish loading."
        if not self.status_label.isHidden():
            return self.status_label.text()
        return "" if self.apply_button.isEnabled() else self.apply_button.toolTip()

    def refresh(self) -> None:
        """Refresh saved state while preserving a condition's unapplied design."""
        if self._applying:
            return
        if self.is_busy():
            self._refresh_pending = True
            return
        self._refresh_pending = False
        if not self.has_pending_design():
            condition = self._document.get_condition(self._condition_id)
            if condition is None:
                return
            protocol = self._document.project.settings.protocol
            self._changing = True
            terminal = "target_pair" if self._mode == "attentional_blink" else "oddball"
            self.cycle_canvas.set_roles(["base"] * (protocol.oddball_every_n - 1) + [terminal])
            self.cycle_canvas.setCurrentRow(self.cycle_canvas.count() - 1)
            self.rate_spin.setValue(protocol.base_hz)
            if condition.attentional_blink is not None:
                self.target_spin.setValue(condition.attentional_blink.t1_duration_ms)
                self.isi_spin.setValue(condition.attentional_blink.isi_ms)
                self.t2_marker_spin.setValue(condition.attentional_blink.t2_trigger_code)
                self.set_isi_mode(condition.attentional_blink.isi_mode)
            self._duty_cycle_mode = condition.duty_cycle_mode
            self._baseline = self._draft_state()
            self._changing = False
        self.refresh_sources()

    def _add_source_role(self, role: str) -> None:
        if role != "isi":
            self.cycle_canvas.add_role(role)

    def refresh_sources(self) -> None:
        condition = self._document.get_condition(self._condition_id)
        if condition is None:
            return
        for role, card in self._cards().items():
            if (role in ("t2", "isi")
                    and getattr(condition, f"{role}_stimulus_set_id") is None):
                self._source_counts[role], self._source_paths[role] = 0, ""
            else:
                source = self._document.get_condition_stimulus_set(self._condition_id, role)
                self._source_counts[role] = source.image_count
                self._source_paths[role] = (
                    str(self._document.project_root / source.source_dir)
                    if source.source_dir and source.image_count
                    else ""
                )
            card.set_source(
                self._source_counts[role], self._source_paths[role], self._pixmaps.get(role, [])
            )
        self._load_thumbnails()
        self._refresh_preview()

    def _cards(self) -> dict[str, SourceCard]:
        cards = {"base": self.base_source, "t1": self.t1_source}
        if self._mode == "attentional_blink":
            cards["t2"] = self.t2_source
            cards["isi"] = self.isi_source
        return cards

    def _load_thumbnails(self) -> None:
        self._thumbnail_revision += 1
        self._thumbnail_pending = True
        if self._thumbnail_task is not None:
            return
        self._launch_thumbnail_task()

    def _launch_thumbnail_task(self) -> None:
        if self._close_requested or (self._embedded and not self.isVisible()):
            return
        sources: dict[str, tuple[str, tuple[str, ...]]] = {}
        for role in self._cards():
            if not self._source_counts.get(role):
                continue
            source = self._document.get_condition_stimulus_set(self._condition_id, role)
            manifest_set = (
                next(
                    (item for item in self._document.manifest.sets if item.set_id == source.set_id),
                    None,
                )
                if self._document.manifest
                else None
            )
            paths = (
                tuple(item.source.relative_path for item in manifest_set.assets)
                if manifest_set
                else ()
            )
            sources[role] = (source.source_dir or "", paths)
        revision = self._thumbnail_revision
        self._thumbnail_pending = False
        self._pixmaps = {}
        self.cycle_canvas.set_pixmaps({})
        self.slot_canvas.set_pixmaps({})
        for role, card in self._cards().items():
            card.set_source(self._source_counts.get(role, 0), self._source_paths.get(role, ""), [])
        if not sources:
            return
        root = self._document.project_root
        task = BackgroundTask(
            parent_widget=self, callback=lambda: load_designer_thumbnails(root, sources)
        )
        self._thumbnail_task = task
        task.succeeded.connect(lambda result: self._thumbnails_loaded(revision, result))
        task.failed.connect(self._task_failed)
        task.finished.connect(self._thumbnail_finished)
        task.start()

    def _thumbnails_loaded(self, revision: int, result: object) -> None:
        if revision != self._thumbnail_revision:
            return
        images = cast(dict[str, list[QImage]], result)
        self._pixmaps = {
            role: [QPixmap.fromImage(image) for image in items] for role, items in images.items()
        }
        for role, card in self._cards().items():
            card.set_source(
                self._source_counts.get(role, 0),
                self._source_paths.get(role, ""),
                self._pixmaps.get(role, []),
            )
        self.cycle_canvas.set_pixmaps({**self._pixmaps, "oddball": self._pixmaps.get("t1", [])})
        self.slot_canvas.set_pixmaps(self._pixmaps)

    def _thumbnail_finished(self) -> None:
        self._thumbnail_task = None
        if self._refresh_pending and not self.is_busy() and not self._close_requested:
            self.refresh()
        elif self._thumbnail_pending and not self._close_requested:
            self._launch_thumbnail_task()
        self._refresh_preview()
        self._finish_close_if_ready()

    def _choose_source(self, role: str) -> None:
        if self._task is not None or role not in self._cards():
            return
        titles = {
            "base": "Base",
            "isi": "ISI",
            "t1": "T1" if self._mode == "attentional_blink" else "Oddball",
            "t2": "T2",
        }
        directory = QFileDialog.getExistingDirectory(
            self,
            f"Choose {titles[role]} Image Folder",
            str(self._document.project_root / "stimuli"),
        )
        if directory:
            self._start_source_import(role, Path(directory))

    def _start_source_import(self, role: str, directory: Path) -> None:
        self._stop_preview()
        self._source_error = None
        root, condition_id = self._document.project_root, self._condition_id
        import_role = "oddball" if role == "t1" and self._mode == "standard" else role
        task = BackgroundTask(
            parent_widget=self,
            callback=lambda: import_designer_source(root, condition_id, import_role, directory),
        )
        self._task = task
        task.succeeded.connect(lambda result: self._source_imported(role, result))
        task.failed.connect(self._task_failed)
        task.finished.connect(self._import_finished)
        self._refresh_preview()
        task.start()

    def _source_imported(self, role: str, result: object) -> None:
        summary, source = cast(tuple[StimulusSetInspectionSummary, StimulusSet], result)
        document_role = "oddball" if role == "t1" and self._mode == "standard" else role
        try:
            self._document.apply_designer_source(
                self._condition_id, role=document_role, stimulus_set=source, summary=summary
            )
        except (ValueError, OSError) as error:
            self._task_failed(error)
            return
        self.refresh_sources()

    def _task_failed(self, error: object) -> None:
        _LOG.error("Designer source task failed: %s", error)
        self._source_error = str(error)
        self._show_error(str(error))

    def _show_error(self, message: str) -> None:
        self.status_label.setText(message)
        if self._mode == "attentional_blink":
            self.slot_content.setCurrentWidget(self.status_label)
        self.status_label.show()

    def _import_finished(self) -> None:
        self._task = None
        if self._refresh_pending and not self.is_busy() and not self._close_requested:
            self.refresh()
        self._refresh_preview()
        self._finish_close_if_ready()

    def _refresh_preview(self, *_args: object) -> None:
        if self._changing:
            return
        self._stop_preview()
        self._description = None
        self.status_label.hide()
        if self._source_error:
            self._show_error(self._source_error)
        ab = self._mode == "attentional_blink"
        self.base_source.title_label.setText("Base images")
        self.t1_source.title_label.setText("T1 · First target" if ab else "Oddball images")
        self.t2_source.setVisible(ab)
        self.isi_source.setVisible(ab)
        blank_isi = self.isi_mode() == "blank"
        self.isi_source.tile.setVisible(not blank_isi)
        self.isi_source.path_widget.setVisible(not blank_isi)
        self.isi_source.folder_button.setVisible(not blank_isi)
        self.isi_source.count_label.setVisible(not blank_isi)
        self.isi_blank_preview.setVisible(blank_isi)
        self.isi_blank_note.setVisible(blank_isi)
        self.cycle_canvas.isi_blank = blank_isi
        self.slot_canvas.isi_blank = blank_isi
        self.cycle_canvas.update()
        self.slot_canvas.update()
        self.slot_panel.setVisible(ab)
        for card in self._cards().values():
            card.folder_button.setEnabled(self._task is None)
        self.apply_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        try:
            roles = self.cycle_canvas.roles()
            rate = self.rate_spin.value()
            slot_ms = 1000.0 / rate
            self.cycle_canvas.set_slot_ms(slot_ms)
            self.slot_length_label.setText(f"{slot_ms:g} ms per slot")
            self.summary_label.setText(f"{len(roles)} slots · {len(roles) / rate:.3f} s per cycle")
            refresh = self.refresh_combo.currentData()
            self.details_summary_label.setText(
                "Choose a preview display to see achieved frame timing."
            )
            if ab:
                description = describe_attentional_blink(
                    cast(tuple[SlotRole, ...], roles), base_hz=rate,
                    t1_ms=self.target_spin.value(), isi_ms=self.isi_spin.value(),
                )
                self._description = description
                self.slot_canvas.set_timing(
                    description.t1_ms, description.isi_ms, description.t2_ms
                )
                self.t2_value.setText(f"{description.t2_ms:g} ms")
                self.used_label.setText(
                    f"{description.slot_ms:g} ms · Slot {roles.index('target_pair') + 1}"
                )
                self.equation_label.setText(
                    f"T2 uses the time remaining in this {description.slot_ms:g} ms slot."
                )
                self.equation_label.setToolTip(
                    f"{description.t1_ms:g} + {description.isi_ms:g} + "
                    f"{description.t2_ms:g} = {description.slot_ms:g} ms. "
                    f"T1 to T2 onset: {description.soa_ms:g} ms."
                )
                if refresh is not None:
                    preview = preview_attentional_blink(
                        cast(tuple[SlotRole, ...], roles), refresh_hz=float(refresh),
                        base_hz=rate, t1_ms=description.t1_ms, isi_ms=description.isi_ms,
                    )
                    self.details_summary_label.setText(
                        f"Achieved: {preview.realized_base_hz:.3f} Hz · "
                        f"{preview.frames_per_slot} frames/slot.\n"
                        f"T1 {preview.t1_ms:g} ms ({preview.t1_frames} frames), "
                        f"separator {preview.isi_ms:g} ms ({preview.isi_frames}), "
                        f"T2 {preview.t2_ms:g} ms ({preview.t2_frames}).\n"
                        f"T1-to-T2 onset: {preview.soa_ms:g} ms. T2 fills remaining frames."
                    )
                reserved = {item.trigger_code for item in self._document.project.conditions}
                reserved.add(self._document.project.settings.triggers.oddball_trigger_code)
                if self.t2_marker_spin.value() in reserved:
                    raise ValueError(
                        "Choose a distinct T2 onset marker in Timing & display details."
                    )
            else:
                describe_cycle(cast(tuple[StimulusRole, ...], roles), base_hz=rate)
                if refresh is not None:
                    ordinary = preview_cycle(
                        cast(tuple[StimulusRole, ...], roles), base_hz=rate,
                        refresh_hz=float(refresh), duty_cycle_mode=self._duty_cycle_mode,
                    )
                    self.details_summary_label.setText(
                        f"Achieved {ordinary.realized_base_hz:.3f} images/s · "
                        f"{ordinary.frames_per_slot} frames/slot.\n"
                        f"Image: {ordinary.target_frames} frames; "
                        f"blank: {ordinary.remainder_frames} frames."
                    )
            ready = all(
                self._source_counts.get(role, 0) > 0 for role in self._cards()
                if role != "isi" or not blank_isi
            )
            if not ready:
                self.summary_label.setText("Choose all image folders")
            enabled = ready and not self.is_importing() and not self._close_requested
            self.apply_button.setEnabled(enabled)
            self.preview_button.setEnabled(enabled and not self.is_busy())
            if ab and not self._source_error:
                self.slot_content.setCurrentWidget(self.slot_canvas)
            self.apply_button.setToolTip(
                "Apply cadence to all conditions and this condition's design." if ready
                else "Choose images for Base, T1, T2 and image ISI to continue." if ab
                else "Choose Base and Oddball images to continue."
            )
        except ValueError as error:
            self.t2_value.setText("—")
            self.used_label.clear()
            self.equation_label.clear()
            self._show_error(str(error))
        if self._close_requested:
            for card in self._cards().values():
                card.folder_button.setEnabled(False)
        busy = self.is_busy()
        importing = self.is_importing()
        if busy != self._reported_busy or importing != self._reported_importing:
            self._reported_busy = busy
            self._reported_importing = importing
            self.busy_changed.emit(busy)
        state = (self._draft_state(), self.validation_message())
        if state != self._last_notified_state:
            self._last_notified_state = state
            self.draft_changed.emit()

    def _toggle_details(self, visible: bool) -> None:
        self.timing_details.setVisible(visible)
        if visible:
            self.timing_details.adjustSize()
            self.timing_details.raise_()

    def _toggle_preview(self, active: bool) -> None:
        if not active:
            self._stop_preview()
            return
        self.preview_note.setText("Illustration only · actual playback uses compiled frames")
        if self._description is not None:
            self._preview_segments = [
                (item.role, item.duration_ms, item.slot_index)
                for item in self._description.segments
            ]
        else:
            self._preview_segments = []
            slot_ms = 1000 / self.rate_spin.value()
            for index, role in enumerate(self.cycle_canvas.roles()):
                image_role = "t1" if role == "oddball" else "base"
                if self._duty_cycle_mode == DutyCycleMode.BLANK_50:
                    self._preview_segments.extend(
                        [(image_role, slot_ms / 2, index), ("blank", slot_ms / 2, index)]
                    )
                else:
                    self._preview_segments.append((image_role, slot_ms, index))
            if self._duty_cycle_mode == DutyCycleMode.SINUSOIDAL:
                self.preview_note.setText(
                    "Sequence only · contrast modulation is omitted. "
                    "Actual playback uses compiled contrast frames."
                )
        self._preview_index = -1
        self.preview_button.setText("■  Stop preview")
        self.preview_window.show()
        self._advance_preview()

    def _advance_preview(self) -> None:
        if not self.preview_button.isChecked() or not self._preview_segments:
            return
        self._preview_index = (self._preview_index + 1) % len(self._preview_segments)
        role, duration, slot = self._preview_segments[self._preview_index]
        images = self._pixmaps.get("isi" if role == "separator" else role, [])
        if role == "blank":
            self.preview_image.clear()
        elif role == "separator" and self.isi_mode() == "blank":
            blank = QPixmap(self.preview_image.size())
            blank.fill(QColor(self._document.project.settings.display.background_color))
            self.preview_image.setPixmap(blank)
        elif images:
            pixmap = images[slot % len(images)]
            self.preview_image.setPixmap(
                pixmap.scaled(
                    self.preview_image.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview_image.setText("Image preview unavailable")
        label = "ODDBALL" if self._mode == "standard" and role == "t1" else role.upper()
        if role == "separator" and self.isi_mode() == "blank":
            label = "BLANK ISI"
        self.preview_phase_label.setText(f"{label} · {duration:g} ms authored · 4× slower")
        self.cycle_canvas.setCurrentRow(slot)
        self.slot_canvas.set_active_phase(role if role in ("t1", "separator", "t2") else None)
        self._preview_timer.start(max(1, round(duration * 4)))

    def _stop_preview(self) -> None:
        self._preview_timer.stop()
        with QSignalBlocker(self.preview_button):
            self.preview_button.setChecked(False)
        self.preview_button.setText("▶  Preview at ¼ speed")
        self.preview_window.hide()
        self.slot_canvas.set_active_phase(None)

    def _apply(self) -> None:
        self.apply_pending_design()

    def apply_pending_design(self) -> bool:
        self._refresh_preview()
        if not self.apply_button.isEnabled():
            return False
        settings = (
            AttentionalBlinkSettings(
                t1_duration_ms=self.target_spin.value(), isi_ms=self.isi_spin.value(),
                t2_trigger_code=self.t2_marker_spin.value(),
                isi_mode=self.isi_mode(),
            ) if self._mode == "attentional_blink" else None
        )
        if self.has_pending_design():
            self._applying = True
            try:
                self._document.apply_experiment_design(
                    self._condition_id, base_hz=self.rate_spin.value(),
                    slot_count=self.cycle_canvas.count(), attentional_blink=settings,
                )
            except ValueError as error:
                self._show_error(str(error))
                return False
            finally:
                self._applying = False
            self._baseline = self._draft_state()
        self._stop_preview()
        self.timing_details.hide()
        self.applied.emit()
        return True

    def _finish_close_if_ready(self) -> None:
        if self._close_requested and not self.is_busy():
            self.closed.emit()

    def request_close(self) -> bool:
        self._stop_preview()
        self.timing_details.hide()
        self._close_requested = True
        if self.is_busy():
            self.close_button.setText("Closing…")
            self._refresh_preview()
            return False
        self.closed.emit()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if not self.request_close():
            event.ignore()
        else:
            super().closeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if self._thumbnail_pending and self._thumbnail_task is None:
            self._launch_thumbnail_task()
            self._refresh_preview()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        compact = self._embedded or self.width() < 1200 or self.height() < 800
        if self._embedded:
            wide = self.width() >= 1200
            if self.property("designerWide") != wide:
                self.setProperty("designerWide", wide)
                self.cycle_canvas.setMaximumHeight(180 if wide else 148)
                self.slot_canvas.setMaximumHeight(140 if wide else 104)
                for card in self._cards().values():
                    card.tile.setMaximumHeight(80 if wide else 50)
                    card.tile.setMinimumHeight(
                        (50 if wide else 30) if card.role == "isi" else (70 if wide else 50)
                    )
        if self.property("designerCompact") != compact:
            self.setProperty("designerCompact", compact)
            layout = self.layout()
            if layout is not None and not self._embedded:
                layout.setContentsMargins(14, 6 if compact else 10, 14, 6 if compact else 10)
                layout.setSpacing(2 if compact else 4)
            controls = self.timing_controls.layout()
            if controls is not None and not self._embedded:
                controls.setContentsMargins(10, 4 if compact else 8, 10, 4 if compact else 8)
            if not self._embedded:
                self.slot_canvas.setMinimumHeight(100 if compact else 176)
                self.slot_content.setMinimumHeight(self.slot_canvas.minimumHeight())
            apply_experiment_designer_theme(self)


class ExperimentDesignerDialog(QDialog):
    """Optional standalone host for the same editor embedded in Setup > Design."""

    def __init__(
        self, document: ProjectDocument, *, condition_id: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("FPVS Studio · Experiment Designer")
        self.setMinimumSize(1040, 760)
        self.resize(1400, 920)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor = ExperimentDesignerWidget(document, condition_id=condition_id, parent=self)
        layout.addWidget(self.editor)
        self.editor.applied.connect(self.accept)
        self.editor.closed.connect(self._finish_reject)

    def _finish_reject(self) -> None:
        super().reject()

    def reject(self) -> None:
        self.editor.request_close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.editor.is_busy():
            self.editor.request_close()
            event.ignore()
        else:
            self.editor._stop_preview()
            self.editor.timing_details.hide()
            super().closeEvent(event)
