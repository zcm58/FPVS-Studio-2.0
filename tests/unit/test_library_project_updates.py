"""Semantic project-version selection never needs an installed release to remain listed."""

import ast
from collections import namedtuple
from pathlib import Path
from threading import Event
from types import MethodType, SimpleNamespace
from typing import cast

import pytest

from fpvs_studio.core.library_origin import LibraryProjectOrigin
from fpvs_studio.library.errors import LibraryAuthorizationError, LibraryCancelled, LibraryError
from fpvs_studio.library.models import LibraryCatalog, LibraryItem
from fpvs_studio.library.project_updates import check_project_update, select_project_update


@pytest.fixture
def discovery():
    """Run real coordination methods without importing Qt or accessing a network."""
    gui = Path(__file__).resolve().parents[2] / "src/fpvs_studio/gui"
    source = gui / "project_update_controller.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    controller = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                      and n.name == "ProjectUpdateController")
    names = {"_current", "_automatic_check", "_offer_key", "_try_offer", "_checked", "_shutdown"}
    methods = [n for n in controller.body if isinstance(n, ast.FunctionDef) and n.name in names]
    flags = SimpleNamespace(visible=True, foreground=1, modal=None, active=None, busy=False)

    def timer():
        calls = []
        return SimpleNamespace(calls=calls, start=lambda *args: calls.append(args),
                               stop=lambda: calls.append("stop"))

    checked = namedtuple(
        "Checked", "result catalog can_download_separately reporting_error reporting_notice",
        defaults=[None, True, "", ""],
    )
    # Inject a fake under the source's imported application symbol. No Qt import
    # or widget construction is performed by these coordinator tests.
    application_name = next(
        alias.asname or alias.name for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets"
        for alias in node.names
    )
    namespace = {
        "cast": cast, "_Checked": checked, "isValid": lambda _window: True,
        "Qt": SimpleNamespace(ApplicationState=SimpleNamespace(ApplicationActive=1)),
        application_name: SimpleNamespace(
            applicationState=lambda: flags.foreground,
            activeModalWidget=lambda: flags.modal, activeWindow=lambda: flags.active,
        ),
    }
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    notices, requests, states = [], [], []
    window = SimpleNamespace(document=SimpleNamespace(project_root=Path("synthetic-project")),
                             isVisible=lambda: flags.visible,
                             is_launch_busy=lambda: flags.busy,
                             _project_update_reload_failed=False,
                             set_project_update_notice=notices.append)
    context = SimpleNamespace(
        _window=window, _current_window=lambda: window, _result=None, _checked_result=None,
        _lifecycle=SimpleNamespace(is_shutting_down=False), _job=None, _importing=False,
        _offered=set(), _pending_check=None, _last_backup=None, dialog=None,
        _poll_timer=timer(), _offer_timer=timer(),
        _message=lambda result: result.message,
        _queue_check=lambda window, **kwargs: requests.append((window, kwargs)),
    )
    for name in names:
        setattr(context, name, MethodType(namespace[name], context))

    def ensure_dialog(_window):
        if context.dialog is None:
            dialog = SimpleNamespace(
                visible=False, set_state=lambda **kwargs: states.append(kwargs),
            )
            dialog.isVisible = lambda: dialog.visible
            dialog.show = lambda: setattr(dialog, "visible", True)
            context.dialog = dialog

    context._ensure_dialog = ensure_dialog
    return SimpleNamespace(controller=context, flags=flags, requests=requests, notices=notices,
                           checked=checked, states=states)


def test_automatic_discovery_offers_new_version_without_install_and_deduplicates(discovery):
    d, c = discovery, discovery.controller
    result = select_project_update(origin(), catalog(item("1.1.0")))
    c._checked(d.checked(result), automatic=True)
    assert c._offer_timer.calls == [(0,)]
    c._try_offer()
    assert c.dialog.visible
    assert d.states[-1]["can_install"]
    assert d.requests == []  # Showing the checked candidate does not re-fetch/download.
    c.dialog.visible = False
    c._checked(d.checked(result), automatic=True)
    c._try_offer()
    assert not c.dialog.visible
    newer = select_project_update(origin(), catalog(item("1.2.0")))
    c._checked(d.checked(newer), automatic=True)
    c._try_offer()
    assert c.dialog.visible
    assert d.states[-1]["latest"].version == "1.2.0"


