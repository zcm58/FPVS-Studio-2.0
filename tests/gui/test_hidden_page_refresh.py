"""Presentation pages defer document-driven work until they are shown again."""

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from fpvs_studio.gui.assets_pages import AssetsPage
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.home_page import HomePage
from fpvs_studio.gui.run_page import RunPage


def _page(document, page_kind):
    if page_kind == "home":
        return HomePage(document, load_condition_template_profiles=lambda: [])
    if page_kind == "assets":
        return AssetsPage(document)
    return RunPage(document)


@pytest.mark.parametrize(
    "page_kind, validations_per_refresh", [("home", 1), ("assets", 1), ("run", 2)],
)
def test_hidden_pages_skip_validation_and_show_latest_document(
    qtbot, tmp_path, monkeypatch, page_kind, validations_per_refresh,
):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Initial project")
    page = _page(document, page_kind)
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    stack.resize(1120, 820)
    stack.addWidget(page)
    other_page = QWidget()
    stack.addWidget(other_page)
    stack.setCurrentWidget(other_page)
    stack.show()
    QApplication.processEvents()

    original_validation = document.validation_report
    validation_calls = []

    def counted_validation(*, refresh_hz):
        validation_calls.append(refresh_hz)
        return original_validation(refresh_hz=refresh_hz)

    monkeypatch.setattr(document, "validation_report", counted_validation)
    row_calls = []
    original_rows = document.condition_rows

    def counted_rows():
        row_calls.append(True)
        return original_rows()

    monkeypatch.setattr(document, "condition_rows", counted_rows)
    document.update_project_name("Intermediate project")
    document.create_condition(name="Latest condition")
    document.update_project_name("Latest project")
    document.manifest_changed.emit()
    document.session_plan_changed.emit()
    QApplication.processEvents()
    assert validation_calls == []
    assert row_calls == []

    stack.setCurrentWidget(page)
    QApplication.processEvents()
    assert len(validation_calls) == validations_per_refresh
    if page_kind == "home":
        assert page.current_project_header.toolTip() == "Latest project"
        assert page.condition_count_value.text() == "1"
        assert not page.launch_button.isEnabled()
        assert page.edit_setup_button.text() == "Complete Setup"
    elif page_kind == "assets":
        assert row_calls == [True]
        assert page.assets_table.rowCount() == 2
        assert page.assets_table.item(0, 0).text() == "Latest condition"
    else:
        expected = original_validation(refresh_hz=page.current_refresh_hz())
        assert page.summary_text.toPlainText() == "\n".join(
            f"- {issue.message}" for issue in expected.issues
        )

    # Visible notifications remain synchronous, including launch readiness changes.
    validation_calls.clear()
    document.update_project_name("Visible update")
    assert len(validation_calls) == validations_per_refresh
    if page_kind == "home":
        assert page.current_project_header.toolTip() == "Visible update"


@pytest.mark.parametrize(
    "page_kind, validations_per_refresh", [("home", 1), ("assets", 1), ("run", 2)],
)
def test_explicit_hidden_refresh_is_synchronous_and_prevents_duplicate_show_refresh(
    qtbot, tmp_path, monkeypatch, page_kind, validations_per_refresh,
):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Explicit refresh")
    page = _page(document, page_kind)
    qtbot.addWidget(page)
    original_validation = document.validation_report
    validation_calls = []

    def counted_validation(*, refresh_hz):
        validation_calls.append(refresh_hz)
        return original_validation(refresh_hz=refresh_hz)

    monkeypatch.setattr(document, "validation_report", counted_validation)
    document.update_project_name("Refreshed before showing")
    assert not validation_calls
    page.refresh()
    assert len(validation_calls) == validations_per_refresh
    page.resize(1120, 820)
    page.show()
    QApplication.processEvents()
    assert len(validation_calls) == validations_per_refresh


def test_hidden_run_session_change_is_reflected_when_shown(qtbot, tmp_path, monkeypatch):
    document = ProjectDocument.create_new(parent_dir=tmp_path, project_name="Session preview")
    page = RunPage(document)
    qtbot.addWidget(page)
    validation_calls = []
    original_validation = document.validation_report

    def counted_validation(*, refresh_hz):
        validation_calls.append(refresh_hz)
        return original_validation(refresh_hz=refresh_hz)

    monkeypatch.setattr(document, "validation_report", counted_validation)
    # No compilation or runtime launch is needed to exercise the presentation signal.
    document._last_session_plan = SimpleNamespace(
        session_id="latest-preview", random_seed=23, block_count=2, total_runs=6,
        refresh_hz=60.0, blocks=[],
    )
    document.session_plan_changed.emit()
    assert validation_calls == []
    assert "latest-preview" not in page.summary_text.toPlainText()

    page.resize(1120, 820)
    page.show()
    QApplication.processEvents()
    assert "Session ID: latest-preview" in page.summary_text.toPlainText()
    assert "Run Count: 6" in page.summary_text.toPlainText()

    page.hide()
    document.update_project_name("Preview invalidated")
    validation_calls.clear()
    document.session_plan_changed.emit()
    assert not validation_calls
    page.show()
    QApplication.processEvents()
    assert "latest-preview" not in page.summary_text.toPlainText()
