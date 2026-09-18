"""Image-pool controls and pictorial timelines for the experiment designer.

These widgets only display pixmaps supplied by the dialog. They neither load image
files nor decide experiment timing, and folder actions never add timeline blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from pathlib import Path

from PySide6.QtCore import QMimeData, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.gui.components import experiment_role_colors, mark_secondary_action
from fpvs_studio.gui.design_system import StudioTheme, resolve_studio_theme

ROLE_MIME = "application/x-fpvs-cycle-role"
INDEX_MIME = "application/x-fpvs-designer-index"
_CYCLE_ROLES = ("base", "oddball", "target_pair")


def _draw_image(
    painter: QPainter, rect: QRectF, pixmap: QPixmap | None, theme: StudioTheme
) -> None:
    """Contain real images; absent assets have an explicitly empty image symbol."""
    if rect.width() < 3 or rect.height() < 3:
        return
    painter.save()
    clip = QPainterPath()
    clip.addRoundedRect(rect, 5, 5)
    painter.setClipPath(clip)
    painter.fillRect(rect, QColor(theme.surface_elevated))
    if pixmap is not None and not pixmap.isNull():
        size = pixmap.size().scaled(
            QSize(max(1, int(rect.width())), max(1, int(rect.height()))),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        target = QRectF(0, 0, size.width(), size.height())
        target.moveCenter(rect.center())
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
    else:
        symbol_size = min(24.0, rect.width() * 0.55, rect.height() * 0.55)
        symbol = QRectF(0, 0, symbol_size, symbol_size * 0.72)
        symbol.moveCenter(rect.center())
        painter.setPen(QPen(QColor(theme.text_hint), 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(symbol, 2, 2)
        path = QPainterPath()
        path.moveTo(symbol.left() + 2, symbol.bottom() - 3)
        path.lineTo(symbol.center().x() - 2, symbol.center().y())
        path.lineTo(symbol.center().x() + 2, symbol.center().y() + 3)
        path.lineTo(symbol.right() - 3, symbol.top() + 3)
        painter.drawPath(path)
    painter.restore()


class SourceTile(QWidget):
    """Only this thumbnail region adds a block or starts a palette drag."""

    clicked = Signal(str)

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.role = role
        self.pixmaps: tuple[QPixmap, ...] = ()
        self._drag_start: QPoint | None = None
        self.setMinimumHeight(48)
        self.setMaximumHeight(114)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setAccessibleName(f"Add {role} images to the sequence")
        self.setToolTip("Click to add a block, or drag these thumbnails onto the sequence.")

    def set_pixmaps(self, pixmaps: Sequence[QPixmap]) -> None:
        self.pixmaps = tuple(pixmaps[:4] if self.role == "base" else pixmaps[:1])
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = resolve_studio_theme(self.palette())
        background, border, _ = experiment_role_colors(self.role, theme)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(background))
        painter.setPen(QPen(QColor(theme.focus_ring if self.hasFocus() else border), 1.5))
        painter.drawRoundedRect(rect, 7, 7)
        count = 4 if self.role == "base" else 1
        gap = 6
        inner = rect.adjusted(7, 7, -7, -7)
        width = (inner.width() - gap * (count - 1)) / count
        for index in range(count):
            image_rect = QRectF(
                inner.left() + index * (width + gap), inner.top(), width, inner.height()
            )
            pixmap = self.pixmaps[index] if index < len(self.pixmaps) else None
            _draw_image(painter, image_rect, pixmap, theme)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._drag_start = None
            mime = QMimeData()
            mime.setData(ROLE_MIME, self.role.encode("ascii"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.CopyAction)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        clicked = (
            self._drag_start is not None
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        )
        self._drag_start = None
        if clicked:
            self.clicked.emit(self.role)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit(self.role)
            event.accept()
        else:
            super().keyPressEvent(event)


class SourceCard(QFrame):
    """A non-clickable source card with independent add and folder controls."""

    folder_requested = Signal(str)
    add_requested = Signal(str)

    def __init__(
        self, role: str, title: str, subtitle: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.role = role
        self.source_count = 0
        self.source_path = ""
        self.setProperty("designerSourceCard", "true")
        self.setProperty("stimulusRole", role)
        self.setMinimumWidth(180)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        self.title_label = QLabel(title, self)
        self.title_label.setProperty("designerRole", "sourceTitle")
        self.title_label.setProperty("stimulusRole", role)
        self.count_label = QLabel("0 images", self)
        self.count_label.setProperty("designerRole", "secondary")
        header = QHBoxLayout()
        header.setSpacing(6)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.count_label)
        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setProperty("designerRole", "secondary")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        self.tile = SourceTile(role, self)
        self.folder_button = QPushButton("Choose images…", self)
        self.folder_button.setAutoDefault(False)
        self.folder_button.setMinimumWidth(150)
        self.folder_button.setProperty("designerFolder", "true")
        mark_secondary_action(self.folder_button)
        layout.addLayout(header)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.tile, 1)
        self.path_label = QLabel(self)
        self.path_label.setProperty("designerRole", "secondary")
        self.path_label.setMinimumWidth(0)
        self.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.path_widget = QWidget(self)
        path_row = QHBoxLayout(self.path_widget)
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(5)
        path_icon = QLabel(self.path_widget)
        path_icon.setPixmap(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon).pixmap(14, 14)
        )
        path_row.addWidget(path_icon)
        path_row.addWidget(self.path_label, 1)
        layout.addWidget(self.path_widget)
        layout.addWidget(self.folder_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.tile.clicked.connect(self.add_requested.emit)
        self.folder_button.clicked.connect(lambda: self.folder_requested.emit(self.role))
        self.set_source(0, "", ())

    def set_source(self, count: int, path: str, pixmaps: Sequence[QPixmap]) -> None:
        self.source_count = count
        self.source_path = path
        self.set_activity("")
        self.tile.set_pixmaps(pixmaps)
        self.folder_button.setText("Change folder…" if path else "Choose images…")
        description = f"{count} images • {path}" if path else "No image folder selected"
        self.folder_button.setToolTip(description)
        self.folder_button.setAccessibleName(f"{self.title_label.text()} folder: {description}")
        self.tile.setAccessibleName(f"Add {self.title_label.text()} to the sequence")
        self.tile.setAccessibleDescription(description)
        self.path_label.setToolTip(path or "No image folder selected")
        self.path_label.setAccessibleName(f"{self.title_label.text()} folder")
        self.path_label.setAccessibleDescription(path or "No image folder selected")
        self._refresh_path_label()

    def set_activity(self, text: str) -> None:
        """Show current image work in the existing count area without resizing the card."""
        count = self.source_count
        self.count_label.setText(text or (f"{count} image" if count == 1 else f"{count} images"))

    def _refresh_path_label(self) -> None:
        text = Path(self.source_path).name if self.source_path else "No folder selected"
        self.path_label.setText(self.path_label.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideMiddle, max(0, self.path_label.width())
        ))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_path_label()


class CycleCanvas(QAbstractScrollArea):
    """Equal-width stream slots with one compound target-pair slot."""

    changed = Signal()
    selection_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._roles: list[str] = []
        self._current = -1
        self._slot_ms = 250.0
        self._mode = "attentional_blink"
        self._pixmaps: dict[str, tuple[QPixmap, ...]] = {}
        self.isi_blank = False
        self._drag_start: QPoint | None = None
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(134)
        self.setMaximumHeight(220)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setAccessibleName(
            "Repeating sequence. Delete removes; Alt arrows move selected slots."
        )
        self.setToolTip("Target-pair thumbnails are schematic. Exact durations appear below.")
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)

    def roles(self) -> tuple[str, ...]:
        return tuple(self._roles)

    def count(self) -> int:
        return len(self._roles)

    def currentRow(self) -> int:  # noqa: N802
        return self._current

    def setCurrentRow(self, index: int) -> None:  # noqa: N802
        index = index if 0 <= index < self.count() else -1
        if index != self._current:
            self._current = index
            self._scroll_to_selected()
            self.selection_changed.emit(index)
            self.viewport().update()

    def set_roles(self, roles: Sequence[str]) -> None:
        if len(roles) > 1000 or any(role not in _CYCLE_ROLES for role in roles):
            raise ValueError("Use up to 1000 base, oddball, or target-pair slots.")
        self._roles = list(roles)
        self.setCurrentRow(-1)
        self._changed()

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.viewport().update()

    def set_slot_ms(self, slot_ms: float) -> None:
        if not isfinite(slot_ms) or slot_ms <= 0:
            raise ValueError("The slot duration must be positive and finite.")
        self._slot_ms = slot_ms
        self.viewport().update()

    def set_pixmaps(self, pixmaps: Mapping[str, Sequence[QPixmap]]) -> None:
        self._pixmaps = {role: tuple(images) for role, images in pixmaps.items()}
        self.viewport().update()

    def add_role(self, role: str, index: int | None = None) -> None:
        if self._mode == "standard":
            if role == "t1":
                role = "oddball"
            elif role in ("t2", "target_pair"):
                return
        elif role in ("t1", "t2"):
            role = "target_pair"
        if role not in _CYCLE_ROLES or self.count() >= 1000:
            return
        if index is None:
            index = self.count()
            if role == "base" and self._roles and self._roles[-1] in ("oddball", "target_pair"):
                index -= 1
        index = max(0, min(index, self.count()))
        self._roles.insert(index, role)
        self.setCurrentRow(index)
        self._changed()

    def remove_selected(self) -> None:
        if self._current >= 0:
            self._roles.pop(self._current)
            self.setCurrentRow(min(self._current, self.count() - 1))
            self._changed()

    def move_selected(self, offset: int) -> None:
        target = self._current + offset
        if self._current >= 0 and 0 <= target < self.count():
            self._roles.insert(target, self._roles.pop(self._current))
            self.setCurrentRow(target)
            self._changed()

    def _changed(self) -> None:
        self._update_scrollbar()
        self._scroll_to_selected()
        description = ", ".join(
            f"{index + 1}: {role.replace('_', ' ')}" for index, role in enumerate(self._roles)
        )
        self.setAccessibleDescription(description or "Empty sequence")
        self.viewport().update()
        self.changed.emit()

    def _slot_width(self) -> float:
        return max(180.0, (self.viewport().width() - 12.0) / max(1, self.count()))

    def _scroll_to_selected(self) -> None:
        if self._current < 0:
            return
        rect = self.slot_rect(self._current)
        scrollbar = self.horizontalScrollBar()
        if rect.left() < 0:
            scrollbar.setValue(scrollbar.value() + int(rect.left()) - 6)
        elif rect.right() > self.viewport().width():
            scrollbar.setValue(
                scrollbar.value() + int(rect.right()) - self.viewport().width() + 6
            )

    def _update_scrollbar(self) -> None:
        content_width = int(self._slot_width() * self.count() + 12)
        self.horizontalScrollBar().setRange(0, max(0, content_width - self.viewport().width()))
        self.horizontalScrollBar().setPageStep(self.viewport().width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_scrollbar()

    def slot_rect(self, index: int) -> QRectF:
        width = self._slot_width()
        return QRectF(
            6 + index * width - self.horizontalScrollBar().value(),
            5, width - 8,
            max(38, self.viewport().height() - self.fontMetrics().height() - 17),
        )

    def _pixmap(self, role: str, index: int = 0) -> QPixmap | None:
        images = self._pixmaps.get(role, ())
        return images[index % len(images)] if images else None

    def target_pair_index(self) -> int | None:
        indices = [index for index, role in enumerate(self._roles) if role == "target_pair"]
        return indices[0] if len(indices) == 1 else None

    def pair_thumbnail_rects(self, index: int) -> tuple[QRectF, ...]:
        """Readable overview tokens; only ExpandedSlotCanvas encodes duration widths."""
        rect = self.slot_rect(index)
        line = self.fontMetrics().height()
        inner = rect.adjusted(10, line + 9, -10, -line - 5)
        gap = 16.0
        width = max(0.0, (inner.width() - 2 * gap) / 3)
        return tuple(QRectF(inner.left() + i * (width + gap), inner.top(),
                            width, max(0, inner.height())) for i in range(3))

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = resolve_studio_theme(self.palette())
        painter.fillRect(self.viewport().rect(), QColor(theme.surface))
        if not self._roles:
            painter.setPen(QColor(theme.text_secondary))
            painter.drawText(
                self.viewport().rect(), Qt.AlignmentFlag.AlignCenter,
                "Drag images here, or click an image source above.",
            )
            return
        for index, role in enumerate(self._roles):
            rect = self.slot_rect(index)
            if rect.right() < 0 or rect.left() > self.viewport().width():
                continue
            background, border, foreground = experiment_role_colors(role, theme)
            if role == "target_pair":
                background, border = theme.surface_alt, theme.border
            selected = index == self._current
            painter.setBrush(QColor(background))
            painter.setPen(
                QPen(QColor(theme.focus_ring if selected else border), 2 if selected else 1)
            )
            painter.drawRoundedRect(rect, 8, 8)
            line_height = painter.fontMetrics().height()
            painter.setPen(QColor(foreground))
            title = "Target pair" if role == "target_pair" else role.title()
            painter.drawText(
                QRectF(rect.left() + 10, rect.top() + 5, rect.width() - 20, line_height + 2),
                Qt.AlignmentFlag.AlignLeft, f"{index + 1} · {title}",
            )
            image_rect = rect.adjusted(
                10, line_height + 10, -10, -7
            )
            if role == "target_pair":
                painter.setPen(QColor(theme.text_secondary))
                schematic_rect = QRectF(rect.right() - 80, rect.top() + 5, 70, line_height + 2)
                title_width = painter.fontMetrics().horizontalAdvance(f"{index + 1} · {title}")
                if schematic_rect.left() > rect.left() + title_width + 16:
                    painter.drawText(schematic_rect, Qt.AlignmentFlag.AlignRight, "Schematic")
                for part_index, (part, part_rect) in enumerate(zip(
                    ("t1", "isi", "t2"), self.pair_thumbnail_rects(index), strict=True
                )):
                    if not (part == "isi" and self.isi_blank):
                        _draw_image(painter, part_rect, self._pixmap(part), theme)
                    else:
                        painter.fillRect(part_rect, QColor(theme.border_soft))
                    painter.setPen(QColor(experiment_role_colors(part, theme)[2]))
                    painter.drawText(
                        QRectF(part_rect.left(), rect.bottom() - line_height - 3,
                               part_rect.width(), line_height),
                        Qt.AlignmentFlag.AlignCenter, part.upper(),
                    )
                    if part_index < 2:
                        painter.setPen(QColor(theme.text_secondary))
                        painter.drawText(
                            QRectF(part_rect.right(), part_rect.top(), 16, part_rect.height()),
                            Qt.AlignmentFlag.AlignCenter, "→",
                        )
            else:
                _draw_image(painter, image_rect, self._pixmap(role, index), theme)
            painter.setPen(QColor(theme.text_secondary))
            timestamp = f"{index * self._slot_ms:g} ms"
            axis_y = self.viewport().height() - line_height - 2
            painter.drawLine(int(rect.left()), axis_y - 5, int(rect.left()), axis_y - 1)
            painter.drawText(
                QRectF(rect.left(), axis_y, rect.width(), line_height),
                Qt.AlignmentFlag.AlignLeft, timestamp,
            )
        end_label = f"{self.count() * self._slot_ms:g} ms  ↻"
        end_x = self.slot_rect(self.count() - 1).right()
        painter.drawLine(int(self.slot_rect(0).left()), axis_y - 5, int(end_x), axis_y - 5)
        text_width = painter.fontMetrics().horizontalAdvance(end_label) + 2
        painter.drawLine(int(end_x), axis_y - 5, int(end_x), axis_y - 1)
        painter.drawText(
            QRectF(end_x - text_width, axis_y, text_width, line_height),
            Qt.AlignmentFlag.AlignRight, end_label,
        )

    def _index_at(self, x: float) -> int:
        index = int((x + self.horizontalScrollBar().value() - 6) // self._slot_width())
        return index if 0 <= index < self.count() else -1

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCurrentRow(self._index_at(event.position().x()))
            self._drag_start = event.position().toPoint() if self._current >= 0 else None
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            self._drag_start = None
            mime = QMimeData()
            mime.setData(INDEX_MIME, f"{id(self)}:{self._current}".encode("ascii"))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_start = None
        super().mouseReleaseEvent(event)

    def _drop_role(self, event: QDropEvent) -> str | None:
        mime = event.mimeData()
        if mime.hasFormat(ROLE_MIME):
            role = bytes(mime.data(ROLE_MIME).data()).decode("ascii", errors="replace")
            allowed = ("base", "t1", "t2", "target_pair") if self._mode != "standard" else (
                "base", "oddball", "t1"
            )
            if role in allowed:
                return role
        return None

    def _drop_index(self, event: QDropEvent) -> int | None:
        mime = event.mimeData()
        if event.source() is not self or not mime.hasFormat(INDEX_MIME):
            return None
        payload = bytes(mime.data(INDEX_MIME).data()).decode("ascii", errors="replace")
        owner, separator, index_text = payload.partition(":")
        if owner != str(id(self)) or not separator:
            return None
        try:
            index = int(index_text)
        except ValueError:
            return None
        return index if 0 <= index < self.count() else None

    def _accept_drag(self, event: QDropEvent) -> None:
        if self._drop_role(event) is not None and self.count() < 1000:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        elif self._drop_index(event) is not None:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        self._accept_drag(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:  # noqa: N802
        self._accept_drag(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        x = event.position().x() + self.horizontalScrollBar().value() - 6
        index = max(0, min(self.count(), int(x / self._slot_width() + 0.5)))
        role = self._drop_role(event)
        source = self._drop_index(event)
        if role is not None and self.count() < 1000:
            self.add_role(role, index)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        elif source is not None:
            target = index - 1 if source < index else index
            self.setCurrentRow(source)
            self.move_selected(target - source)
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            offset = -1 if event.key() == Qt.Key.Key_Left else 1
            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self.move_selected(offset)
            else:
                self.setCurrentRow(max(0, min(self.count() - 1, self._current + offset)))
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        if event.reason() != QContextMenuEvent.Reason.Keyboard:
            self.setCurrentRow(self._index_at(event.pos().x()))
        menu = QMenu(self)
        left = menu.addAction("Move left")
        left.setEnabled(self._current > 0)
        right = menu.addAction("Move right")
        right.setEnabled(0 <= self._current < self.count() - 1)
        remove = menu.addAction("Remove")
        remove.setEnabled(self._current >= 0)
        menu.addSeparator()
        clear = menu.addAction("Clear cycle")
        clear.setEnabled(self.count() > 0)
        action = menu.exec(event.globalPos())
        if action is left:
            self.move_selected(-1)
        elif action is right:
            self.move_selected(1)
        elif action is remove:
            self.remove_selected()
        elif action is clear:
            self.set_roles(())
        menu.deleteLater()


class TargetPairDetailHeader(QWidget):
    """Connect the compound slot to its timing detail, including while scrolling."""

    def __init__(self, cycle: CycleCanvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cycle = cycle
        cycle.changed.connect(self.update)
        cycle.selection_changed.connect(self.update)
        cycle.horizontalScrollBar().valueChanged.connect(self.update)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        index = self.cycle.target_pair_index()
        if index is None:
            return
        rect = self.cycle.slot_rect(index)
        if not 0 <= rect.center().x() <= self.cycle.viewport().width():
            return
        x = self.mapFromGlobal(self.cycle.viewport().mapToGlobal(rect.center().toPoint())).x()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(resolve_studio_theme(self.palette()).focus_ring), 1.5))
        painter.drawLine(x, 0, x, 7)
        painter.drawLine(x, 7, x - 10, 16)


class ExpandedSlotCanvas(QWidget):
    """A target slot whose three widths represent the supplied durations exactly."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.durations = (50.0, 50.0, 150.0)
        self._pixmaps: dict[str, tuple[QPixmap, ...]] = {}
        self.isi_blank = False
        self.active_phase: str | None = None
        self.setMinimumHeight(100)
        self.setMaximumHeight(260)
        self.setAccessibleName("Expanded target slot: T1, separator during ISI, then T2")
        self.set_timing(*self.durations)

    def set_timing(self, t1_ms: float, isi_ms: float, t2_ms: float) -> None:
        if any(not isfinite(value) or value < 0 for value in (t1_ms, isi_ms, t2_ms)):
            raise ValueError("Display durations must be finite and nonnegative.")
        if t1_ms + isi_ms + t2_ms <= 0:
            raise ValueError("The displayed slot must have a positive duration.")
        self.durations = (t1_ms, isi_ms, t2_ms)
        description = f"T1: {t1_ms:g} ms; separator / ISI: {isi_ms:g} ms; T2: {t2_ms:g} ms."
        self.setAccessibleDescription(description)
        self.setToolTip(description)
        self.update()

    def set_pixmaps(self, pixmaps: Mapping[str, Sequence[QPixmap]]) -> None:
        self._pixmaps = {role: tuple(images) for role, images in pixmaps.items()}
        self.update()

    def set_active_phase(self, phase: str | None) -> None:
        self.active_phase = phase
        self.update()

    def phase_rects(self) -> tuple[QRectF, ...]:
        width = float(max(1, self.width() - 18))
        total = sum(self.durations)
        rows = max(item[3] for item in self._axis_layout()) + 1
        axis_height = rows * (self.fontMetrics().height() + 2)
        start = 9.0
        rects = []
        for duration in self.durations:
            segment_width = width * duration / total
            rects.append(QRectF(start, 3, segment_width, max(24, self.height() - axis_height - 15)))
            start += segment_width
        return tuple(rects)

    def _axis_layout(self) -> tuple[tuple[str, float, float, int, float], ...]:
        boundaries = (0.0, self.durations[0], sum(self.durations[:2]), sum(self.durations))
        row_ends = [float("-inf")] * 4
        labels = []
        for index, value in enumerate(boundaries):
            if index > 0 and value == boundaries[index - 1]:
                continue
            x = 9 + (self.width() - 18) * value / boundaries[-1]
            text = f"{value:g} ms"
            width = float(self.fontMetrics().horizontalAdvance(text) + 4)
            left = min(max(0.0, x - width / 2), max(0, self.width() - width))
            row = next(row for row, end in enumerate(row_ends) if left > end + 5)
            row_ends[row] = left + width
            labels.append((text, left, width, row, x))
        return tuple(labels)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = resolve_studio_theme(self.palette())
        painter.fillRect(self.rect(), QColor(theme.surface))
        labels = ("T1", "Blank / ISI" if self.isi_blank else "Image / ISI", "T2")
        phase_names = ("t1", "separator", "t2")
        rects = self.phase_rects()
        line_height = painter.fontMetrics().height()
        bar_y = int(rects[0].bottom())
        time_top = bar_y + 11
        for rect, phase, label, duration in zip(
            rects, phase_names, labels, self.durations, strict=True
        ):
            if rect.width() <= 0:
                continue
            role = "isi" if phase == "separator" else phase
            background, border, foreground = experiment_role_colors(role, theme)
            painter.fillRect(rect, QColor(background))
            painter.setPen(QPen(QColor(border), 1))
            painter.drawRect(rect)
            images = self._pixmaps.get(role, ())
            painter.setPen(QColor(foreground))
            label_rect = QRectF(rect.left() + 3, rect.top() + 5, rect.width() - 6, line_height + 2)
            if painter.fontMetrics().horizontalAdvance(label) <= label_rect.width():
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
            show_duration = self.height() >= 130
            duration_height = line_height + 5 if show_duration else 0
            image_height = max(0, rect.height() - line_height - 21 - duration_height)
            image_rect = QRectF(
                0, 0, min(image_height * 1.4, max(0, rect.width() - 18)), image_height
            )
            image_rect.moveCenter(QPoint(
                int(rect.center().x()), int(rect.top() + line_height + 13 + image_height / 2)
            ))
            if not (phase == "separator" and self.isi_blank):
                _draw_image(painter, image_rect, images[0] if images else None, theme)
            if show_duration:
                duration_text = f"{duration:g} ms"
                if painter.fontMetrics().horizontalAdvance(duration_text) < rect.width() - 6:
                    painter.drawText(
                        QRectF(rect.left() + 3, bar_y - line_height - 6,
                               rect.width() - 6, line_height),
                        Qt.AlignmentFlag.AlignCenter, duration_text,
                    )
            bar = QRectF(rect.left(), bar_y, rect.width(), 6)
            painter.fillRect(bar, QColor(border))
            if self.active_phase == phase:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(theme.focus_ring), 3))
                painter.drawRect(rect.adjusted(1.5, 1.5, -1.5, -1.5))
        painter.setPen(QColor(theme.text_secondary))
        for text, left, text_width, row, x in self._axis_layout():
            row_y = time_top + row * (line_height + 2)
            painter.drawLine(int(x), bar_y + 7, int(x), row_y - 1)
            painter.drawText(
                QRectF(left, row_y, text_width, line_height),
                Qt.AlignmentFlag.AlignCenter, text,
            )