@pytest.mark.parametrize("reason", ["busy", "modal", "background", "other-window", "job", "import"])
def test_automatic_discovery_defers_offer_until_safe(discovery, reason):
    d, c = discovery, discovery.controller
    c._result = select_project_update(origin(), catalog(item("1.1.0")))
    c._checked_result = discovery.checked(c._result)
    if reason == "busy":
        d.flags.busy = True
    elif reason == "modal":
        d.flags.modal = object()
    elif reason == "background":
        d.flags.foreground = 0
    elif reason == "other-window":
        d.flags.active = object()
    elif reason == "job":
        c._job = object()
    else:
        c._importing = True
    c._try_offer()
    assert c.dialog is None
    assert c._offered == set()
    assert c._offer_timer.calls == [(1000,)]
    d.flags.busy, d.flags.modal, d.flags.foreground, d.flags.active = False, None, 1, None
    c._job, c._importing = None, False
    c._try_offer()
    assert c.dialog.visible


@pytest.mark.parametrize("status", ["unlinked", "disabled", "unavailable", "current"])
def test_non_update_results_never_open_automatic_offer(discovery, status):
    from fpvs_studio.library.project_updates import ProjectUpdateResult

    c = discovery.controller
    c._checked(discovery.checked(ProjectUpdateResult(status)), automatic=True)
    c._try_offer()
    assert c.dialog is None


def test_opt_out_stale_window_and_shutdown_suppress_automatic_offer(discovery):
    c = discovery.controller
    c._result = select_project_update(origin(auto_check=False), catalog(item("1.1.0")))
    c._try_offer()
    assert c.dialog is None
    c._result = select_project_update(origin(), catalog(item("1.1.0")))
    c._checked_result = discovery.checked(c._result)
    discovery.flags.visible = False
    c._try_offer()
    c._automatic_check()
    assert c.dialog is None and discovery.requests == []
    assert c._poll_timer.calls[-1] == "stop"
    c._shutdown()
    assert c._offer_timer.calls[-1] == "stop"


@pytest.mark.parametrize("blocked", [None, "busy", "job", "import", "dialog"])
def test_polling_only_queues_idle_automatic_worker(discovery, blocked):
    c = discovery.controller
    if blocked == "busy":
        discovery.flags.busy = True
    elif blocked == "job":
        c._job = object()
    elif blocked == "import":
        c._importing = True
    elif blocked == "dialog":
        c._ensure_dialog(c._window)
        c.dialog.show()
    c._automatic_check()
    assert bool(discovery.requests) == (blocked is None)
    if blocked is None:
        assert discovery.requests[0][1] == {"automatic": True}


def origin(**changes):
    return LibraryProjectOrigin(**{
        "service_url": "https://library.example.test", "item_id": "masking",
        "installed_version": "1.0.0", "bundle_sha256": "a" * 64,
        "local_project_id": "masking", **changes,
    })


def item(version, **changes):
    return LibraryItem(**{
        "item_id": "masking", "version": version, "title": "Masking",
        "description": "Synthetic", "experiment_category": "fpvs_oddball",
        "filename": "masking.fpvsbundle", "size_bytes": 10,
        "uncompressed_size_bytes": 20, "file_count": 2, "sha256": "a" * 64,
        "min_studio_version": "1.0.0", **changes,
    })


def catalog(*items):
    return LibraryCatalog(schema_version="1.0", library_name="Library", items=list(items))


class Client:
    service_url = "https://library.example.test"

    def __init__(self, result=None, *, connected=True):
        self.result = result or catalog(item("1.1.0"))
        self.connected = connected
        self.calls = []

    def connection_info(self):
        self.calls.append("connection")
        return object() if self.connected else None

    def catalog(self, *, cancel_event=None):
        self.calls.append("catalog")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_selects_newest_semantic_version_when_installed_version_was_withdrawn():
    result = select_project_update(
        origin(), catalog(item("1.9.0"), item("1.10.0"), item("99.0", item_id="other")),
    )
    assert result.status == "update_available"
    assert result.latest_item.version == "1.10.0"
    assert result.can_install


def test_newest_incompatible_version_remains_visible_without_downgrading_candidate():
    result = select_project_update(
        origin(), catalog(item("1.1.0"), item("2.0.0", min_studio_version="99.0.0")),
    )
    assert result.status == "incompatible"
    assert result.latest_item.version == "2.0.0"
    assert "99.0.0" in result.message
    assert not result.can_install


@pytest.mark.parametrize("version", ["0.9.0", "1.0.0"])
def test_no_downgrade_or_repeat_update(version):
    result = select_project_update(origin(), catalog(item(version)))
    assert result.status == "current"
    assert not result.can_install


def test_unknown_legacy_version_is_not_claimed_to_have_an_update():
    receipt = origin(installed_version=None, bundle_sha256=None)
    result = select_project_update(receipt, catalog(item("1.1.0")))
    assert result.status == "version_unknown"
    assert result.origin == receipt
    assert result.can_install


