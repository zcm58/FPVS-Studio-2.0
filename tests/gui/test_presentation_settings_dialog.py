"""Registered Qt coverage for modular stimulus-presentation authoring."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel
from tests.gui.helpers import _open_created_project, _write_image_directory

from fpvs_studio.core.condition_template_profiles import (
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import (
    ImageGeometryMode,
    PresentationUnit,
    StimulusModality,
    StimulusTransform,
    StimulusVariant,
    TextHeightMode,
)
from fpvs_studio.core.models import (
    ConditionPresentationSettings,
    ImageGeometrySettings,
    ProjectPresentationSettings,
    StimulusPresentationDefaults,
    TextHeightScheduleSettings,
    TextPositionSettings,
)
from fpvs_studio.core.presentation import (
    legacy_project_presentation_settings,
    resolve_role_presentation,
)
from fpvs_studio.gui.condition_template_manager_dialog import _format_profile_details
from fpvs_studio.gui.condition_template_profile_editor_dialog import (
    ConditionTemplateProfileEditorDialog,
)
from fpvs_studio.gui.control_condition_dialog import ControlConditionDialog
from fpvs_studio.gui.controller import StudioController
from fpvs_studio.gui.create_project_dialog import CreateProjectDialog
from fpvs_studio.gui.presentation_settings_dialog import (
    _PREVIEW_SAMPLE_LIMIT,
    PresentationSettingsDialog,
    _PresentationPreview,
    _preview_background_color,
    _representative_sample,
    condition_presentation_summary,
)
from fpvs_studio.gui.runtime_settings_page import ImageSizePreviewDialog


def _apply_button(dialog: PresentationSettingsDialog):
    return dialog.button_box.button(QDialogButtonBox.StandardButton.Apply)


def test_project_presentation_dialog_applies_native_geometry_and_word_defaults(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Presentation Defaults",
    )
    dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(dialog)
    dialog.resize(1000, 640)
    dialog.show()
    QApplication.processEvents()

    editor = dialog._editors["project"]
    assert editor.font_value_label.text() == "Arial (fixed)"
    assert editor.font_value_label.isEnabled()
    assert {
        editor.geometry_mode_combo.itemData(index)
        for index in range(editor.geometry_mode_combo.count())
    } == set(ImageGeometryMode)
    assert {
        editor.transform_combo.itemData(index) for index in range(editor.transform_combo.count())
    } == set(StimulusTransform)
    editor.transform_combo.setCurrentIndex(
        editor.transform_combo.findData(StimulusTransform.MIRROR_VERTICAL)
    )
    editor.geometry_mode_combo.setCurrentIndex(
        editor.geometry_mode_combo.findData(ImageGeometryMode.EXACT_BOX)
    )
    editor.geometry_width_spin.setValue(5.125)
    editor.geometry_height_spin.setValue(6.25)
    editor.text_height_mode_combo.setCurrentIndex(
        editor.text_height_mode_combo.findData(TextHeightMode.BALANCED_RANDOMIZED)
    )
    editor.text_height_unit_combo.setCurrentIndex(
        editor.text_height_unit_combo.findData(PresentationUnit.WINDOW_HEIGHT_FRACTION)
    )
    editor.text_height_values_edit.setText("0.03, 0.04, 0.05, 0.06, 0.07")
    editor.text_color_edit.setText("#F0E68C")
    editor.position_unit_combo.setCurrentIndex(
        editor.position_unit_combo.findData(PresentationUnit.DEGREES)
    )
    editor.position_x_spin.setValue(0.25)
    editor.position_y_spin.setValue(-0.5)
    QApplication.processEvents()

    assert dialog.preview_widget.isVisible()
    assert dialog.preview_widget.rect().right() <= dialog.preview_widget.width()
    qtbot.mouseClick(_apply_button(dialog), Qt.MouseButton.LeftButton)

    defaults = document.project.settings.presentation.defaults
    assert defaults.transform == StimulusTransform.MIRROR_VERTICAL
    assert defaults.image_geometry.mode == ImageGeometryMode.EXACT_BOX
    assert defaults.image_geometry.width_degrees == 5.125
    assert defaults.image_geometry.height_degrees == 6.25
    assert defaults.text_height.mode == TextHeightMode.BALANCED_RANDOMIZED
    assert defaults.text_height.values == [0.03, 0.04, 0.05, 0.06, 0.07]
    assert defaults.text_color == "#F0E68C"
    assert defaults.text_position.x == 0.25
    assert defaults.text_position.y == -0.5
    size_editor = window.setup_wizard_page.image_display_size_editor
    assert "5.125 x 6.25 deg exact box" in size_editor.preview_value_label.text()
    assert size_editor.full_screen_preview_button.isEnabled()
    size_editor.viewing_distance_spin.setValue(78.0)
    QApplication.processEvents()
    assert document.project.settings.presentation.defaults.image_geometry.width_degrees == 5.125
    size_preview = ImageSizePreviewDialog(document)
    qtbot.addWidget(size_preview)
    assert "Exact Box: 5.125 x 6.25 deg" in size_preview.preview_value_label.text()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert _preview_background_color((16, 32, 48)) == "#102030"


def test_presentation_preview_caches_and_invalidates_composited_image_layer(
    qtbot,
    tmp_path: Path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "presentation-preview.png"
    Image.new("RGB", (32, 16), "red").save(image_path)
    preview = _PresentationPreview()
    qtbot.addWidget(preview)
    preview.resize(320, 280)
    preview.show()
    settings = StimulusPresentationDefaults()
    preview.set_preview(
        settings=settings,
        modality=StimulusModality.IMAGE,
        value=image_path,
        height_value=settings.text_height.values[0],
        background="#000000",
    )
    QApplication.processEvents()

    source_key = preview._source_pixmap.cacheKey()
    layer_key = preview._image_layer.cacheKey()
    preview.set_preview(
        settings=settings,
        modality=StimulusModality.IMAGE,
        value=image_path,
        height_value=settings.text_height.values[0],
        background="#000000",
    )
    preview.repaint()
    QApplication.processEvents()
    assert preview._source_pixmap.cacheKey() == source_key
    assert preview._image_layer.cacheKey() == layer_key

    changed_dpr = preview.devicePixelRatioF() + 0.5
    monkeypatch.setattr(
        _PresentationPreview,
        "devicePixelRatioF",
        lambda _preview: changed_dpr,
    )
    preview.repaint()
    QApplication.processEvents()
    dpr_layer_key = preview._image_layer.cacheKey()
    assert dpr_layer_key != layer_key

    exact_settings = StimulusPresentationDefaults(
        image_geometry=ImageGeometrySettings(
            mode=ImageGeometryMode.EXACT_BOX,
            width_degrees=4.0,
            height_degrees=6.0,
        )
    )
    preview.set_preview(
        settings=exact_settings,
        modality=StimulusModality.IMAGE,
        value=image_path,
        height_value=exact_settings.text_height.values[0],
        background="#000000",
    )
    QApplication.processEvents()
    geometry_layer_key = preview._image_layer.cacheKey()
    assert preview._source_pixmap.cacheKey() == source_key
    assert geometry_layer_key != dpr_layer_key

    preview.resize(420, 300)
    QApplication.processEvents()
    resized_layer_key = preview._image_layer.cacheKey()
    assert preview._source_pixmap.cacheKey() == source_key
    assert resized_layer_key != geometry_layer_key

    Image.new("RGB", (48, 24), "green").save(image_path)
    preview.repaint()
    QApplication.processEvents()
    assert preview._source_pixmap.cacheKey() != source_key
    assert preview._source_pixmap.size().width() == 48
    assert preview._source_pixmap.toImage().pixelColor(0, 0).name() == "#008000"
    assert preview._image_layer.cacheKey() != resized_layer_key
    rendered_layer = preview._image_layer.toImage()
    assert rendered_layer.pixelColor(rendered_layer.rect().center()).name() == "#008000"
    assert preview._modality == StimulusModality.IMAGE

    preview.set_preview(
        settings=exact_settings,
        modality=StimulusModality.WORD,
        value="READ",
        height_value=exact_settings.text_height.values[0],
        background="#000000",
    )
    assert preview._image_layer.isNull()
    assert preview._modality == StimulusModality.WORD


def test_project_presentation_dialog_cancel_discards_draft_and_validates_lists(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Presentation Draft",
    )
    original = document.project.settings.presentation.model_copy(deep=True)
    dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(dialog)
    editor = dialog._editors["project"]
    editor.text_height_mode_combo.setCurrentIndex(
        editor.text_height_mode_combo.findData(TextHeightMode.BALANCED_RANDOMIZED)
    )
    editor.text_height_values_edit.setText("0.03, 0.03")

    dialog.accept()
    # The dialog is intentionally not shown in this state-focused test. Check
    # whether validation explicitly unhides the label rather than inherited
    # top-level window visibility.
    assert not dialog.validation_label.isHidden()
    assert "duplicates" in dialog.validation_label.text().lower()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert document.project.settings.presentation == original

    dialog.reject()
    assert document.project.settings.presentation == original


def test_project_presentation_dialog_preserves_legacy_word_height_until_authored(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Legacy Word Height Compatibility",
    )
    legacy = legacy_project_presentation_settings(8.0)
    document.set_project_presentation(legacy)

    no_op_dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(no_op_dialog)
    no_op_dialog.accept()
    assert (
        document.project.settings.presentation.defaults.text_height.legacy_stimulus_width_fraction
        == 0.25
    )

    authored_dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(authored_dialog)
    authored_dialog._editors["project"].text_height_values_edit.setText("2.5")
    authored_dialog.accept()
    assert (
        document.project.settings.presentation.defaults.text_height.legacy_stimulus_width_fraction
        is None
    )


def test_presentation_dialog_no_op_preserves_schema_valid_values_beyond_old_limits(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Unbounded Presentation Values",
    )
    presentation = ProjectPresentationSettings(
        pre_stream_fixation_seconds=75.5,
        defaults=StimulusPresentationDefaults(
            image_geometry=ImageGeometrySettings(
                mode=ImageGeometryMode.EXACT_BOX,
                width_degrees=100.25,
                height_degrees=125.5,
            ),
            text_position=TextPositionSettings(
                unit=PresentationUnit.DEGREES,
                x=15.125,
                y=-18.75,
            ),
            text_height=TextHeightScheduleSettings(values=[0.0123456789]),
        ),
    )
    document.set_project_presentation(presentation)

    dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(dialog)
    editor = dialog._editors["project"]
    assert editor.geometry_width_spin.value() == 100.25
    assert editor.geometry_height_spin.value() == 125.5
    assert editor.position_x_spin.value() == 15.125
    assert editor.position_y_spin.value() == -18.75
    assert editor.text_height_values_edit.text() == "0.0123456789"
    dialog.accept()

    assert document.project.settings.presentation == presentation
    fixation_editor = window.setup_wizard_page.fixation_schedule_editor
    assert fixation_editor.pre_stream_fixation_spin.value() == 75.5


def test_condition_dialog_no_op_preserves_lead_in_beyond_old_limit(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Unbounded Condition Lead In",
    )
    condition_id = document.create_condition(name="Long Lead In")
    presentation = ConditionPresentationSettings(
        pre_stream_fixation_seconds=90.25,
    )
    document.set_condition_presentation(condition_id, presentation)

    dialog = PresentationSettingsDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    assert dialog.condition_lead_in_spin is not None
    assert dialog.condition_lead_in_spin.value() == 90.25
    dialog.accept()

    condition = document.get_condition(condition_id)
    assert condition is not None
    assert condition.presentation == presentation


def test_condition_dialog_resolves_common_and_role_overrides_with_live_sizes(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Condition Presentation",
    )
    condition_id = document.create_condition(name="Mirrored Words")
    document.set_condition_stimulus_modality(
        condition_id,
        modality=StimulusModality.WORD,
    )
    document.update_condition_words(
        condition_id,
        role="base",
        words=["base", "reader"],
    )
    document.update_condition_words(
        condition_id,
        role="oddball",
        words=["target", "mirror"],
    )

    dialog = PresentationSettingsDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)
    dialog.resize(1000, 640)
    dialog.show()
    common = dialog._editors["common"]
    oddball = dialog._editors["oddball"]
    base = dialog._editors["base"]
    assert not base.transform_combo.isEnabled()
    base._override_checks["transform"].setChecked(True)
    assert base.transform_combo.isEnabled()
    base._override_checks["transform"].setChecked(False)
    assert not base.transform_combo.isEnabled()
    common._override_checks["transform"].setChecked(True)
    common.transform_combo.setCurrentIndex(
        common.transform_combo.findData(StimulusTransform.MIRROR_HORIZONTAL)
    )
    oddball._override_checks["text_height"].setChecked(True)
    oddball.text_height_mode_combo.setCurrentIndex(
        oddball.text_height_mode_combo.findData(TextHeightMode.BALANCED_RANDOMIZED)
    )
    oddball.text_height_values_edit.setText("0.03, 0.04, 0.05")
    dialog.condition_lead_in_checkbox.setChecked(True)
    dialog.condition_lead_in_spin.setValue(1.5)
    dialog.preview_role_combo.setCurrentIndex(dialog.preview_role_combo.findData("oddball"))
    QApplication.processEvents()

    assert dialog.preview_modality_combo.currentData() == StimulusModality.WORD
    assert "Arial" in condition_presentation_summary(document, condition_id)
    assert "Natural aspect" not in condition_presentation_summary(document, condition_id)
    assert dialog.preview_stimulus_combo.count() == 2
    assert dialog.preview_size_combo.count() == 3
    assert dialog.preview_size_combo.isEnabled()
    qtbot.mouseClick(_apply_button(dialog), Qt.MouseButton.LeftButton)

    condition = document.get_condition(condition_id)
    assert condition is not None
    assert condition.presentation.common.transform == StimulusTransform.MIRROR_HORIZONTAL
    assert condition.presentation.base.transform is None
    assert condition.presentation.oddball.text_height is not None
    assert condition.presentation.oddball.text_height.values == [0.03, 0.04, 0.05]
    assert condition.presentation.pre_stream_fixation_seconds == 1.5
    summary = condition_presentation_summary(document, condition_id)
    assert "Base: Arial" in summary
    assert "Oddball: Arial" in summary
    assert "balanced randomized" in summary
    effective_base = resolve_role_presentation(
        document.project.settings.presentation,
        condition.presentation,
        "base",
    )
    assert effective_base.transform == StimulusTransform.MIRROR_HORIZONTAL


def test_natural_width_keeps_legacy_size_control_and_native_default_synchronized(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Natural Width Synchronization",
    )
    dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(dialog)
    editor = dialog._editors["project"]
    editor.geometry_mode_combo.setCurrentIndex(
        editor.geometry_mode_combo.findData(ImageGeometryMode.NATURAL_ASPECT)
    )
    editor.natural_dimension_combo.setCurrentIndex(editor.natural_dimension_combo.findData("width"))
    editor.geometry_width_spin.setValue(6.75)
    dialog.accept()

    assert document.project.settings.display.stimulus_width_degrees == 6.75
    assert document.project.settings.presentation.defaults.image_geometry.width_degrees == 6.75

    size_editor = window.setup_wizard_page.image_display_size_editor
    size_editor.width_degrees_spin.setValue(7.5)
    QApplication.processEvents()
    assert document.project.settings.presentation.defaults.image_geometry.width_degrees == 7.5

    height_dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(height_dialog)
    height_editor = height_dialog._editors["project"]
    height_editor.natural_dimension_combo.setCurrentIndex(
        height_editor.natural_dimension_combo.findData("height")
    )
    height_editor.geometry_height_spin.setValue(4.25)
    height_dialog.accept()
    QApplication.processEvents()

    assert not size_editor.width_degrees_spin.isEnabled()
    assert not size_editor.full_screen_preview_button.isEnabled()
    assert "4.25 deg high" in size_editor.preview_value_label.text()
    assert "scaled source preview" in size_editor.full_screen_preview_button.toolTip()


def test_mixed_text_units_use_one_scale_for_clipping_warning(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Mixed Text Units",
    )
    dialog = PresentationSettingsDialog(document)
    qtbot.addWidget(dialog)
    editor = dialog._editors["project"]
    editor.text_height_unit_combo.setCurrentIndex(
        editor.text_height_unit_combo.findData(PresentationUnit.DEGREES)
    )
    editor.text_height_values_edit.setText("1")
    editor.position_unit_combo.setCurrentIndex(
        editor.position_unit_combo.findData(PresentationUnit.WINDOW_HEIGHT_FRACTION)
    )
    editor.position_y_spin.setValue(0.49)
    QApplication.processEvents()

    settings = editor.build_defaults()
    warning = dialog._clipping_warning(
        settings,
        modality=StimulusModality.WORD,
        height_value=1.0,
    )
    assert warning is not None


def test_representative_stimulus_sample_is_bounded_and_spans_full_word_set() -> None:
    values = [f"word-{index}" for index in range(2_228)]
    sample = _representative_sample(values)

    assert len(sample) == _PREVIEW_SAMPLE_LIMIT
    assert sample[0] == values[0]
    assert sample[-1] == values[-1]


def test_condition_preview_resolves_active_derived_variant_assets(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Derived Preview",
    )
    source_id = document.create_condition(name="Faces")
    document.import_condition_stimulus_folder(
        source_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "derived-preview-base"),
    )
    document.import_condition_stimulus_folder(
        source_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "derived-preview-oddball"),
    )
    control_id = document.create_control_condition(
        source_id,
        variant=StimulusVariant.GRAYSCALE,
        name="Grayscale Faces",
    )
    document.materialize_assets()

    dialog = PresentationSettingsDialog(document, condition_id=control_id)
    qtbot.addWidget(dialog)
    paths = [
        dialog.preview_stimulus_combo.itemData(index)
        for index in range(dialog.preview_stimulus_combo.count())
    ]

    assert paths
    assert all(path is not None and "grayscale" in path.as_posix() for path in paths)


def test_condition_preview_rejects_unsafe_persisted_manifest_paths(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, _window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Contained Preview Paths",
    )
    condition_id = document.create_condition(name="Faces")
    document.import_condition_stimulus_folder(
        condition_id,
        role="base",
        source_dir=_write_image_directory(tmp_path / "contained-preview-base"),
    )
    document.import_condition_stimulus_folder(
        condition_id,
        role="oddball",
        source_dir=_write_image_directory(tmp_path / "contained-preview-oddball"),
    )
    base_set = document.get_condition_stimulus_set(condition_id, "base")
    manifest_set = next(item for item in document.manifest.sets if item.set_id == base_set.set_id)
    for asset in manifest_set.assets:
        object.__setattr__(asset.source, "relative_path", "C:/outside/preview.png")

    dialog = PresentationSettingsDialog(document, condition_id=condition_id)
    qtbot.addWidget(dialog)

    assert dialog.preview_stimulus_combo.count() == 1
    assert dialog.preview_stimulus_combo.currentText() == "No example available"
    assert dialog.preview_stimulus_combo.currentData() is None


def test_setup_entry_buttons_open_project_and_condition_dialogs(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
    monkeypatch,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Presentation Entry Points",
    )
    captures: list[str | None] = []

    def _capture_exec(dialog: PresentationSettingsDialog) -> int:
        captures.append(dialog._condition_id)
        return int(QDialog.DialogCode.Rejected)

    monkeypatch.setattr(PresentationSettingsDialog, "exec", _capture_exec)
    guide = window.setup_wizard_page
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="experiment")
    QApplication.processEvents()
    assert guide.image_display_size_editor.configure_presentation_button.isVisible()
    qtbot.mouseClick(
        guide.image_display_size_editor.configure_presentation_button,
        Qt.MouseButton.LeftButton,
    )

    condition_id = document.create_condition(name="Entry Condition")
    guide.open_wizard(step_key="conditions")
    guide.condition_setup_step._select_condition(condition_id)
    QApplication.processEvents()
    assert guide.condition_setup_step.presentation_button.isVisible()
    qtbot.mouseClick(
        guide.condition_setup_step.presentation_button,
        Qt.MouseButton.LeftButton,
    )
    assert captures == [None, condition_id]


def test_fixation_step_authors_pre_stream_gaze_lead_in(
    qtbot,
    controller: StudioController,
    tmp_path: Path,
) -> None:
    document, window = _open_created_project(
        controller,
        qtbot,
        tmp_path,
        "Fixation Lead In",
    )
    guide = window.setup_wizard_page
    window.resize(1120, 720)
    window.show_setup_wizard(step_key="fixation")
    editor = guide.fixation_schedule_editor
    QApplication.processEvents()

    assert editor.pre_stream_fixation_spin.value() == 2.0
    assert "first stimulus and condition trigger" in (
        editor.pre_stream_fixation_note.text().lower()
    )
    editor.pre_stream_fixation_spin.setValue(2.75)
    QApplication.processEvents()
    assert document.project.settings.presentation.pre_stream_fixation_seconds == 2.75
    assert "2.75 s pre-stream gaze lead-in" in guide._fixation_review_line()


def test_experiment_template_editor_exposes_and_saves_presentation_defaults(qtbot) -> None:
    profile = built_in_condition_template_profiles()[0]
    dialog = ConditionTemplateProfileEditorDialog(
        existing_profile_ids=set(),
        initial_profile=profile.model_copy(update={"built_in": False}),
    )
    qtbot.addWidget(dialog)
    dialog.resize(760, 760)
    dialog.show()
    QApplication.processEvents()

    assert [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())] == [
        "General",
        "Presentation",
        "Fixation",
    ]
    editor = dialog.presentation_editor
    assert editor.font_value_label.text() == "Arial (fixed)"
    editor.transform_combo.setCurrentIndex(
        editor.transform_combo.findData(StimulusTransform.MIRROR_HORIZONTAL)
    )
    editor.geometry_mode_combo.setCurrentIndex(
        editor.geometry_mode_combo.findData(ImageGeometryMode.EXACT_BOX)
    )
    editor.geometry_width_spin.setValue(6.25)
    editor.geometry_height_spin.setValue(5.0)
    dialog.pre_stream_fixation_spin.setValue(2.5)

    saved = dialog._build_profile()
    assert saved.defaults.presentation.pre_stream_fixation_seconds == 2.5
    assert saved.defaults.presentation.defaults.transform == StimulusTransform.MIRROR_HORIZONTAL
    assert saved.defaults.presentation.defaults.image_geometry.mode == (ImageGeometryMode.EXACT_BOX)
    details = _format_profile_details(saved)
    assert "Presentation" in details
    assert "Experiment Font: Arial" in details
    assert "Pre-stream fixation: 2.5 seconds" in details


def test_experiment_template_no_op_preserves_values_beyond_old_spin_limits(qtbot) -> None:
    profile = built_in_condition_template_profiles()[0]
    presentation = ProjectPresentationSettings(
        pre_stream_fixation_seconds=82.75,
        defaults=StimulusPresentationDefaults(
            image_geometry=ImageGeometrySettings(
                mode=ImageGeometryMode.EXACT_BOX,
                width_degrees=101.5,
                height_degrees=130.25,
            ),
            text_position=TextPositionSettings(
                unit=PresentationUnit.DEGREES,
                x=17.5,
                y=-21.25,
            ),
            text_height=TextHeightScheduleSettings(values=[0.0123456789]),
        ),
    )
    custom = profile.model_copy(
        update={
            "built_in": False,
            "defaults": profile.defaults.model_copy(
                update={"presentation": presentation},
                deep=True,
            ),
        },
        deep=True,
    )
    dialog = ConditionTemplateProfileEditorDialog(
        existing_profile_ids=set(),
        initial_profile=custom,
    )
    qtbot.addWidget(dialog)

    assert dialog.pre_stream_fixation_spin.value() == 82.75
    assert dialog.presentation_editor.geometry_width_spin.value() == 101.5
    assert dialog.presentation_editor.geometry_height_spin.value() == 130.25
    assert dialog.presentation_editor.position_x_spin.value() == 17.5
    assert dialog.presentation_editor.position_y_spin.value() == -21.25
    assert dialog.presentation_editor.text_height_values_edit.text() == "0.0123456789"

    saved = dialog._build_profile()
    assert saved.defaults.presentation == presentation


def test_experiment_template_editor_preserves_legacy_word_height_on_no_op(qtbot) -> None:
    profile = built_in_condition_template_profiles()[0]
    legacy_defaults = profile.defaults.model_copy(
        update={"presentation": legacy_project_presentation_settings(8.0)},
        deep=True,
    )
    dialog = ConditionTemplateProfileEditorDialog(
        existing_profile_ids=set(),
        initial_profile=profile.model_copy(
            update={"built_in": False, "defaults": legacy_defaults},
            deep=True,
        ),
    )
    qtbot.addWidget(dialog)

    saved = dialog._build_profile()

    assert saved.defaults.presentation.defaults.text_height.legacy_stimulus_width_fraction == 0.25


def test_create_project_uses_experiment_template_language(qtbot) -> None:
    dialog = CreateProjectDialog(condition_template_profiles=built_in_condition_template_profiles())
    qtbot.addWidget(dialog)
    labels = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Experiment Template" in labels
    assert "Image Timing" not in labels
    assert "experiment template" in dialog.condition_profile_combo.placeholderText().lower()


def test_control_dialog_distinguishes_runtime_transforms_from_derived_assets(qtbot) -> None:
    dialog = ControlConditionDialog(source_condition_name="Faces")
    qtbot.addWidget(dialog)
    labels = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    choices = [
        dialog.variant_combo.itemText(index) for index in range(dialog.variant_combo.count())
    ]

    assert "without creating files" in labels
    assert any("Original assets" in choice and "no new files" in choice for choice in choices)
    assert any("create derived assets" in choice for choice in choices)
