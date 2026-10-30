"""App-owned automatic discovery and opt-in installation of Library project versions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from fpvs_studio.core.library_installations import LibraryInstallStatus
from fpvs_studio.core.library_origin import (
    LibraryOriginError,
    LibraryProjectOrigin,
    load_library_origin,
    save_library_origin,
)
from fpvs_studio.core.project_bundle import (
    BundleImportStage,
    ProjectBundleCancelled,
    ProjectBundleManifest,
    read_project_bundle_manifest,
)
from fpvs_studio.core.project_bundle_update import (
    ProjectBundleRecoveryError,
    ProjectBundleUpdateResult,
    capture_project_update_snapshot,
    update_project_bundle,
)
from fpvs_studio.data_sharing.errors import DataSharingCancelled, DataSharingError
from fpvs_studio.data_sharing.project_updates import inspect_project_update_reporting
from fpvs_studio.gui.library_controller import ImportCallback
from fpvs_studio.gui.project_version_dialog import ProjectVersionDialog
from fpvs_studio.gui.update_lifecycle import (
    ProgressReporter,
    UpdateCallback,
    UpdateJob,
    UpdateTaskResult,
    update_lifecycle,
)
from fpvs_studio.gui.workers import ProgressSignalBridge
from fpvs_studio.library.client import LibraryClient
from fpvs_studio.library.errors import LibraryCancelled, LibraryError
from fpvs_studio.library.installations import check_library_install, download_library_install
from fpvs_studio.library.models import LibraryCatalog
from fpvs_studio.library.project_updates import ProjectUpdateResult, check_project_update
from fpvs_studio.runtime.condition_recovery import ensure_project_update_recovery_ready

if TYPE_CHECKING:
    from fpvs_studio.gui.main_window import StudioMainWindow

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Checked:
    result: ProjectUpdateResult
    catalog: LibraryCatalog | None = None
    can_download_separately: bool = True
    reporting_error: str = ""
    reporting_notice: str = ""


@dataclass(frozen=True)
class _Updated:
    result: ProjectBundleUpdateResult
    reconnect_required: bool


class ProjectUpdateController(QObject):
    """A background check never changes the project or opens a participant-facing dialog."""

    def __init__(
        self, app: QApplication, *,
        current_window: Callable[[], StudioMainWindow | None],
        import_bundle: ImportCallback,
        apply_update: Callable[[ProjectBundleUpdateResult], None],
        studio_root: Callable[[], Path],
        client: LibraryClient | None = None,
    ) -> None:
        super().__init__(app)
        self.client = client or LibraryClient()
        self._current_window = current_window
        self._import_bundle = import_bundle
        self._apply_update = apply_update
        self._studio_root = studio_root
        self._lifecycle = update_lifecycle(app)
        self._lifecycle.shutdown_started.connect(self._shutdown)
        self._window: StudioMainWindow | None = None
        self.dialog: ProjectVersionDialog | None = None
        self._job: UpdateJob | None = None
        self._pending_check: tuple[StudioMainWindow, bool] | None = None
        self._result: ProjectUpdateResult | None = None
        self._checked_result: _Checked | None = None
        self._generation = 0
        self._importing = False
        self._separate_download_allowed = True
        self._update_bridge: ProgressSignalBridge | None = None
        self._last_backup: tuple[Path, Path] | None = None
        self._offered: set[tuple[str, str, str, str, str]] = set()
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(5 * 60 * 1000)
        self._poll_timer.timeout.connect(self._automatic_check)
        self._offer_timer = QTimer(self)
        self._offer_timer.setSingleShot(True)
        self._offer_timer.timeout.connect(self._try_offer)

    def _current(self, window: StudioMainWindow) -> bool:
        return (
            not self._lifecycle.is_shutting_down
            and isValid(window) and window.isVisible()
            and not window._project_update_reload_failed
            and window is self._window and window is self._current_window()
        )

    def opened(self, window: StudioMainWindow) -> None:
        if self._lifecycle.is_shutting_down:
            return
        self._offer_timer.stop()
        self._generation += 1
        self._window = window
        if self._last_backup is not None and self._last_backup[0] != window.document.project_root:
            self._last_backup = None
        self._result = None
        self._checked_result = None
        if self.dialog is not None and isValid(self.dialog):
            self.dialog.hide()
            self.dialog.deleteLater()
        self.dialog = None
        self._poll_timer.start()
        self._queue_check(window, automatic=True)

    def _automatic_check(self) -> None:
        window = self._window
        if window is None or not self._current(window):
            self._poll_timer.stop()
            return
        if (
            self._job is not None or self._importing or window.is_launch_busy()
            or (self.dialog is not None and self.dialog.isVisible())
        ):
            return
        self._queue_check(window, automatic=True)

    def _offer_key(self) -> tuple[str, str, str, str, str] | None:
        result, window = self._result, self._window
        if (
            result is None or window is None or result.status != "update_available"
            or result.origin is None or not result.origin.auto_check
            or result.latest_item is None
        ):
            return None
        return (str(window.document.project_root), result.origin.service_url,
                result.latest_item.item_id, result.latest_item.version, result.latest_item.sha256)

    def _try_offer(self) -> None:
        window = self._window
        key = self._offer_key()
        if window is None or not self._current(window) or key is None or key in self._offered:
            return
        checked = self._checked_result
        if checked is None or checked.result is not self._result:
            return
        if (
            self._job is not None or self._importing or window.is_launch_busy()
            or QApplication.applicationState() != Qt.ApplicationState.ApplicationActive
            or QApplication.activeModalWidget() is not None
            or QApplication.activeWindow() not in (None, window, self.dialog)
        ):
            self._offer_timer.start(1000)
            return
        self._offered.add(key)
        self._ensure_dialog(window)
        # Reuse the checked candidate; opening an automatic offer does not issue
        # another request or begin a download.
        self._checked(checked)
        assert self.dialog is not None
        self.dialog.show()

    def _ensure_dialog(self, window: StudioMainWindow) -> None:
        if self.dialog is None:
            self.dialog = ProjectVersionDialog(window.document.project.meta.name, parent=window)
            self.dialog.action_requested.connect(self._action)
            self.dialog.closing.connect(self._close)

    def show(self, window: StudioMainWindow) -> None:
        if self._importing or self._lifecycle.is_shutting_down or window.is_launch_busy():
            return
        if window is not self._window:
            self.opened(window)
        self._ensure_dialog(window)
        assert self.dialog is not None
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        self._queue_check(window, automatic=False)

    def _queue_check(self, window: StudioMainWindow, *, automatic: bool) -> None:
        if not self._current(window):
            return
        self._result = None
        self._checked_result = None
        if self.dialog is not None:
            self.dialog.clear_install_candidate()
        if self._job is not None or self._importing:
            self._pending_check = (window, automatic)
            if self._job is not None:
                self._job.cancel()
            if self.dialog is not None:
                self.dialog.set_busy(True, "Waiting for the previous check to finish…")
            return
        root = window.document.project_root
        local_project_id = window.document.project.meta.project_id
        studio_root = self._studio_root()

        def check(_progress: ProgressReporter, cancel: Event) -> _Checked:
            separate_allowed = True
            reporting_error, reporting_notice = "", ""
            try:
                origin = load_library_origin(root)
                if origin is not None and origin.local_project_id != local_project_id:
                    raise LibraryOriginError("The Library record belongs to a different project.")
            except LibraryOriginError as error:
                if automatic:
                    raise
                origin = None
                result = ProjectUpdateResult(
                    "unlinked",
                    message=f"{error} Link this project explicitly to repair the record.",
                )
            else:
                result = check_project_update(self.client, origin, automatic=automatic,
                                              cancel_event=cancel)
            catalog = None
            if result.can_install and result.latest_item is not None:
                installed = check_library_install(
                    studio_root, self.client.service_url, result.latest_item, cancel_event=cancel,
                )
                if installed.state == "installed":
                    separate_allowed = False
                    if result.status != "update_available":
                        result = ProjectUpdateResult(
                            "unavailable", origin, result.latest_item, installed.message,
                        )
            if not automatic and origin is None and self.client.connection_info() is not None:
                catalog = self.client.catalog(cancel_event=cancel)
            if result.status == "update_available":
                try:
                    ensure_project_update_recovery_ready(root, cancel_event=cancel)
                    reporting = inspect_project_update_reporting(root, cancel_event=cancel)
                    if reporting.reconnect_required:
                        reporting_notice = (
                            "Results sharing will need reconnecting for the new version."
                        )
                except DataSharingCancelled:
                    raise
                except InterruptedError as error:
                    raise LibraryCancelled(str(error)) from error
                except (DataSharingError, ValueError) as error:
                    reporting_error = str(error)
            return _Checked(result, catalog, separate_allowed, reporting_error, reporting_notice)

        self._start(check,
                    lambda value: self._checked(value, automatic=automatic),
                    "Checking for a newer project version…")

    def _start(
        self, callback: UpdateCallback, completed: Callable[[object], None], message: str,
        *, holds_download: bool = False,
    ) -> None:
        window = self._window
        if window is None or not self._current(window) or self._job is not None:
            return
        generation = self._generation
        if self.dialog is not None:
            self.dialog.set_busy(True, message)
        job = self._lifecycle.start_task(callback, keep_success_on_cancel=True)
        self._job = job

        def finished(value: object) -> None:
            self._job = None
            outcome = cast(UpdateTaskResult, value)
            discarded = (
                not self._current(window) or generation != self._generation
                or job.cancel_event.is_set() or outcome.cancelled
            )
            if holds_download and (discarded or outcome.error is not None):
                self.client.release_download()
            if not discarded:
                if outcome.error is not None:
                    if self.dialog is not None:
                        self.dialog.set_busy(False, self._error(outcome.error))
                    else:
                        _LOGGER.info("Project version check unavailable: %s",
                                     self._error(outcome.error))
                else:
                    if self.dialog is not None:
                        self.dialog.set_busy(False)
                    completed(outcome.value)
            elif self.dialog is not None and self._current(window):
                self.dialog.set_busy(False, "Operation canceled.")
            self._run_pending()

        job.finished.connect(finished)

    def _run_pending(self) -> None:
        if self._job is not None or self._importing:
            return
        pending, self._pending_check = self._pending_check, None
        if pending is not None:
            self._queue_check(pending[0], automatic=pending[1])

    def _checked(self, value: object, *, automatic: bool = False) -> None:
        checked = cast(_Checked, value)
        self._result = checked.result
        self._checked_result = checked
        self._separate_download_allowed = checked.can_download_separately
        result = checked.result
        latest, origin = result.latest_item, result.origin
        message = self._message(result)
        if (
            self._last_backup is not None and self._window is not None
            and self._last_backup[0] == self._window.document.project_root
            and result.status == "current"
        ):
            message = f"Previous version backup: {self._last_backup[1]}"
        message = "\n".join(filter(None, (
            message, checked.reporting_error, checked.reporting_notice,
        )))
        if self.dialog is not None:
            self.dialog.set_state(
                installed_version=origin.installed_version if origin else None,
                latest=latest, linked=origin is not None,
                auto_check=origin.auto_check if origin else True,
                status=message, can_install=result.can_install,
                can_update=result.status == "update_available" and not checked.reporting_error,
                can_download_separately=(
                    result.can_install and checked.can_download_separately
                ),
            )
            if checked.catalog is not None:
                self.dialog.set_link_items(checked.catalog.items)
        window = self._window
        if window is not None and self._current(window):
            window.set_project_update_notice(
                message if result.status in {"update_available", "incompatible", "version_unknown"}
                and latest is not None else ""
            )
            key = self._offer_key()
            if key is not None:
                if self.dialog is not None and self.dialog.isVisible():
                    self._offered.add(key)
                elif automatic:
                    self._offer_timer.start(0)

    def _action(self, action: str) -> None:
        if action == "cancel":
            self._pending_check = None
            if self._job is not None:
                self._job.cancel()
            return
        window = self._window
        if window is None or not self._current(window) or self._importing:
            return
        if action == "check":
            self._queue_check(window, automatic=False)
        elif self._job is None and not window.is_launch_busy():
            if action == "install":
                self._install()
            elif action == "update":
                self._update_current()
            elif action in {"link", "set_auto"}:
                self._save_origin(link=action == "link")
            elif action == "relink":
                self._start(
                    lambda _progress, cancel: self.client.catalog(cancel_event=cancel),
                    self._link_choices, "Loading Library experiments…",
                )

    def _link_choices(self, value: object) -> None:
        if self.dialog is not None:
            self.dialog.begin_linking()
            self.dialog.set_link_items(cast(LibraryCatalog, value).items)

    def _save_origin(self, *, link: bool) -> None:
        window, dialog = self._window, self.dialog
        if window is None or dialog is None or not self._current(window):
            return
        try:
            if link:
                item = dialog.selected_link_item()
                if item is None:
                    return
                origin = LibraryProjectOrigin(
                    service_url=self.client.service_url, item_id=item.item_id,
                    installed_version=dialog.link_installed_version(), bundle_sha256=None,
                    local_project_id=window.document.project.meta.project_id,
                    auto_check=dialog.auto_check_enabled(),
                )
            else:
                if self._result is None or self._result.origin is None:
                    return
                origin = self._result.origin.model_copy(
                    update={"auto_check": dialog.auto_check_enabled()},
                )
        except ValueError:
            dialog.set_busy(False, "Enter a valid installed version, or leave it blank if unknown.")
            return
        root = window.document.project_root

        def save(_progress: ProgressReporter, cancel: Event) -> None:
            if cancel.is_set():
                raise LibraryCancelled("Operation canceled.")
            save_library_origin(root, origin)
            return None

        self._start(save, lambda _value: self._queue_check(window, automatic=False),
                    "Saving this project's Library link…")

    def _install(self) -> None:
        result = self._result
        if (
            result is None or not result.can_install or result.latest_item is None
            or not self._separate_download_allowed
        ):
            return
        assert result.origin is not None
        item, previous_origin = result.latest_item, result.origin
        assert self._window is not None
        root = self._studio_root()

        def download(
            progress: ProgressReporter, cancel: Event,
        ) -> tuple[Path, ProjectBundleManifest, LibraryProjectOrigin]:
            path = download_library_install(
                self.client, item, root, update=True,
                cancel_event=cancel, progress_callback=progress,
            )
            if isinstance(path, LibraryInstallStatus):
                raise LibraryOriginError(path.message)
            manifest = read_project_bundle_manifest(path)
            origin = LibraryProjectOrigin(
                service_url=self.client.service_url, item_id=item.item_id,
                installed_version=item.version, bundle_sha256=item.sha256,
                local_project_id=manifest.project.project_id,
                auto_check=previous_origin.auto_check,
            )
            return path, manifest, origin

        self._start(download, self._downloaded, "Downloading and verifying the new version…",
                    holds_download=True)

    def _update_current(self) -> None:
        result, window = self._result, self._window
        if (
            result is None or result.status != "update_available"
            or result.latest_item is None or result.origin is None
            or window is None or not self._current(window) or self._job is not None
        ):
            return
        if (
            not window._allow_project_handoff_during_fixation_load()
            or not window.prepare_project_handoff()
        ):
            return
        item, previous = result.latest_item, result.origin
        root, studio_root = window.document.project_root, self._studio_root()
        origin = LibraryProjectOrigin(
            service_url=self.client.service_url, item_id=item.item_id,
            installed_version=item.version, bundle_sha256=item.sha256,
            local_project_id=window.document.project.meta.project_id,
            auto_check=previous.auto_check,
        )
        generation = self._generation
        bridge = ProgressSignalBridge(self)
        self._update_bridge = bridge

        def stage_changed(stage: str) -> None:
            if self._current(window) and stage in {
                "verify", "base", "oddball", "project", "complete",
            }:
                window.set_bundle_import_stage(cast(BundleImportStage, stage))

        bridge.stage_changed.connect(stage_changed, Qt.ConnectionType.QueuedConnection)
        window.start_bundle_import_processing(
            project_name=window.document.project.meta.name,
            bundle_path=Path(item.filename), root_dir=root, updating_current=True,
        )
        self._importing = True
        if self.dialog is not None:
            self.dialog.set_busy(True, "Downloading and updating the current project…")

        def update(progress: ProgressReporter, cancel: Event) -> _Updated:
            ensure_project_update_recovery_ready(root, cancel_event=cancel)
            reporting = inspect_project_update_reporting(root, cancel_event=cancel)
            snapshot = capture_project_update_snapshot(root, cancel_event=cancel)
            if snapshot.origin != previous:
                raise LibraryOriginError(
                    "The project's Library record changed. Check for updates again."
                )
            path = self.client.download(item, cancel_event=cancel, progress_callback=progress)
            def precommit() -> None:
                nonlocal reporting
                ensure_project_update_recovery_ready(root, cancel_event=cancel)
                reporting = inspect_project_update_reporting(root, cancel_event=cancel)

            updated = update_project_bundle(
                path, root, studio_root, library_origin=origin,
                expected_snapshot=snapshot, cancel_event=cancel,
                progress_callback=bridge.stage_changed.emit,
                precommit_check=precommit,
            )
            return _Updated(updated, reporting.reconnect_required)

        try:
            job = self._lifecycle.start_task(update, keep_success_on_cancel=True)
        except Exception:
            self._importing = False
            window.finish_bundle_import_processing(restore_previous=True)
            bridge.deleteLater()
            self._update_bridge = None
            raise
        self._job = job

        def finished(value: object) -> None:
            self._job = None
            outcome = cast(UpdateTaskResult, value)
            committed = (
                isinstance(outcome.value, _Updated) and outcome.error is None
            )
            current = self._current(window) and generation == self._generation
            try:
                if committed:
                    completed = cast(_Updated, outcome.value)
                    updated = completed.result
                    self._last_backup = (root, updated.backup_path)
                    if current:
                        self._apply_update(updated)
                        window.finish_bundle_import_processing(restore_previous=False)
                        window.show_home()
                        notice = (
                            "Results sharing will need reconnecting for this version."
                            if completed.reconnect_required else ""
                        )
                        self._checked(_Checked(
                            ProjectUpdateResult("current", origin, item),
                            can_download_separately=False, reporting_notice=notice,
                        ))
                        if self.dialog is not None:
                            self.dialog.set_busy(False)
                    elif isValid(window):
                        window.fail_library_project_update()
                elif isinstance(outcome.error, ProjectBundleRecoveryError):
                    if isValid(window):
                        window.fail_library_project_update()
                    if current and self.dialog is not None:
                        self.dialog.set_busy(False, self._error(outcome.error))
                    self._invalidate_failed_update_candidate()
                else:
                    if isValid(window):
                        window.finish_bundle_import_processing(restore_previous=True)
                    if current and self.dialog is not None:
                        message = (
                            self._error(outcome.error)
                            if outcome.error is not None and not isinstance(
                                outcome.error,
                                (
                                    LibraryCancelled, ProjectBundleCancelled,
                                    DataSharingCancelled, InterruptedError,
                                ),
                            ) else "Update canceled. Your project is unchanged."
                        )
                        self.dialog.set_busy(False, message)
            except Exception:
                _LOGGER.exception("Updated project could not be opened")
                if isValid(window):
                    window.fail_library_project_update()
                if current and self.dialog is not None and isValid(self.dialog):
                    self.dialog.set_busy(
                        False, "The project was updated on disk. Reopen it before editing.",
                    )
                self._invalidate_failed_update_candidate()
            finally:
                try:
                    self.client.release_download()
                except OSError:
                    _LOGGER.warning("Could not release the Library transfer cache", exc_info=True)
                finally:
                    self._importing = False
                    self._update_bridge = None
                    bridge.deleteLater()
                    self._run_pending()

        job.finished.connect(finished)

    def _invalidate_failed_update_candidate(self) -> None:
        """Leave recovery guidance visible without allowing another stale-model action."""
        self._result = None
        self._checked_result = None
        self._separate_download_allowed = False
        self._pending_check = None
        self._poll_timer.stop()
        self._offer_timer.stop()
        if self.dialog is not None and isValid(self.dialog):
            self.dialog.clear_install_candidate()
            for control in (
                self.dialog.check_button, self.dialog.relink_button,
                self.dialog.auto_check_checkbox, self.dialog.link_panel,
            ):
                control.setEnabled(False)

    def _downloaded(self, value: object) -> None:
        path, manifest, origin = cast(
            tuple[Path, ProjectBundleManifest, LibraryProjectOrigin], value,
        )
        window = self._window
        if window is not None and window.is_launch_busy():
            self.client.release_download()
            if self.dialog is not None:
                self.dialog.set_busy(
                    False, "Presentation is running. Open the new version after it finishes.",
                )
            return
        self._importing = True
        if self.dialog is not None:
            self.dialog.hide()
        try:
            self._import_bundle(
                path, manifest, origin,
                lambda root: self._import_finished(root, window),
            )
        except Exception as error:
            _LOGGER.exception("Project version import handoff failed")
            self._import_finished(None, window)
            if self.dialog is not None and isValid(self.dialog):
                self.dialog.set_busy(False, self._error(error))

    def _import_finished(self, root: Path | None, window: StudioMainWindow | None) -> None:
        self.client.release_download()
        self._importing = False
        if (
            root is None and window is not None and self._current(window)
            and self.dialog is not None
        ):
            self.dialog.set_busy(
                False, "Import canceled or unsuccessful. Your project is unchanged.",
            )
            self.dialog.show()
        self._run_pending()

    def _close(self) -> None:
        self._action("cancel")

    def _shutdown(self) -> None:
        self._poll_timer.stop()
        self._offer_timer.stop()
        self._pending_check = None
        if self._job is not None:
            self._job.cancel()

    @staticmethod
    def _error(error: Exception) -> str:
        if isinstance(error, (LibraryError, DataSharingError, ValueError, OSError)):
            return str(error)
        _LOGGER.error("Project version operation failed (%s)", type(error).__name__)
        return "Could not check or install the project version. Retry when ready."

    @staticmethod
    def _message(result: ProjectUpdateResult) -> str:
        origin, item = result.origin, result.latest_item
        if result.status == "unlinked":
            return (
                (result.message or "This project has no Library version record.")
                + " Connect in View > Experiment Library if needed."
            )
        if result.status == "disabled":
            return "Automatic project version checks are off."
        if result.status == "not_connected":
            return result.message or "Connect through View > Experiment Library, then check again."
        if result.status == "unavailable":
            return result.message or "Could not check this project's Library version."
        if item is not None:
            if result.status == "incompatible":
                return f"Project version {item.version} is available. {item.compatibility_message}"
            if result.status == "version_unknown":
                return (
                    f"Library version {item.version} is available; "
                    "the installed version is unknown."
                )
            if result.status == "update_available":
                installed = origin.installed_version if origin else "?"
                return (
                    f"Project update available: {installed} → {item.version}. "
                    "Review the update before continuing data collection."
                )
        return f"Project version {origin.installed_version if origin else ''} is up to date."
