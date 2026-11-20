"""Native whole-experiment library view; services own credentials and downloads."""

from __future__ import annotations

import socket
from collections import Counter
from html import escape
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, Qt, QUrl, QVariantAnimation, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QResizeEvent, QTextOption
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.enums import ExperimentCategory
from fpvs_studio.core.experiment_categories import experiment_category_label
from fpvs_studio.core.library_installations import (
    InstalledLibraryProject,
    LibraryInstallStatus,
    library_install_status,
)
from fpvs_studio.core.library_origin import LibraryScope
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_library_dialog_theme,
    configure_setup_form,
    mark_primary_action,
    mark_text_role,
    refresh_widget_style,
    widget_animation_duration,
)
from fpvs_studio.gui.design_system import (
    FONT_SIZE_BODY,
    FONT_SIZE_PAGE_TITLE,
    FONT_SIZE_SECTION_TITLE,
    resolve_studio_theme,
)
from fpvs_studio.gui.library_access_dialog import STUDIO_ACCOUNT_URL
from fpvs_studio.library.models import LibraryCatalog, LibraryConnection, LibraryItem

_RowKey = tuple[LibraryScope, str, str]
_SummaryKey = tuple[LibraryScope, str, str, str]
_SCOPES: tuple[LibraryScope, ...] = ("public", "lab")
_ODDBALL_DEMO_ID = "color-oddball-demo"
_ODDBALL_DEMO_TITLE = "FPVS Oddball Demo"
_ODDBALL_DEMO_PREVIEWS = Path(__file__).resolve().parents[1] / "assets" / "oddball-demo"


def _label(text: str, parent: QWidget, *, supporting: bool = False) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if supporting:
        mark_text_role(label, "supporting")
    return label


def _format_size(size_bytes: int) -> str:
    return (
        f"{size_bytes / 1024:.1f} KB" if size_bytes < 1048576 else f"{size_bytes / 1048576:.1f} MB"
    )


def _summary_key(item: LibraryItem, scope: LibraryScope) -> _SummaryKey:
    return scope, item.item_id, item.version, item.sha256


def _display_title(item: LibraryItem, scope: LibraryScope) -> str:
    if scope == "public" and item.item_id == _ODDBALL_DEMO_ID:
        return _ODDBALL_DEMO_TITLE
    return item.title


def _oddball_demo_preview(text_secondary: str) -> str:
    strips = []
    for color in ("red", "green"):
        url = escape((_ODDBALL_DEMO_PREVIEWS / f"{color}.png").as_uri(), quote=True)
        strips.append(f"""
            <p style="margin-top: 12px; margin-bottom: 4px"><b>{color.title()} oddballs</b></p>
            <p style="margin-top: 0; margin-bottom: 0">
            <img src="{url}" width="484" height="44"
                 alt="Two cycles of four grayscale objects followed by one {color} object"></p>
        """)
    return f"""
        <h2 style="font-size: {FONT_SIZE_SECTION_TITLE}px; margin-top: 20px; margin-bottom: 4px">
        Experiment preview</h2>
        <p style="color: {text_secondary}; margin-top: 0; margin-bottom: 0">
        Download this demo to see what FPVS experiments look like and practice setting up a new
        project from the OpenFPVS Experiment Library.</p>
        {''.join(strips)}
    """