@pytest.mark.parametrize("installed_version", ["1.0.0", None])
def test_view_only_catalog_keeps_latest_visible_without_offering_download(installed_version):
    receipt = origin(installed_version=installed_version, bundle_sha256=None)
    available = catalog(item("1.1.0")).model_copy(update={"access_level": "view"})
    result = check_project_update(Client(available), receipt, automatic=False)
    assert result.status == "unavailable"
    assert result.latest_item.version == "1.1.0"
    assert "view-only" in result.message
    assert not result.can_install


def test_project_update_uses_refreshed_download_permission():
    client = Client(catalog(item("1.1.0")).model_copy(update={"access_level": "view"}))
    assert not check_project_update(client, origin()).can_install
    client.result = catalog(item("1.1.0"))
    assert check_project_update(client, origin()).can_install


@pytest.mark.parametrize("available", [
    catalog(), catalog(item("1.0"), item("1.0.0")), catalog(item("1.0.0", sha256="b" * 64)),
])
def test_missing_ambiguous_or_changed_release_is_not_reported_current(available):
    result = select_project_update(origin(), available)
    assert result.status == "unavailable"
    assert not result.can_install


@pytest.mark.parametrize("receipt, status", [
    (None, "unlinked"), (origin(auto_check=False), "disabled"),
    (origin(service_url="https://different.example.test"), "unavailable"),
])
def test_unlinked_disabled_or_foreign_origin_never_contacts_client(receipt, status):
    client = Client()
    result = check_project_update(client, receipt)
    assert result.status == status
    assert client.calls == []


def test_manual_check_bypasses_auto_check_preference():
    client = Client()
    assert check_project_update(client, origin(auto_check=False), automatic=False).can_install
    assert client.calls == ["connection", "catalog"]


def test_disconnected_check_does_not_fetch_catalog():
    client = Client(connected=False)
    assert check_project_update(client, origin()).status == "not_connected"
    assert client.calls == ["connection"]


@pytest.mark.parametrize("error, status", [
    (LibraryError("Offline; retry later."), "unavailable"),
    (LibraryAuthorizationError("Reconnect this device."), "not_connected"),
])
def test_service_errors_return_non_destructive_status(error, status):
    receipt = origin()
    result = check_project_update(Client(error), receipt)
    assert result.status == status
    assert result.origin == receipt
    assert result.message == str(error)
    assert not result.can_install


def test_cancellation_propagates_before_or_during_network():
    cancel = Event()
    cancel.set()
    client = Client()
    with pytest.raises(LibraryCancelled):
        check_project_update(client, origin(), cancel_event=cancel)
    assert client.calls == []
    with pytest.raises(LibraryCancelled):
        check_project_update(Client(LibraryCancelled("cancelled")), origin())


@pytest.mark.parametrize("previous_origin", [
    "https://fpvs-studio-library.fpvs-studio-zcm58.workers.dev",
    "https://fpvs.zack-murphy.com",
])
def test_managed_origin_move_preserves_project_version_identity(previous_origin):
    receipt = origin(service_url=previous_origin)
    client = Client()
    client.service_url = "https://openfpvs.com"
    result = check_project_update(client, receipt)
    assert result.status == "update_available"
    assert result.origin == receipt
    assert result.origin.service_url == previous_origin
    assert client.calls == ["connection", "catalog"]


@pytest.mark.parametrize("previous_origin", [
    "https://fpvs-studio-library.fpvs-studio-zcm58.workers.dev",
    "https://fpvs.zack-murphy.com",
])
def test_managed_receipt_cannot_select_a_custom_service(previous_origin):
    client = Client()
    result = check_project_update(client, origin(service_url=previous_origin))
    assert result.status == "unavailable"
    assert client.calls == []


@pytest.mark.parametrize("blocked", ["reports", "separate-installed"])
def test_automatic_offer_preserves_checked_eligibility_and_warnings(discovery, blocked):
    c = discovery.controller
    result = select_project_update(origin(), catalog(item("1.1.0")))
    checked = discovery.checked(
        result, None, blocked != "separate-installed",
        "Resolve saved reports first" if blocked == "reports" else "",
        "Results must reconnect",
    )
    c._checked(checked, automatic=True)
    c._try_offer()
    assert c.dialog.visible
    assert discovery.states[-1]["can_update"] == (blocked != "reports")
    assert discovery.states[-1]["can_download_separately"] == (blocked != "separate-installed")
    assert "Results must reconnect" in discovery.states[-1]["status"]
