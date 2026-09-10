"""Registered visible Qt coverage for source picking and the experimental designer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QObject, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QDragEnterEvent,
    QDropEvent,
    QImage,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QLabel, QMenu, QPushButton
from tests.gui.helpers import assert_visible_children_within_parent, write_image_directory

from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import DutyCycleMode, ExperimentCategory
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.gui.components import apply_experiment_designer_theme
from fpvs_studio.gui.design_system import resolve_studio_theme
from fpvs_studio.gui.designer_sources import import_designer_source, load_designer_thumbnails
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.experiment_designer_dialog import (
    ExperimentDesignerDialog,
    ExperimentDesignerWidget,
)
from fpvs_studio.gui.experiment_designer_widgets import (
    INDEX_MIME,
    ROLE_MIME,
    CycleCanvas,
    ExpandedSlotCanvas,
    SourceCard,
)
from fpvs_studio.preprocessing.importer import import_stimulus_source_directory


def _legacy_ab_profile(category=ExperimentCategory.ATTENTIONAL_BLINK):
    if category != ExperimentCategory.ATTENTIONAL_BLINK:
        return None
    return next(
        profile for profile in built_in_condition_template_profiles()
        if profile.profile_id == ATTENTIONAL_BLINK_PROFILE_ID
    )


@pytest.fixture
def image_document(qtbot, tmp_path: Path) -> tuple[ProjectDocument, str]:
    document = ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Visual designer",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
        condition_template_profile=_legacy_ab_profile(),
    )
    document.update_display_settings(preferred_refresh_hz=120.0)
    condition_id = document.create_condition(
        name="Object recognition with familiar and unfamiliar natural scenes"
    )
    return document, condition_id


@pytest.fixture
def oddball_document(qtbot, tmp_path: Path) -> tuple[ProjectDocument, str]:
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Oddball designer")
    document.update_display_settings(preferred_refresh_hz=120.0)
    condition_id = document.create_condition(name="Object recognition")
    return document, condition_id


def _show_widget(qtbot, widget, width: int, height: int) -> None:
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.show()
    widget.raise_()
    QApplication.processEvents()


def _physical_click(qtbot, widget) -> None:
    """Resolve the rendered hit target instead of directly emitting clicked()."""
    global_position = widget.mapToGlobal(widget.rect().center())
    hit = QApplication.widgetAt(global_position)
    assert hit is widget, f"Expected {widget.objectName() or type(widget).__name__}, got {hit}"
    qtbot.mouseClick(hit, Qt.MouseButton.LeftButton, pos=hit.mapFromGlobal(global_position))
    QApplication.processEvents()


@pytest.mark.parametrize("role", ["base", "t1", "t2"])
def test_source_folder_hit_target_never_adds_a_timeline_block(qtbot, role) -> None:
    card = SourceCard(role, "Base / separator" if role == "base" else role.upper())
    apply_experiment_designer_theme(card)
    card.set_source(24, "C:/Study sources/long reviewed and counterbalanced image folder", ())
    _show_widget(qtbot, card, 430 if role == "base" else 260, 150)
    folder_requests = []
    add_requests = []
    card.folder_requested.connect(folder_requests.append)
    card.add_requested.connect(add_requests.append)

    assert not isinstance(card, QPushButton)
    assert card.folder_button.parentWidget() is card
    assert card.tile.geometry().bottom() < card.folder_button.geometry().top()
    assert card.count_label.text() == "24 images"
    assert abs(card.folder_button.geometry().center().x() - card.rect().center().x()) <= 1
    assert "counterbalanced image folder" in card.folder_button.toolTip()
    assert card.path_label.toolTip() == card.source_path
    assert card.path_label.accessibleDescription() == card.source_path
    assert card.path_label.width() >= card.path_label.fontMetrics().horizontalAdvance(
        card.path_label.text()
    )
    _physical_click(qtbot, card.folder_button)

    assert folder_requests == [role]
    assert add_requests == []
    _physical_click(qtbot, card.tile)
    assert add_requests == [role]
    assert folder_requests == [role]
    assert_visible_children_within_parent(card)


def test_source_tile_keyboard_adds_and_displays_only_provided_thumbnails(qtbot) -> None:
    card = SourceCard("base", "Base / separator")
    pixmaps = []
    for color in ("red", "green", "blue", "yellow"):
        pixmap = QPixmap(16, 12)
        pixmap.fill(QColor(color))
        pixmaps.append(pixmap)
    card.set_source(40, "C:/sources/base", pixmaps)
    _show_widget(qtbot, card, 440, 150)
    requested = []
    card.add_requested.connect(requested.append)

    qtbot.keyClick(card.tile, Qt.Key.Key_Space)
    qtbot.keyClick(card.tile, Qt.Key.Key_Return)

    assert requested == ["base", "base"]
    assert len(card.tile.pixmaps) == 4
    assert [image.cacheKey() for image in card.tile.pixmaps] == [
        image.cacheKey() for image in pixmaps
    ]
    card.set_source(0, "", ())
    assert not card.tile.pixmaps
    assert card.folder_button.text() == "Choose images…"
    assert "No image folder" in card.tile.accessibleDescription()


def _open_canvas(qtbot, roles=("base", "base", "base", "target_pair")) -> CycleCanvas:
    canvas = CycleCanvas()
    canvas.set_roles(roles)
    _show_widget(qtbot, canvas, 960, 156)
    return canvas


def _drop_palette_role(canvas: CycleCanvas, role: str, position: QPoint) -> tuple[bool, bool]:
    mime = QMimeData()
    mime.setData(ROLE_MIME, role.encode("ascii"))
    enter = QDragEnterEvent(
        position, Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(canvas.viewport(), enter)
    drop = QDropEvent(
        QPointF(position), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(canvas.viewport(), drop)
    QApplication.processEvents()
    return enter.isAccepted(), drop.isAccepted()


def test_cycle_keeps_target_pair_inside_one_equal_width_slot(qtbot) -> None:
    canvas = _open_canvas(qtbot)

    assert canvas.count() == 4
    widths = [canvas.slot_rect(index).width() for index in range(canvas.count())]
    assert widths == [widths[0]] * 4
    assert canvas.horizontalScrollBar().maximum() == 0
    assert "4: target pair" in canvas.accessibleDescription()
    enter, drop = _drop_palette_role(canvas, "t1", QPoint(10, 25))
    assert enter and drop
    assert canvas.roles() == ("target_pair", "base", "base", "base", "target_pair")
    assert "t1" not in canvas.roles()
    canvas.setCurrentRow(0)
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert canvas.roles() == ("base", "base", "base", "target_pair")


def test_cycle_light_theme_paints_its_own_legible_viewport(qtbot) -> None:
    canvas = _open_canvas(qtbot)
    palette = QPalette(canvas.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor("#f4f7fb"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#000000"))
    canvas.setPalette(palette)
    QApplication.processEvents()

    rendered = canvas.viewport().grab().toImage()

    assert rendered.pixelColor(1, 1) == QColor(resolve_studio_theme(canvas.palette()).surface)


def test_target_pair_overview_is_readable_while_detail_remains_proportional(qtbot) -> None:
    cycle = _open_canvas(qtbot)
    pair_index = cycle.target_pair_index()
    assert pair_index == 3
    tokens = cycle.pair_thumbnail_rects(pair_index)
    assert len(tokens) == 3
    assert min(token.width() for token in tokens) >= 30
    assert min(token.height() for token in tokens) >= 20
    assert "schematic" in cycle.toolTip()
    expanded = ExpandedSlotCanvas()
    _show_widget(qtbot, expanded, 920, 100)
    expanded.set_timing(15, 50, 185)
    rectangles = expanded.phase_rects()
    total = sum(rect.width() for rect in rectangles)
    assert [rect.width() / total for rect in rectangles] == pytest.approx([0.06, 0.20, 0.74])
    cycle.setCurrentRow(3)
    cycle.move_selected(-1)
    assert cycle.target_pair_index() == 2
    assert cycle.pair_thumbnail_rects(2)[0].width() == pytest.approx(tokens[0].width())
    cycle.remove_selected()
    assert cycle.target_pair_index() is None


def test_cycle_palette_gap_insertion_and_keyboard_order(qtbot) -> None:
    canvas = _open_canvas(qtbot, ("base", "target_pair"))
    left = canvas.slot_rect(0)
    right = canvas.slot_rect(1)
    gap = QPoint(int((left.right() + right.left()) / 2), 25)

    assert _drop_palette_role(canvas, "base", gap) == (True, True)
    assert canvas.roles() == ("base", "base", "target_pair")
    canvas.setCurrentRow(2)
    qtbot.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    assert canvas.roles() == ("base", "target_pair", "base")
    qtbot.keyClick(canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    assert canvas.roles() == ("base", "base", "target_pair")


def test_standard_cycle_reuses_t1_source_as_oddball_and_rejects_t2(qtbot) -> None:
    canvas = _open_canvas(qtbot, ("base",))
    canvas.set_mode("standard")

    assert _drop_palette_role(canvas, "t1", QPoint(900, 25)) == (True, True)
    assert canvas.roles() == ("base", "oddball")
    assert _drop_palette_role(canvas, "t2", QPoint(900, 25)) == (False, False)
    canvas.add_role("t2")
    assert canvas.roles() == ("base", "oddball")


def _drop_existing_slot(canvas, source_index: int, target_index: int, owner=None):
    class EnterEvent(QDragEnterEvent):
        def source(self):
            return canvas

    class DropEvent(QDropEvent):
        def source(self):
            return canvas

    point = canvas.slot_rect(target_index).topLeft().toPoint() + QPoint(2, 15)
    mime = QMimeData()
    mime.setData(INDEX_MIME, f"{id(canvas) if owner is None else owner}:{source_index}".encode())
    enter = EnterEvent(
        point, Qt.DropAction.MoveAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    canvas.dragEnterEvent(enter)
    drop = DropEvent(
        QPointF(point), Qt.DropAction.MoveAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    canvas.dropEvent(drop)
    return enter.isAccepted(), drop.isAccepted()


def test_cycle_internal_drag_preserves_slot_roles(qtbot) -> None:
    canvas = _open_canvas(qtbot)

    assert _drop_existing_slot(canvas, 3, 1) == (True, True)
    assert canvas.roles() == ("base", "target_pair", "base", "base")
    assert canvas.currentRow() == 1
    assert _drop_existing_slot(canvas, 1, 0, owner=-1) == (False, False)
    assert canvas.roles() == ("base", "target_pair", "base", "base")


@pytest.mark.parametrize("action_name", ["Move left", "Move right", "Remove", "Clear cycle"])
def test_cycle_context_menu_has_keyboard_equivalent_actions(
    qtbot, monkeypatch, action_name
) -> None:
    canvas = _open_canvas(qtbot, ("base", "target_pair", "base"))
    canvas.setCurrentRow(1)

    class ChoosingMenu(QMenu):
        def exec(self, *_args):
            return next(action for action in self.actions() if action.text() == action_name)

    monkeypatch.setattr("fpvs_studio.gui.experiment_designer_widgets.QMenu", ChoosingMenu)
    point = canvas.slot_rect(1).center().toPoint()
    canvas.contextMenuEvent(
        QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, point, canvas.mapToGlobal(point))
    )

    expected = {
        "Move left": ("target_pair", "base", "base"),
        "Move right": ("base", "base", "target_pair"),
        "Remove": ("base", "base"),
        "Clear cycle": (),
    }
    assert canvas.roles() == expected[action_name]


def test_long_cycle_scrolls_to_keyboard_selection(qtbot) -> None:
    canvas = _open_canvas(qtbot, ("base",) * 30 + ("target_pair",))
    assert canvas.horizontalScrollBar().maximum() > 0

    canvas.setCurrentRow(30)

    assert canvas.slot_rect(30).right() <= canvas.viewport().width()
    canvas.setCurrentRow(0)
    assert canvas.slot_rect(0).left() >= 0


def test_compact_cycle_keeps_cards_above_the_time_axis(qtbot) -> None:
    canvas = CycleCanvas()
    canvas.setMinimumHeight(88)
    canvas.set_roles(("base", "base", "base", "target_pair"))
    _show_widget(qtbot, canvas, 920, 88)
    axis_top = canvas.viewport().height() - canvas.fontMetrics().height() - 7
    assert all(canvas.slot_rect(index).bottom() < axis_top for index in range(canvas.count()))


@pytest.mark.parametrize("durations", [(50.0, 50.0, 150.0), (25.0, 75.0, 150.0), (50.0, 0, 200.0)])
@pytest.mark.parametrize("height", [100, 156])
def test_expanded_slot_widths_match_actual_durations(qtbot, durations, height) -> None:
    canvas = ExpandedSlotCanvas()
    _show_widget(qtbot, canvas, 920, height)
    canvas.set_timing(*durations)

    rectangles = canvas.phase_rects()
    full_width = sum(rect.width() for rect in rectangles)
    assert [rect.width() / full_width for rect in rectangles] == pytest.approx(
        [duration / sum(durations) for duration in durations]
    )
    assert rectangles[0].right() == pytest.approx(rectangles[1].left())
    assert rectangles[1].right() == pytest.approx(rectangles[2].left())
    assert all(rect.bottom() < canvas.height() for rect in rectangles)
    assert "separator / ISI" in canvas.toolTip()
    canvas.set_active_phase("t2")
    assert canvas.active_phase == "t2"
    canvas.set_active_phase(None)
    assert canvas.active_phase is None


def _open_designer(qtbot, monkeypatch, image_document, *, size=(1040, 760)):
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda self: None)
    document, condition_id = image_document
    dialog = ExperimentDesignerWidget(document, condition_id=condition_id)
    _show_widget(qtbot, dialog, *size)
    dialog.closed.connect(dialog.hide)
    return dialog


def _populate_sources(document, condition_id: str, tmp_path: Path) -> None:
    roles = (
        ("base", "t1", "t2", "isi")
        if document.project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        else ("base", "oddball")
    )
    for role in roles:
        source = write_image_directory(tmp_path / f"source-{role}", count=2)
        summary, stimulus_set = import_stimulus_source_directory(
            source_dir=source, project_root=document.project_root,
            set_id=f"designer-{role}", set_name=f"Designer {role.upper()}", strict=False,
        )
        document.apply_designer_source(
            condition_id, role=role, stimulus_set=stimulus_set, summary=summary,
        )


def test_designer_opens_at_4hz_with_one_250ms_target_pair(
    qtbot, monkeypatch, image_document
) -> None:
    document, _condition_id = image_document
    before = document.project.model_copy(deep=True)
    dialog = _open_designer(qtbot, monkeypatch, image_document)

    assert not hasattr(dialog, "mode_tabs")
    assert dialog.rate_spin.value() == 4.0
    assert dialog.target_spin.value() == 50.0
    assert dialog.isi_spin.value() == 50.0
    assert "150" in dialog.t2_value.text()
    assert dialog.cycle_canvas.roles() == ("base", "base", "base", "target_pair")
    assert dialog.slot_canvas.durations == (50.0, 50.0, 150.0)
    assert all(card.isVisible() for card in (
        dialog.base_source, dialog.t1_source, dialog.t2_source,
    ))
    assert not dialog.timing_details.isVisible()
    assert document.project == before


def test_editable_isi_recalculates_t2_and_rejects_an_overfull_slot(
    qtbot, monkeypatch, image_document
) -> None:
    document, _condition_id = image_document
    before = document.project.model_copy(deep=True)
    dialog = _open_designer(qtbot, monkeypatch, image_document)

    dialog.isi_spin.setValue(75.0)
    QApplication.processEvents()
    assert "125" in dialog.t2_value.text()
    assert dialog.slot_canvas.durations == (50.0, 75.0, 125.0)
    dialog.isi_spin.setValue(225.0)
    QApplication.processEvents()

    assert dialog.status_label.isVisible()
    assert dialog.status_label.text().strip()
    assert not dialog.apply_button.isEnabled()
    assert not dialog.preview_button.isEnabled()
    assert document.project == before




def test_standard_category_preserves_existing_protocol_until_apply(
    qtbot, monkeypatch, oddball_document, tmp_path
) -> None:
    document, _condition_id = oddball_document
    document.update_protocol_settings(base_hz=6.0, oddball_every_n=5)
    _populate_sources(document, _condition_id, tmp_path)
    before = document.project.model_copy(deep=True)
    dialog = _open_designer(qtbot, monkeypatch, oddball_document)

    QApplication.processEvents()
    assert dialog.rate_spin.value() == 6.0
    assert dialog.cycle_canvas.roles() == ("base", "base", "base", "base", "oddball")
    assert not dialog.t2_source.isVisible()
    dialog.rate_spin.setValue(4.0)
    dialog.cycle_canvas.set_roles(("base", "base", "base", "oddball"))
    assert document.project == before
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    assert document.project.settings.protocol.base_hz == 4.0
    assert document.project.settings.protocol.oddball_every_n == 4
    assert document.project.conditions == before.conditions




def test_apply_saves_ab_draft_and_retains_the_independent_t2_source(
    qtbot, monkeypatch, image_document, tmp_path
) -> None:
    document, condition_id = image_document
    _populate_sources(document, condition_id, tmp_path)
    original_condition = document.get_condition(condition_id)
    assert original_condition is not None
    original_t2_id = original_condition.t2_stimulus_set_id
    assert original_t2_id is not None
    disk_before = document.project_file_path.read_bytes()
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    dialog.target_spin.setValue(25.0)
    dialog.isi_spin.setValue(75.0)
    QApplication.processEvents()

    assert dialog.apply_button.isEnabled()
    qtbot.mouseClick(dialog.apply_button, Qt.MouseButton.LeftButton)

    condition = document.get_condition(condition_id)
    assert condition is not None
    assert condition.attentional_blink is not None
    assert condition.attentional_blink.t1_duration_ms == 25.0
    assert condition.attentional_blink.isi_ms == 75.0
    assert condition.t2_stimulus_set_id == original_t2_id
    assert document.get_condition_stimulus_set(condition_id, "t2").image_count == 2
    assert document.project.settings.protocol.base_hz == 4.0
    assert document.project.settings.protocol.oddball_every_n == 4
    assert document.project_file_path.read_bytes() == disk_before


@pytest.mark.parametrize("category", [ExperimentCategory.FPVS_ODDBALL,
                                      ExperimentCategory.ATTENTIONAL_BLINK])
def test_folder_selection_attaches_the_correct_source_without_adding_slots(
    qtbot, monkeypatch, tmp_path, category
) -> None:
    class ImmediateTask(QObject):
        succeeded = Signal(object)
        failed = Signal(object)
        finished = Signal()

        def __init__(self, *, parent_widget, callback):
            super().__init__(parent_widget)
            self._callback = callback

        def start(self):
            try:
                self.succeeded.emit(self._callback())
            except Exception as error:
                self.failed.emit(error)
            finally:
                self.finished.emit()

    monkeypatch.setattr("fpvs_studio.gui.experiment_designer_dialog.BackgroundTask", ImmediateTask)
    document = ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Folder import", experiment_category=category,
        condition_template_profile=_legacy_ab_profile(category),
    )
    condition_id = document.create_condition(name="Target source")
    role = "t2" if category == ExperimentCategory.ATTENTIONAL_BLINK else "oddball"
    folder = write_image_directory(tmp_path / "new-second-target-source", count=3)
    dialog = _open_designer(qtbot, monkeypatch, (document, condition_id))
    original = document.get_condition(condition_id)
    assert original is not None
    old_t1 = original.oddball_stimulus_set_id
    before_roles = dialog.cycle_canvas.roles()
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *_args: str(folder))

    card = dialog.t2_source if role == "t2" else dialog.t1_source
    _physical_click(qtbot, card.folder_button)

    condition = document.get_condition(condition_id)
    assert condition is not None
    if role == "t2":
        assert condition.t2_stimulus_set_id is not None
        assert condition.t2_stimulus_set_id != condition.oddball_stimulus_set_id
        assert condition.oddball_stimulus_set_id == old_t1
    else:
        assert condition.oddball_stimulus_set_id != old_t1
        assert condition.t2_stimulus_set_id is None
        assert "Oddball" in card.folder_button.accessibleName()
        assert "Oddball" in card.tile.accessibleName()
    assert document.get_condition_stimulus_set(condition_id, role).image_count == 3
    assert role in document.get_condition_stimulus_set(condition_id, role).set_id
    assert card.source_count == 3
    assert dialog.cycle_canvas.roles() == before_roles
    assert dialog._task is None


@pytest.mark.parametrize("use_manifest_paths", [True, False])
def test_designer_import_preserves_long_filename_and_decodes_long_destination(
    qapp, tmp_path, use_manifest_paths
) -> None:
    incoming = write_image_directory(tmp_path / "incoming", count=1)
    basename = "reviewed-target-" + "a" * (104 - len("reviewed-target-") - 4) + ".png"
    original = (incoming / "stimulus-01.png").rename(incoming / basename)
    original_bytes = original.read_bytes()
    assert len(basename) == 104
    assert len(str(original)) < 260
    padding = "p" * max(12, 125 - len(str(tmp_path)) - 1)
    project_root = tmp_path / padding
    project_root.mkdir()
    assert len(str(project_root)) >= 119

    summary, source = import_designer_source(
        project_root, "fruit-vs-vegetable", "t2", incoming
    )

    assert source.image_count == 1
    assert source.source_dir is not None
    assert not Path(source.source_dir).is_absolute()
    relative_paths = tuple(record.relative_path for record in summary.files)
    assert len(relative_paths) == 1
    assert Path(relative_paths[0]).name == basename
    destination = project_root / relative_paths[0]
    assert len(str(destination)) > 260
    assert filesystem_path(destination).read_bytes() == original_bytes
    assert original.read_bytes() == original_bytes
    images = load_designer_thumbnails(
        project_root,
        {"t2": (source.source_dir, relative_paths if use_manifest_paths else ())},
    )

    assert len(images["t2"]) == 1
    decoded = images["t2"][0]
    assert not decoded.isNull()
    assert 0 < decoded.width() <= 360
    assert 0 < decoded.height() <= 240
    assert decoded.pixelColor(0, 0) == QColor(20, 10, 5)


def test_closing_discards_unapplied_ab_timing(qtbot, monkeypatch, image_document) -> None:
    document, _condition_id = image_document
    before = document.project.model_copy(deep=True)
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    dialog.target_spin.setValue(35.0)
    dialog.isi_spin.setValue(65.0)
    dialog.cycle_canvas.add_role("base")

    qtbot.mouseClick(dialog.close_button, Qt.MouseButton.LeftButton)

    assert document.project == before


def _inject_thumbnails(dialog: ExperimentDesignerWidget, color="green") -> None:
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    dialog._thumbnails_loaded(
        dialog._thumbnail_revision, {role: [image] for role in ("base", "t1", "t2", "isi")}
    )


def test_slow_preview_stops_on_toggle_edit_and_window_close(
    qtbot, monkeypatch, image_document, tmp_path
) -> None:
    document, condition_id = image_document
    _populate_sources(document, condition_id, tmp_path)
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    _inject_thumbnails(dialog)

    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    assert dialog.preview_window.isVisible()
    assert dialog._preview_timer.isActive()
    assert "4× slower" in dialog.preview_phase_label.text()
    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    assert not dialog._preview_timer.isActive()
    assert not dialog.preview_window.isVisible()
    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    dialog.isi_spin.setValue(75.0)
    assert not dialog._preview_timer.isActive()
    assert not dialog.preview_button.isChecked()
    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    dialog.preview_window.close()
    QApplication.processEvents()
    assert not dialog._preview_timer.isActive()
    assert dialog.slot_canvas.active_phase is None
    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)
    dialog.close()
    QApplication.processEvents()
    assert not dialog._preview_timer.isActive()
    assert not dialog.preview_window.isVisible()


def test_outdated_thumbnail_result_cannot_replace_the_current_source(
    qtbot, monkeypatch, image_document
) -> None:
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    _inject_thumbnails(dialog)
    original = dialog.t1_source.tile.pixmaps[0].cacheKey()
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))

    dialog._thumbnails_loaded(dialog._thumbnail_revision - 1, {"t1": [image]})

    assert dialog.t1_source.tile.pixmaps[0].cacheKey() == original


def test_standard_half_blank_preview_removes_the_image_for_half_of_each_slot(
    qtbot, monkeypatch, oddball_document, tmp_path
) -> None:
    document, condition_id = oddball_document
    _populate_sources(document, condition_id, tmp_path)
    document.update_condition(condition_id, duty_cycle_mode=DutyCycleMode.BLANK_50)
    dialog = _open_designer(qtbot, monkeypatch, oddball_document)
    _inject_thumbnails(dialog)
    dialog.rate_spin.setValue(4.0)
    dialog.cycle_canvas.set_roles(("base", "oddball"))

    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)

    assert dialog._preview_segments == [
        ("base", 125.0, 0), ("blank", 125.0, 0),
        ("t1", 125.0, 1), ("blank", 125.0, 1),
    ]
    assert not dialog.preview_image.pixmap().isNull()
    dialog._advance_preview()
    assert "BLANK" in dialog.preview_phase_label.text()
    assert dialog.preview_image.pixmap().isNull()
    assert dialog.preview_image.text() == ""
    assert dialog._preview_timer.interval() == 500
    dialog._advance_preview()
    assert "ODDBALL" in dialog.preview_phase_label.text()
    assert not dialog.preview_image.pixmap().isNull()


def test_standard_contrast_preview_discloses_modulation_omission(
    qtbot, monkeypatch, oddball_document, tmp_path
) -> None:
    document, condition_id = oddball_document
    _populate_sources(document, condition_id, tmp_path)
    document.update_condition(condition_id, duty_cycle_mode=DutyCycleMode.SINUSOIDAL)
    dialog = _open_designer(qtbot, monkeypatch, oddball_document)
    _inject_thumbnails(dialog)
    dialog.rate_spin.setValue(4.0)
    dialog.cycle_canvas.set_roles(("base", "oddball"))

    qtbot.mouseClick(dialog.preview_button, Qt.MouseButton.LeftButton)

    assert dialog._preview_segments == [("base", 250.0, 0), ("t1", 250.0, 1)]
    assert dialog.preview_note.isVisible()
    assert "contrast modulation is omitted" in dialog.preview_note.text()
    assert document.get_condition(condition_id).duty_cycle_mode == DutyCycleMode.SINUSOIDAL


@pytest.mark.parametrize("close_method", ["request_close", "close"])
def test_close_waits_for_both_import_and_thumbnail_tasks(
    qtbot, monkeypatch, image_document, close_method
) -> None:
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    monkeypatch.setattr(dialog, "_task", object())
    monkeypatch.setattr(dialog, "_thumbnail_task", object())
    dialog._refresh_preview()

    getattr(dialog, close_method)()
    QApplication.processEvents()

    assert dialog._close_requested
    assert dialog.isVisible()
    assert not dialog.apply_button.isEnabled()
    dialog._import_finished()
    assert dialog.isVisible()
    dialog._thumbnail_finished()
    QApplication.processEvents()
    assert not dialog.isVisible()


def test_timing_details_are_optional_and_do_not_change_the_real_display(
    qtbot, monkeypatch, image_document
) -> None:
    document, _condition_id = image_document
    before = document.project.settings.display.model_copy(deep=True)
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    qtbot.mouseClick(dialog.details_button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()

    assert dialog.timing_details.isVisible()
    assert "Achieved" in dialog.details_summary_label.text()
    assert "T1" in dialog.details_summary_label.text()
    assert "T2" in dialog.details_summary_label.text()
    assert_visible_children_within_parent(dialog.timing_details)
    dialog.refresh_combo.setCurrentIndex(dialog.refresh_combo.findData(60.0))
    assert document.project.settings.display == before
    dialog.timing_details.close()
    QApplication.processEvents()
    assert not dialog.details_button.isChecked()
    assert not dialog.timing_details.isVisible()


def test_source_failure_remains_visible_after_task_finishes(
    qtbot, monkeypatch, image_document
) -> None:
    dialog = _open_designer(qtbot, monkeypatch, image_document)
    dialog._task_failed(ValueError("The selected folder contains no supported images."))
    dialog._import_finished()

    assert dialog.status_label.isVisible()
    assert "no supported images" in dialog.status_label.text()


def test_standalone_dialog_hosts_the_same_category_specific_editor(
    qtbot, monkeypatch, image_document, tmp_path
) -> None:
    document, condition_id = image_document
    _populate_sources(document, condition_id, tmp_path)
    monkeypatch.setattr(ExperimentDesignerWidget, "_load_thumbnails", lambda self: None)
    dialog = ExperimentDesignerDialog(document, condition_id=condition_id)
    _show_widget(qtbot, dialog, 1040, 680)
    assert isinstance(dialog.editor, ExperimentDesignerWidget)
    assert not hasattr(dialog.editor, "mode_tabs")
    assert not hasattr(dialog.editor, "mask_spin")
    qtbot.mouseClick(dialog.editor.apply_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize(
    "category", [ExperimentCategory.FPVS_ODDBALL, ExperimentCategory.ATTENTIONAL_BLINK]
)
@pytest.mark.parametrize("size", [(1040, 760), (1400, 920)])
def test_fixed_category_designer_preserves_folder_hit_targets_and_geometry(
    qtbot, monkeypatch, tmp_path, category, size
) -> None:
    document = ProjectDocument.create_new(
        parent_dir=tmp_path, project_name="Category design", experiment_category=category,
        condition_template_profile=_legacy_ab_profile(category),
    )
    condition_id = document.create_condition(name="Familiar and unfamiliar natural object images")
    dialog = _open_designer(qtbot, monkeypatch, (document, condition_id), size=size)
    assert (dialog.width(), dialog.height()) == size
    assert_visible_children_within_parent(dialog)
    assert not hasattr(dialog, "mode_tabs")
    ab = category == ExperimentCategory.ATTENTIONAL_BLINK
    assert dialog.slot_panel.isVisible() == ab
    assert dialog.t2_source.isVisible() == ab
    requests = []

    def cancel_picker(_parent, title, _start):
        requests.append(title)
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", cancel_picker)
    initial = dialog.cycle_canvas.roles()
    for source in dialog._cards().values():
        _physical_click(qtbot, source.folder_button)
        assert dialog.cycle_canvas.roles() == initial
    assert len(requests) == (4 if ab else 2)
    for label in dialog.findChildren(QLabel):
        if label.isVisible() and label.text() and label.wordWrap():
            assert label.height() >= label.heightForWidth(label.width())
