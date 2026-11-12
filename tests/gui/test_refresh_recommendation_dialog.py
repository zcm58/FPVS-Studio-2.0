"""Registered visible smoke for the Windows refresh-rate advisory."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, QRect, Qt, Signal
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from tests.gui.helpers import assert_visible_children_within_parent
from tests.platform_adapters import set_module_platform

from fpvs_studio.gui import refresh_recommendation_dialog as advisory
from fpvs_studio.runtime.windows_display import WindowsRefreshRecommendation


def _assert_dialog_fit(dialog, size):
    QApplication.processEvents()
    assert dialog.size().toTuple() == size
    assert_visible_children_within_parent(dialog)
    for label in dialog.findChildren(QLabel):
        if not label.isVisible():
            continue
        rect = label.contentsRect()
        required = label.fontMetrics().boundingRect(
            QRect(0, 0, rect.width(), 1000), Qt.TextFlag.TextWordWrap, label.text(),
        )
        assert rect.width() >= required.width(), label.text()
        assert rect.height() >= required.height(), label.text()
    for button in (dialog.settings_button, dialog.continue_button):
        assert button.width() >= button.fontMetrics().horizontalAdvance(button.text())


@pytest.mark.parametrize("size", [(520, 280), (560, 300)])
@pytest.mark.parametrize(
    ("rates", "has_supported_upgrade", "guidance"),
    [
        ((120,), True, "Choose 120 Hz in Windows for Studio timing checks."),
        ((144, 360), True, "Choose 144 Hz in Windows for Studio timing checks."),
        (
            (360,), False,
            "60 Hz is the highest Studio-supported rate Windows reported at this resolution.",
        ),
    ],
)
def test_recommendation_copy_actions_and_fit(
    qtbot, monkeypatch, size, rates, has_supported_upgrade, guidance,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    dialog = advisory.RefreshRecommendationDialog(
        WindowsRefreshRecommendation(7680, 4320, rates), parent,
        display_device_name=r"\\.\DISPLAY12",
    )
    qtbot.addWidget(dialog)
    open_settings = Mock(side_effect=[False, True])
    monkeypatch.setattr(advisory.QDesktopServices, "openUrl", open_settings)
    dialog.resize(*size)
    dialog.open()
    qtbot.waitUntil(dialog.isVisible)

    visible_text = [label.text() for label in dialog.findChildren(QLabel) if label.isVisible()]
    assert f"60 Hz in use · {max(rates)} Hz available" in visible_text
    assert guidance in visible_text
    assert dialog.details_label.text() == "Display 12 · 7680 × 4320"
    assert dialog.settings_hint.isVisible() == has_supported_upgrade
    if has_supported_upgrade:
        assert "Check refresh rate" in dialog.settings_hint.text()
    assert not dialog.settings_error.isVisible()
    assert dialog.settings_button.isDefault() == has_supported_upgrade
    assert dialog.continue_button.isDefault() == (not has_supported_upgrade)
    _assert_dialog_fit(dialog, size)

    if has_supported_upgrade:
        qtbot.keyClick(dialog, Qt.Key.Key_Return)
    else:
        dialog.settings_button.click()
    assert dialog.isVisible()
    open_settings.assert_called_once()
    assert dialog.settings_error.isVisible()
    assert "could not open" in dialog.settings_error.text()
    assert "System → Display → Advanced display" in dialog.settings_error.text()
    assert dialog.settings_hint.isVisible() == has_supported_upgrade
    if has_supported_upgrade:
        assert "Check refresh rate" in dialog.settings_hint.text()
    _assert_dialog_fit(dialog, size)

    finished = dialog.rejected if has_supported_upgrade else dialog.accepted
    with qtbot.waitSignal(finished):
        qtbot.keyClick(dialog, Qt.Key.Key_Return)
    settings_opens = 2 if has_supported_upgrade else 1
    assert [call.args[0].toString() for call in open_settings.call_args_list] == (
        ["ms-settings:display-advanced"] * settings_opens
    )


class _ImmediateTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, *, parent_widget, callback):
        super().__init__(parent_widget)
        self.callback = callback

    def start(self):
        self.succeeded.emit(self.callback())
        self.finished.emit()


def test_selected_display_reaches_advisory_and_pending_selector_blocks_overlap(qtbot, monkeypatch):
    set_module_platform(monkeypatch, advisory, "win32")
    monkeypatch.setattr(advisory, "BackgroundTask", _ImmediateTask)
    probe = Mock(return_value=WindowsRefreshRecommendation(7680, 4320, (120,)))
    monkeypatch.setattr(advisory, "query_windows_refresh_recommendation", probe)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    proceed = Mock()
    parent.setProperty("experimentDisplaySelectionPending", True)
    advisory.check_windows_refresh(parent, proceed, display_device_name=r"\\.\DISPLAY12")
    probe.assert_not_called()
    proceed.assert_not_called()
    parent.setProperty("experimentDisplaySelectionPending", False)
    advisory.check_windows_refresh(parent, proceed, display_device_name=r"\\.\DISPLAY12")
    probe.assert_called_once_with(r"\\.\DISPLAY12")
    proceed.assert_not_called()
    dialog = parent.findChild(advisory.RefreshRecommendationDialog)
    assert dialog is not None and dialog.isModal()
    assert dialog.details_label.text() == "Display 12 · 7680 × 4320"
    dialog.continue_button.click()
    proceed.assert_called_once_with()


@pytest.mark.parametrize("choice", ["continue", "dismiss", "no_higher_rate"])
def test_gate_resumes_only_when_allowed(qtbot, monkeypatch, choice):
    set_module_platform(monkeypatch, advisory, "win32")
    monkeypatch.setattr(advisory, "BackgroundTask", _ImmediateTask)
    probe = Mock(return_value=(
        None if choice == "no_higher_rate" else WindowsRefreshRecommendation(1920, 1080, (120,))
    ))
    monkeypatch.setattr(advisory, "query_windows_refresh_recommendation", probe)
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    proceed = Mock()
    advisory.check_windows_refresh(parent, proceed)
    dialog = parent.findChild(advisory.RefreshRecommendationDialog)
    if choice == "no_higher_rate":
        assert dialog is None
        proceed.assert_called_once_with()
        return
    assert dialog is not None and dialog.isModal()
    advisory.check_windows_refresh(parent, proceed)
    probe.assert_called_once_with()
    proceed.assert_not_called()
    if choice == "continue":
        dialog.continue_button.click()
        proceed.assert_called_once_with()
    else:
        dialog.reject()
        proceed.assert_not_called()
