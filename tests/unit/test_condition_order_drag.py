"""Exercise condition-list drop guards without importing or constructing Qt."""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest


def _methods(owner_name, names, **namespace):
    source = Path(__file__).resolve().parents[2] / (
        "src/fpvs_studio/gui/condition_order_dialog.py"
    )
    parsed = ast.parse(source.read_text(encoding="utf-8"))
    owner = next(node for node in parsed.body
                 if isinstance(node, ast.ClassDef) and node.name == owner_name)
    methods = [node for node in owner.body
               if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {method.name for method in methods} == set(names)
    for method in methods:
        method.decorator_list = []
    module = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        *methods,
    ], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    return namespace


@pytest.fixture
def drop_handler():
    namespace = _methods(
        "_ConditionOrderList", ["_accepts_drag", "dropEvent"],
        Qt=SimpleNamespace(DropAction=SimpleNamespace(MoveAction="move")),
    )

    def invoke(listing, event):
        listing._accepts_drag = MethodType(namespace["_accepts_drag"], listing)
        namespace["dropEvent"](listing, event)

    return invoke


class _DropEvent:
    def __init__(self, source):
        self._source = source
        self.point = object()
        self.accepted = False
        self.ignored = False
        self.action = None

    def source(self):
        return self._source

    def position(self):
        return SimpleNamespace(toPoint=lambda: self.point)

    def setDropAction(self, action):
        self.action = action

    def accept(self):
        self.accepted = True

    def ignore(self):
        self.ignored = True


def _listing(*, move_accepted=True):
    return SimpleNamespace(
        _can_reorder=Mock(return_value=True), _move_row=Mock(return_value=move_accepted),
        _drop_row=Mock(return_value=2), _drag_source_row=4, _drag_revision=7, _revision=7,
    )


@pytest.mark.parametrize("move_accepted", [True, False])
def test_drop_accepts_only_a_successful_same_list_move(drop_handler, move_accepted):
    listing = _listing(move_accepted=move_accepted)
    event = _DropEvent(listing)
    drop_handler(listing, event)
    listing._drop_row.assert_called_once_with(event.point)
    listing._move_row.assert_called_once_with(4, 2)
    assert event.accepted is move_accepted
    assert event.ignored is not move_accepted
    assert event.action == ("move" if move_accepted else None)


@pytest.mark.parametrize("blocked", ["external", "disabled", "stale_revision", "missing_drag"])
def test_drop_does_not_invoke_reorder_for_invalid_drag_context(drop_handler, blocked):
    listing = _listing()
    source = listing
    if blocked == "external":
        source = object()
    elif blocked == "disabled":
        listing._can_reorder.return_value = False
    elif blocked == "stale_revision":
        listing._revision += 1
    else:
        listing._drag_source_row = -1
    event = _DropEvent(source)
    drop_handler(listing, event)
    listing._move_row.assert_not_called()
    assert event.ignored
    assert not event.accepted


class _Item:
    def __init__(self, condition_id, block):
        self.condition_id = condition_id
        self.block = block

    def data(self, role):
        return self.condition_id if role == 256 else self.block


@pytest.fixture
def draft():
    namespace = _methods(
        "ConditionOrderDialog", ["_reorder_enabled", "_move_positions", "_reorder_condition"],
        Qt=SimpleNamespace(ItemDataRole=SimpleNamespace(UserRole=256)),
        _BLOCK_ROLE=257, Counter=Counter,
    )
    items = [_Item(None, 0), *(_Item(key, 0) for key in ("a", "b", "c")),
             _Item(None, 1), *(_Item(key, 1) for key in ("a", "b", "c"))]
    dialog = SimpleNamespace(
        _order=["a", "b", "c", "a", "b", "c"], _job=None, _dismissed=False,
        _stale=Mock(return_value=False), _render=Mock(),
        order_list=SimpleNamespace(
            item=lambda row: items[row] if 0 <= row < len(items) else None,
            count=lambda: len(items),
        ),
    )
    for name in ("_reorder_enabled", "_move_positions", "_reorder_condition"):
        setattr(dialog, name, MethodType(namespace[name], dialog))
    return dialog, items


def test_same_block_drop_updates_only_draft_and_preserves_occurrence_counts(draft):
    dialog, _items = draft
    before = Counter(dialog._order)
    assert dialog._reorder_condition(2, 1)
    assert dialog._order == ["b", "a", "c", "a", "b", "c"]
    assert Counter(dialog._order) == before
    dialog._render.assert_called_once_with(0)


@pytest.mark.parametrize("source,insertion", [(0, 2), (4, 6), (3, 5), (5, 3),
                                                (2, 2), (2, 3), (-1, 2), (99, 2)])
def test_semantic_reorder_rejects_headers_cross_block_noop_and_missing_rows(
    draft, source, insertion,
):
    dialog, _items = draft
    before = list(dialog._order)
    assert not dialog._reorder_condition(source, insertion)
    assert dialog._order == before
    dialog._render.assert_not_called()


@pytest.mark.parametrize("state", ["busy", "stale", "dismissed"])
def test_semantic_reorder_is_disabled_for_non_editable_dialog(draft, state):
    dialog, _items = draft
    if state == "busy":
        dialog._job = object()
    elif state == "stale":
        dialog._stale.return_value = True
    else:
        dialog._dismissed = True
    before = list(dialog._order)
    assert not dialog._reorder_condition(2, 1)
    assert dialog._order == before
    dialog._render.assert_not_called()


def test_partial_block_reorders_without_pulling_another_block_occurrence(draft):
    dialog, items = draft
    items.pop()
    dialog._order.pop()
    before = Counter(dialog._order)
    assert dialog._reorder_condition(6, 5)
    assert dialog._order == ["a", "b", "c", "b", "a"]
    assert Counter(dialog._order) == before
    dialog._render.assert_called_once_with(3)