class _ProjectRow(QPushButton):
    def __init__(
        self, item: LibraryItem, parent: QWidget, *, title: str, show_version: bool,
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.display_title = title
        self._title = f"{title} · {item.version}" if show_version else title
        self._elide_mode = (
            Qt.TextElideMode.ElideMiddle if show_version else Qt.TextElideMode.ElideRight
        )
        self.category = experiment_category_label(ExperimentCategory(item.experiment_category))
        self.installation: LibraryInstallStatus | None = None
        self._status = ""
        self.setProperty("libraryProject", "true")
        self.setAutoDefault(False)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(self._title)
        self.setText(self._title)

    def set_installation(self, installation: LibraryInstallStatus | None) -> None:
        self.installation = installation
        state = installation.state if installation is not None else "unchecked"
        self._status = {
            "installed": "Installed",
            "update": "Installed · update available",
            "review": "Possible local copy",
        }.get(state, "")
        self.setAccessibleDescription(self._status)
        self.setToolTip("\n".join(filter(None, (self._title, self._status))))
        if self.property("libraryInstallation") != state:
            self.setProperty("libraryInstallation", state)
            refresh_widget_style(self)
        self._update_text()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_text()

    def _update_text(self) -> None:
        width = max(0, self.width() - 26)
        title = self.fontMetrics().elidedText(self._title, self._elide_mode, width)
        self.setText(f"{title}\n{self._status}" if self._status else title)


class LibraryDialog(QDialog):
    """Browse editable local experiment copies at 900x640 minimum / 1040x760 default."""

    action_requested = Signal(str)
    summary_requested = Signal()
    closing = Signal()

    def __init__(self, *, openfpvs: bool = True) -> None:
        super().__init__()
        self.setObjectName("experiment_library_dialog")
        self.setWindowTitle("FPVS Studio Experiment Library")
        self.setMinimumSize(900, 640)
        self.resize(1040, 760)
        self.setModal(True)
        self._busy = False
        self._downloading = False
        self._openfpvs = openfpvs
        self._connection: LibraryConnection | None = None
        self._catalogs: dict[LibraryScope, LibraryCatalog | None] = dict.fromkeys(_SCOPES)
        self._loading: set[LibraryScope] = set()
        self._section_errors: dict[LibraryScope, str] = dict.fromkeys(_SCOPES, "")
        self._rows: dict[_RowKey, _ProjectRow] = {}
        self._selected: _RowKey | None = None
        self._selection_explicit = False
        self._installations: tuple[InstalledLibraryProject, ...] | None = None
        self._service_url = ""
        self._condition_counts: dict[_SummaryKey, int | None] = {}
        self._status_override = ""
        self._reveal_widget: QWidget | None = None
        self._reveal_animation = QVariantAnimation(self)
        self._reveal_animation.setStartValue(0.90)
        self._reveal_animation.setEndValue(1.0)
        self._reveal_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal_animation.valueChanged.connect(self._reveal_step)
        self._reveal_animation.finished.connect(self._finish_reveal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.header = DialogHeader("Experiment Library", "", parent=self)
        self.header.subtitle_label.hide()
        layout.addWidget(self.header)

        workspace = QFrame(self)
        workspace.setObjectName("library_workspace")
        columns = QHBoxLayout(workspace)
        columns.setContentsMargins(1, 1, 1, 1)
        columns.setSpacing(0)
        sidebar = QWidget(workspace)
        sidebar.setObjectName("library_sidebar")
        sidebar.setMinimumWidth(272)
        sidebar.setMaximumWidth(352)
        browse = QVBoxLayout(sidebar)
        browse.setContentsMargins(14, 14, 12, 12)
        browse.setSpacing(12)
        self.search_edit = QLineEdit(sidebar)
        self.search_edit.setObjectName("library_search")
        self.search_edit.setPlaceholderText("Search experiments")
        self.search_edit.setAccessibleName("Search experiments")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter)
        browse.addWidget(self.search_edit)

        scroll = QScrollArea(sidebar)
        scroll.setObjectName("library_catalog_scroll")
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        groups = QWidget(scroll)
        groups.setObjectName("library_catalog_groups")
        group_layout = QVBoxLayout(groups)
        group_layout.setContentsMargins(0, 0, 3, 0)
        group_layout.setSpacing(14)
        self.public_section = QWidget(groups)
        public_layout = self._section(self.public_section, "Public projects")
        self.public_status = _label("", self.public_section, supporting=True)
        self.public_retry = self._button(
            "Retry public projects", "refresh-public", self.public_section,
        )
        public_layout.addWidget(self.public_status)
        public_layout.addWidget(self.public_retry, alignment=Qt.AlignmentFlag.AlignLeft)
        self.public_section.setVisible(openfpvs)
        group_layout.addWidget(self.public_section)
        divider = QFrame(groups)
        divider.setObjectName("library_group_divider")
        divider.setFixedHeight(1)
        divider.setVisible(openfpvs)
        group_layout.addWidget(divider)

        self.lab_section = QWidget(groups)
        lab_layout = self._section(self.lab_section, "Lab projects" if openfpvs else "Experiments")
        self.connection_label = _label("", self.lab_section, supporting=True)
        lab_layout.addWidget(self.connection_label)
        self.connect_toggle = QPushButton("Connect to a lab", self.lab_section)
        self.connect_toggle.setAutoDefault(False)
        self.connect_toggle.clicked.connect(self._toggle_connection)
        lab_layout.addWidget(self.connect_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.connection_fields = QWidget(self.lab_section)
        connection_layout = QVBoxLayout(self.connection_fields)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        connection_layout.setSpacing(5)
        self.sign_in_button = QPushButton("Sign in to OpenFPVS", self.connection_fields)
        self.sign_in_button.setAutoDefault(False)
        self.sign_in_button.setVisible(openfpvs)
        self.sign_in_button.clicked.connect(self._open_sign_in)
        connection_layout.addWidget(self.sign_in_button, alignment=Qt.AlignmentFlag.AlignLeft)
        form = QFormLayout()
        self.code_edit = QLineEdit(self.connection_fields)
        self.code_edit.setObjectName("library_access_code")
        self.code_edit.setMaxLength(128)
        self.code_edit.setEchoMode(QLineEdit.EchoMode.Password)
        code_label = "Computer code" if openfpvs else "Enrollment code"
        self.code_edit.setPlaceholderText(code_label)
        code_guidance = (
            "Generate a one-time computer code from your OpenFPVS account."
            if openfpvs else "Enter the enrollment code for your Library service."
        )
        self.code_edit.setToolTip(code_guidance)
        self.code_edit.setAccessibleDescription(code_guidance)
        self.device_edit = QLineEdit(socket.gethostname()[:80], self.connection_fields)
        self.device_edit.setObjectName("library_device_name")
        self.device_edit.setMaxLength(80)
        form.addRow(code_label, self.code_edit)
        form.addRow("Computer name", self.device_edit)
        configure_setup_form(form, stacked=True)
        connection_layout.addLayout(form)
        self.connect_button = self._button("Connect", "connect", self.connection_fields)
        connection_layout.addWidget(self.connect_button, alignment=Qt.AlignmentFlag.AlignLeft)
        lab_layout.addWidget(self.connection_fields)
        self.connection_fields.setVisible(not openfpvs)

        connection_actions = QHBoxLayout()
        connection_actions.setContentsMargins(0, 0, 0, 0)
        connection_actions.setSpacing(6)
        self.refresh_button = self._button("Refresh", "refresh", self.lab_section)
        self.disconnect_button = self._button("Disconnect", "disconnect", self.lab_section)
        self.disconnect_button.setToolTip("Disconnect this computer from the lab.")
        connection_actions.addWidget(self.refresh_button)
        connection_actions.addWidget(self.disconnect_button)
        connection_actions.addStretch(1)
        lab_layout.addLayout(connection_actions)
        self.lab_status = _label("", self.lab_section, supporting=True)
        lab_layout.addWidget(self.lab_status)
        self._row_layouts: dict[LibraryScope, QVBoxLayout] = {
            "public": public_layout, "lab": lab_layout,
        }
        group_layout.addWidget(self.lab_section)
        group_layout.addStretch(1)
        scroll.setWidget(groups)
        browse.addWidget(scroll, 1)
        columns.addWidget(sidebar, 1)

        self.details = QTextBrowser(workspace)
        self.details.setObjectName("library_experiment_details")
        self.details.setAccessibleName("Selected experiment details")
        self.details.setOpenExternalLinks(False)
        self.details.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.details.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        columns.addWidget(self.details, 2)
        layout.addWidget(workspace, 1)

        footer = QHBoxLayout()
        feedback = QVBoxLayout()
        feedback.setContentsMargins(0, 0, 0, 0)
        feedback.setSpacing(4)
        self.status_label = _label("", self, supporting=True)
        self.status_label.setObjectName("library_status")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        feedback.addWidget(self.status_label)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setAccessibleName("Experiment download")
        self.progress_bar.setMaximumWidth(260)
        self.progress_bar.hide()
        feedback.addWidget(self.progress_bar)
        footer.addLayout(feedback, 1)
        self.cancel_button = self._button("Cancel operation", "cancel", self)
        self.cancel_button.hide()
        footer.addWidget(self.cancel_button)
        self.install_button = self._button("Download and set up experiment", "install", self)
        self.install_button.setObjectName("library_install")
        mark_primary_action(self.install_button)
        footer.addWidget(self.install_button)
        layout.addLayout(footer)
        self.code_edit.textChanged.connect(self._sync_actions)
        self.device_edit.textChanged.connect(self._sync_actions)
        self.set_connection(None)
        apply_library_dialog_theme(self)

    @staticmethod
    def _section(parent: QWidget, title: str) -> QVBoxLayout:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        heading = _label(title, parent)
        mark_text_role(heading, "sectionTitle")
        layout.addWidget(heading)
        return layout

    def _button(self, label: str, action: str, parent: QWidget) -> QPushButton:
        button = QPushButton(label, parent)
        button.setAutoDefault(False)
        button.clicked.connect(lambda: self.action_requested.emit(action))
        return button

    def _open_sign_in(self) -> None:
        if not QDesktopServices.openUrl(QUrl(STUDIO_ACCOUNT_URL)):
            self.set_catalog_state(
                "lab", error=f"Could not open your browser. Visit {STUDIO_ACCOUNT_URL}.",
            )

    def _toggle_connection(self) -> None:
        opening = self.connection_fields.isHidden()
        self.connection_fields.setVisible(opening)
        self.connect_toggle.setText("Hide connection options" if opening else "Connect to a lab")
        if opening:
            self._animate_reveal(self.connection_fields)

    def set_connection(self, connection: LibraryConnection | None) -> None:
        previous = self._connection
        self._connection = connection
        if previous is not None or connection is not None:
            self.connection_fields.setVisible(connection is None and not self._openfpvs)
            self.connect_toggle.setText("Connect to a lab")
        if connection is not None:
            self.code_edit.clear()
        if connection is None or previous != connection:
            self.set_catalog(None)
        self._sync_connection_label()
        self._sync_actions()

    def set_catalog(self, catalog: LibraryCatalog | None) -> None:
        self._set_catalog("lab", catalog)

    def set_public_catalog(self, catalog: LibraryCatalog | None) -> None:
        self._set_catalog("public", catalog)

    def _set_catalog(self, scope: LibraryScope, catalog: LibraryCatalog | None) -> None:
        first_public_load = (
            scope == "public" and self._catalogs[scope] is None and not self._selection_explicit
        )
        if first_public_load:
            self._selected = None
        self._catalogs[scope] = catalog
        current_keys = {_summary_key(item, scope) for item in catalog.items} if catalog else set()
        self._condition_counts = {
            key: count for key, count in self._condition_counts.items()
            if key[0] != scope or (count is not None and key in current_keys)
        }
        for key in tuple(self._rows):
            if key[0] == scope:
                row = self._rows.pop(key)
                self._row_layouts[scope].removeWidget(row)
                row.hide()
                row.deleteLater()
        parent = self.public_section if scope == "public" else self.lab_section
        items = catalog.items if catalog else ()
        titles = [_display_title(item, scope) for item in items]
        title_counts = Counter(title.casefold() for title in titles)
        for item, title in zip(items, titles, strict=True):
            key = (scope, item.item_id, item.version)
            row = _ProjectRow(
                item, parent, title=title, show_version=title_counts[title.casefold()] > 1,
            )
            self._sync_row_installation(row)
            row.clicked.connect(lambda _checked=False, key=key: self._select(key))
            self._row_layouts[scope].addWidget(row)
            self._rows[key] = row
        self._sync_connection_label()
        self._filter()
        self._sync_tab_order()

    def _sync_tab_order(self) -> None:
        public_rows = [row for key, row in self._rows.items() if key[0] == "public"]
        lab_rows = [row for key, row in self._rows.items() if key[0] == "lab"]
        order = [
            self.search_edit, *public_rows, self.public_retry, self.connect_toggle,
            self.sign_in_button, self.code_edit, self.device_edit, self.connect_button,
            self.refresh_button, self.disconnect_button, *lab_rows, self.details,
            self.cancel_button, self.install_button,
        ]
        for first, second in zip(order, order[1:], strict=False):
            QWidget.setTabOrder(first, second)

    def set_catalog_state(
        self, scope: LibraryScope, *, loading: bool = False, error: str = "",
    ) -> None:
        if loading:
            self._loading.add(scope)
        else:
            self._loading.discard(scope)
        self._section_errors[scope] = error
        self._sync_section_status()
        self._sync_actions()

    @property
    def can_download(self) -> bool:
        catalog = self._catalogs[self.selected_scope()] if self._selected else None
        return catalog is not None and catalog.access_level == "download" and (
            self.selected_scope() == "public" or self._connection is not None
        )

    def _sync_connection_label(self) -> None:
        connection = self._connection
        self.connect_toggle.setVisible(self._openfpvs and connection is None)
        self.refresh_button.setVisible(connection is not None)
        self.disconnect_button.setVisible(connection is not None)
        if connection is None:
            self.connection_label.setText(
                "Connect to see projects shared by your lab."
                if self._openfpvs else "Enter your Library enrollment code to connect."
            )
            self.connection_label.setToolTip("")
            return
        metadata = self._catalogs["lab"] or connection
        permission = "View-only access" if metadata.access_level == "view" else "Download access"
        lab_name = metadata.lab_name or metadata.library_name
        self.connection_label.setText(f"{lab_name} · {permission}")
        self.connection_label.setToolTip(
            f"{metadata.library_name}\nComputer: {connection.device_name}",
        )

    def selected_item(self) -> LibraryItem | None:
        row = self._rows.get(self._selected) if self._selected else None
        return row.item if row is not None else None

    def selected_scope(self) -> LibraryScope:
        return self._selected[0] if self._selected else "lab"

    def set_installations(
        self, projects: tuple[InstalledLibraryProject, ...] | None, service_url: str,
    ) -> None:
        self._installations = projects
        self._service_url = service_url
        for row in self._rows.values():
            self._sync_row_installation(row)
        self._selection_changed()

    def _sync_row_installation(self, row: _ProjectRow) -> None:
        item = row.item
        row.set_installation(
            library_install_status(
                self._installations, service_url=self._service_url,
                item_id=item.item_id, version=item.version, title=item.title,
            ) if self._installations is not None else None,
        )

    def selected_installation(self) -> LibraryInstallStatus | None:
        row = self._rows.get(self._selected) if self._selected else None
        return row.installation if row else None

    def needs_condition_count(self, item: LibraryItem, scope: LibraryScope) -> bool:
        return self.can_download and _summary_key(item, scope) not in self._condition_counts

    def set_condition_count(
        self, item: LibraryItem, scope: LibraryScope, count: int | None,
    ) -> None:
        key = _summary_key(item, scope)
        catalog = self._catalogs[scope]
        if catalog is None or item not in catalog.items:
            return
        self._condition_counts[key] = count
        selected = self.selected_item()
        if selected is not None and _summary_key(selected, self.selected_scope()) == key:
            self._render_details(selected)

    def set_busy(self, busy: bool, message: str = "", *, downloading: bool = False) -> None:
        restore_focus = not busy and self.cancel_button.hasFocus()
        self._busy = busy
        self._downloading = downloading
        self._status_override = message
        self._sync_footer()
        self.progress_bar.setVisible(downloading)
        self.progress_bar.setValue(0)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(busy)
        self._sync_actions()
        if downloading:
            self.cancel_button.setFocus(Qt.FocusReason.OtherFocusReason)
        elif restore_focus and self.install_button.isEnabled():
            self.install_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def show_progress(self, received: int, total: int) -> None:
        self.progress_bar.setValue(min(100, max(0, round(100 * received / max(1, total)))))
        self.status_label.setText(
            f"Downloading: {_format_size(received)} of {_format_size(total)}"
        )

    def _filter(self, _text: str = "") -> None:
        query = self.search_edit.text().strip().casefold()
        incoming: _RowKey | None = None
        for scope in _SCOPES:
            for key, row in self._rows.items():
                if key[0] != scope:
                    continue
                searchable = f"{row.item.title} {row.item.description} {row.category}".casefold()
                visible = query in searchable or query in row.display_title.casefold()
                row.setVisible(visible)
                if visible and incoming is None:
                    incoming = key
        previous = self._selected
        if previous not in self._rows or (previous and self._rows[previous].isHidden()):
            self._selected = incoming
        self._sync_section_status()
        self._selection_changed(animate=previous is not None and self._selected != previous)

    def _sync_section_status(self) -> None:
        query = bool(self.search_edit.text().strip())
        for scope in _SCOPES:
            label = self.public_status if scope == "public" else self.lab_status
            visible = any(key[0] == scope and not row.isHidden() for key, row in self._rows.items())
            status = self._section_errors[scope]
            if scope in self._loading:
                status = f"Loading {scope} projects…"
            elif not status and not visible and self._catalogs[scope] is not None:
                status = (
                    f"No matching {scope} projects." if query else f"No {scope} projects available."
                )
            label.setText(status)
            label.setVisible(bool(status))
        self.public_retry.setVisible(bool(self._section_errors["public"]))

    def _select(self, key: _RowKey) -> None:
        previous = self._selected
        self._selected = key
        self._selection_explicit = True
        self._status_override = ""
        self.status_label.setToolTip("")
        self._selection_changed(animate=previous != key)

    def _selection_changed(self, *, animate: bool = False) -> None:
        for key, row in self._rows.items():
            row.setChecked(key == self._selected)
        item = self.selected_item()
        if item is None:
            self.details.setPlainText(
                "No matching experiments." if self.search_edit.text().strip()
                else "Select a project to see its details."
            )
        else:
            self._render_details(item)
        if animate and item is not None:
            self._animate_reveal(self.details)
        self._sync_footer()
        self._sync_actions()
        self.summary_requested.emit()

    def _render_details(self, item: LibraryItem) -> None:
        theme = resolve_studio_theme(self.palette())
        scope = self.selected_scope()
        count = self._condition_counts.get(_summary_key(item, scope))
        conditions = str(count) if count is not None else (
            "Checking…" if self.needs_condition_count(item, scope) else "Not listed"
        )
        minimum_color = theme.text_primary if item.compatible else theme.warning_text
        preview = (
            _oddball_demo_preview(theme.text_secondary)
            if scope == "public" and item.item_id == _ODDBALL_DEMO_ID and item.version == "1.0.0"
            else ""
        )
        self.details.setHtml(f"""
            <body style="font-size: {FONT_SIZE_BODY}px; color: {theme.text_primary}">
            <p style="font-size: {FONT_SIZE_PAGE_TITLE}px; font-weight: 700; margin-bottom: 20px">
            {escape(_display_title(item, scope))}</p>
            <p><span style="color: {theme.text_secondary}">Download size</span><br>
            <b>{_format_size(item.size_bytes)}</b></p>
            <p><span style="color: {theme.text_secondary}">Minimum Studio version</span><br>
            <b style="color: {minimum_color}">{escape(item.min_studio_version)}</b></p>
            <p><span style="color: {theme.text_secondary}">Conditions</span><br>
            <b>{conditions}</b></p>
            {preview}</body>
        """)

    def _sync_footer(self) -> None:
        if not self._busy:
            access = "No account required" if self.selected_scope() == "public" else ""
            self.status_label.setText(self._status_override or access)
        elif self._status_override:
            self.status_label.setText(self._status_override)

    def _animate_reveal(self, widget: QWidget) -> None:
        self._finish_reveal()
        duration = widget_animation_duration(widget, 150) if self.isVisible() else 0
        if not duration:
            return
        self._reveal_widget = widget
        effect = QGraphicsOpacityEffect(widget)
        effect.setOpacity(0.90)
        widget.setGraphicsEffect(effect)
        self._reveal_animation.setDuration(duration)
        self._reveal_animation.start()

    def _reveal_step(self, value: float) -> None:
        if self._reveal_widget is not None:
            effect = self._reveal_widget.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(value)

    def _finish_reveal(self) -> None:
        self._reveal_animation.stop()
        if self._reveal_widget is not None:
            self._reveal_widget.setGraphicsEffect(None)  # type: ignore[arg-type]  # Qt accepts None to remove the effect.
            self._reveal_widget = None

    def _sync_actions(self, *_args: object) -> None:
        item = self.selected_item()
        installed = self.selected_installation()
        self.install_button.setText({
            "new": "Download and set up experiment",
            "installed": "Already installed",
            "update": "Review update…",
            "review": "Review existing project…",
        }[installed.state] if installed else (
            "Checking installation…" if item else "Download and set up experiment"
        ))
        lab_catalog = self._catalogs["lab"]
        view_only = (
            self.selected_scope() == "lab" and lab_catalog is not None
            and lab_catalog.access_level == "view" and item is not None
        )
        guidance = ""
        if view_only:
            self.install_button.setText("View-only access")
            guidance = "Your lab has view-only access; downloading experiments is not permitted."
        elif installed is not None and installed.state == "new":
            guidance = (
                "Creates a separate project in your Studio Root Folder. "
                "Review display, timing and triggers in Setup before use."
            )
        if "lab" in self._loading and self.can_download:
            guidance = "Wait for the current Library check to finish."
        if item is not None and self.can_download and not item.compatible:
            self.install_button.setText("Studio update required")
            guidance = item.compatibility_message
        if self._downloading:
            self.install_button.setText("Preparing bundle…")
        self.install_button.setToolTip(guidance)
        self.install_button.setAccessibleDescription(guidance)
        lab_idle = not self._busy and "lab" not in self._loading
        self.connect_button.setEnabled(
            lab_idle and bool(self.code_edit.text().strip())
            and bool(self.device_edit.text().strip())
        )
        self.disconnect_button.setEnabled(lab_idle and self._connection is not None)
        self.refresh_button.setEnabled(lab_idle and self._connection is not None)
        self.connect_toggle.setEnabled(lab_idle)
        self.connection_fields.setEnabled(lab_idle)
        self.public_retry.setEnabled(not self._busy and "public" not in self._loading)
        self.install_button.setEnabled(
            lab_idle and self.can_download and item is not None and item.compatible
            and installed is not None and installed.state != "installed"
        )
        self.search_edit.setEnabled(
            not self._busy and (self._openfpvs or self._connection is not None),
        )
        for row in self._rows.values():
            row.setEnabled(not self._busy)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.ThemeChange,
        ):
            if hasattr(self, "details") and (item := self.selected_item()) is not None:
                self._render_details(item)

    def reject(self) -> None:
        self.closing.emit()
        if self._busy:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._busy:
            self.closing.emit()
            event.ignore()
            return
        super().closeEvent(event)
