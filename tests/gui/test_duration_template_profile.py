"""Duration-aware template edits preserve timing without exposing competing counters."""

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from tests.gui.helpers import assert_visible_children_within_parent

from fpvs_studio.core.models import (
    ConditionDefaults,
    ConditionTemplateDefaults,
    ConditionTemplateProfile,
)
from fpvs_studio.gui.condition_template_profile_editor_dialog import (
    ConditionTemplateProfileEditorDialog,
)


@pytest.mark.parametrize("background", ["#f4f7fb", "#202124"])
def test_profile_editor_preserves_hidden_requested_seconds(qtbot, background):
    profile = ConditionTemplateProfile(
        profile_id="two-minute", display_name="Two minute stream",
        defaults=ConditionTemplateDefaults(condition=ConditionDefaults(stream_duration_seconds=120)),
    )
    dialog = ConditionTemplateProfileEditorDialog(initial_profile=profile)
    qtbot.addWidget(dialog)
    dialog.setPalette(QPalette(QColor(background)))
    dialog.resize(760, 760)
    dialog.show()
    QApplication.processEvents()
    assert_visible_children_within_parent(dialog)
    assert not dialog.sequence_count_spin.isEnabled()
    assert not dialog.oddball_cycles_spin.isEnabled()
    assert dialog.sequence_count_spin.toolTip()
    dialog.description_edit.setText("Retained authored stream duration")
    saved = dialog._build_profile()
    assert saved.defaults.condition.stream_duration_seconds == 120
