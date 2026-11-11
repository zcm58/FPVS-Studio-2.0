"""Software response pointers exercised with fake Pyglet textures and handles."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from tests.unit.test_memory_modifier_engine import _recognition_step as _memory_recognition_step
from tests.unit.test_psychopy_task_mouse import _CursorScreen, _recognition_step

from fpvs_studio.engines import psychopy_engine as engine_module
from fpvs_studio.engines import psychopy_task_cursor as cursor_module
from fpvs_studio.engines.psychopy_tasks import render_task_step


class _CursorHarness:
    def __init__(
        self, monkeypatch, *, window=None,
        install_error=None, restore_error=None, delete_error=None,
    ):
        self.original = object()
        self.operations = []
        self.image_properties = None
        self.hotspot = None
        self.imports = []
        self.handle = window.winHandle if window is not None else SimpleNamespace()
        self.handle._mouse_cursor = self.original

        def set_cursor(cursor):
            self.operations.append(("cursor", cursor))
            self.handle._mouse_cursor = cursor
            error = restore_error if cursor is self.original else install_error
            if error is not None:
                raise error

        def delete_texture(texture_id):
            self.operations.append(("delete", texture_id))
            if delete_error is not None:
                raise delete_error

        self.handle.set_mouse_cursor = set_cursor
        self.window = window or SimpleNamespace(winHandle=self.handle, winType="pyglet")
        self.texture = SimpleNamespace(
            id=41, _context=SimpleNamespace(delete_texture=delete_texture),
        )

        def image_data(width, height, image_format, data, **kwargs):
            self.image_properties = (width, height, image_format, data, kwargs)
            return SimpleNamespace(get_texture=lambda: self.texture)

        def image_cursor(image, hot_x=0, hot_y=0):
            self.hotspot = (hot_x, hot_y)
            return SimpleNamespace(drawable=True, texture=image.get_texture())

        modules = {
            "pyglet.image": SimpleNamespace(ImageData=image_data),
            "pyglet.window": SimpleNamespace(ImageMouseCursor=image_cursor),
        }

        def import_module(name):
            self.imports.append(name)
            return modules[name]

        monkeypatch.setattr(cursor_module, "import_module", import_module)


def test_task_cursor_is_an_opaque_high_contrast_arrow_in_the_framebuffer(monkeypatch):
    harness = _CursorHarness(monkeypatch)
    cursor = cursor_module.create_task_cursor(harness.window)
    installed = harness.handle._mouse_cursor

    assert installed is not harness.original
    assert installed.drawable
    width, height, image_format, data, image_options = harness.image_properties
    assert (width, height, image_format) == (32, 32, "RGBA")
    assert len(data) == width * height * 4
    pixels = set(zip(data[::4], data[1::4], data[2::4], data[3::4], strict=True))
    assert (0, 0, 0, 255) in pixels
    assert (255, 255, 255, 255) in pixels
    assert any(pixel[3] == 0 for pixel in pixels)
    assert {pixel[3] for pixel in pixels} == {0, 255}
    assert harness.hotspot == (1, 30)
    assert data[(width + 1) * 4:(width + 1) * 4 + 4] == b"\x00\x00\x00\xff"
    assert image_options["pitch"] == -width * 4
    assert set(harness.imports) == {"pyglet.image", "pyglet.window"}

    cursor.close()

    assert harness.handle._mouse_cursor is harness.original
    assert harness.operations == [
        ("cursor", installed), ("cursor", harness.original), ("delete", 41),
    ]
    assert harness.texture.id == 0
    cursor.close()
    assert harness.operations.count(("delete", 41)) == 1


@pytest.mark.parametrize("initially_visible", [False, True])
@pytest.mark.parametrize("exit_kind", ["submit", "escape", "render_failure", "input_failure"])
def test_response_exit_restores_native_cursor_and_deletes_software_texture(
    monkeypatch, tmp_path, initially_visible, exit_kind,
):
    screen = _CursorScreen(initially_visible=initially_visible)
    harness = _CursorHarness(monkeypatch, window=screen)
    screen.actions = [None, ("click", (-200, -120), 1)]
    if exit_kind in {"escape", "render_failure"}:
        screen.actions = [None, "escape" if exit_kind == "escape" else "error"]
    elif exit_kind == "input_failure":
        def fail_setup(**handlers):
            raise RuntimeError("mouse input unavailable")

        screen.winHandle.push_handlers = fail_setup

    def reject_legacy_mouse(**kwargs):
        raise AssertionError("The software pointer must retain native click coordinates.")

    screen.event.Mouse = reject_legacy_mouse

    def render():
        return render_task_step(
            visual=screen.visual, core=screen.core, event=screen.event, window=screen,
            keyboard=screen.keyboard, project_root=tmp_path, step=_recognition_step(),
            is_aborted=lambda: False, set_aborted=lambda: None,
            cursor_factory=cursor_module.create_task_cursor,
        )

    if exit_kind in {"render_failure", "input_failure"}:
        with pytest.raises(RuntimeError, match="display failed|mouse input unavailable"):
            render()
    else:
        result = render()
        assert result.aborted is (exit_kind == "escape")
        if exit_kind == "submit":
            assert result.selected_item_ids == ("pen-target",)
            assert result.mouse_position_px == (-200, -120)

    assert harness.handle._mouse_cursor is harness.original
    assert harness.operations[-2:] == [("cursor", harness.original), ("delete", 41)]
    assert harness.texture.id == 0
    assert screen.mouseVisible is initially_visible
    assert screen.winHandle.handlers == []


@pytest.mark.parametrize("failure", ["restore", "delete", "both"])
def test_task_cursor_attempts_restore_and_texture_release_independently(monkeypatch, failure):
    restore_error = OSError("cursor restoration failed") if failure in {"restore", "both"} else None
    delete_error = RuntimeError("texture release failed") if failure in {"delete", "both"} else None
    harness = _CursorHarness(
        monkeypatch, restore_error=restore_error, delete_error=delete_error,
    )
    cursor = cursor_module.create_task_cursor(harness.window)

    with pytest.raises(type(restore_error or delete_error)) as caught:
        cursor.close()

    assert caught.value is (restore_error or delete_error)
    assert harness.operations[-2:] == [("cursor", harness.original), ("delete", 41)]


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_task_cursor_install_failure_rolls_back_and_preserves_original_error(
    monkeypatch, rollback_fails,
):
    install_error = ValueError("native cursor installation failed")
    harness = _CursorHarness(
        monkeypatch, install_error=install_error,
        restore_error=OSError("rollback failed") if rollback_fails else None,
    )

    with pytest.raises(ValueError) as caught:
        cursor_module.create_task_cursor(harness.window)

    assert caught.value is install_error
    assert harness.operations[-2:] == [("cursor", harness.original), ("delete", 41)]
    assert harness.texture.id == 0


def test_task_cursor_rejects_unknown_texture_cleanup_interface(monkeypatch):
    harness = _CursorHarness(monkeypatch)
    del harness.texture._context

    with pytest.raises(RuntimeError):
        cursor_module.create_task_cursor(harness.window)

    assert harness.handle._mouse_cursor is harness.original


def test_task_cursor_rejects_shared_texture_without_deleting_its_owner_resource(monkeypatch):
    harness = _CursorHarness(monkeypatch)
    harness.texture.owner = object()

    with pytest.raises(RuntimeError, match="owned response-cursor texture"):
        cursor_module.create_task_cursor(harness.window)

    assert harness.operations == []
    assert harness.texture.id == 41
    assert harness.handle._mouse_cursor is harness.original


def test_task_cursor_cleanup_stays_on_its_presentation_thread(monkeypatch):
    harness = _CursorHarness(monkeypatch)
    cursor = cursor_module.create_task_cursor(harness.window)
    installed = harness.handle._mouse_cursor

    with ThreadPoolExecutor(max_workers=1) as worker:
        with pytest.raises(RuntimeError, match="thread"):
            worker.submit(cursor.close).result()

    assert harness.operations == [("cursor", installed)]
    cursor.close()
    assert harness.texture.id == 0


@pytest.mark.parametrize("scale", [1, 1.25, 1.5, 2])
@pytest.mark.parametrize("exit_kind", ["submit", "escape", "render_failure"])
def test_memory_selection_keeps_drawable_cursor_through_validation_and_revision(
    monkeypatch, tmp_path, scale, exit_kind,
):
    """Exercise the actual engine route for the reported four-of-eight image task."""

    screen = _CursorScreen(initially_visible=False)
    screen.scale = scale
    screen.recordFrameIntervals = True
    screen.frameIntervals = [0.016]
    harness = _CursorHarness(monkeypatch, window=screen)
    step = _memory_recognition_step()
    submit_position = (0, -screen.size[1] * 0.32)
    # Refuse early Submit, select four, then replace the first choice before exiting.
    selections = (0, 1, "submit", 2, 3, 0, 4, "submit")
    screen.actions = [None] + [
        ("click", submit_position if item == "submit" else step.items[item].position_px, 1)
        for item in selections
    ]
    if exit_kind != "submit":
        screen.actions[-1] = "escape" if exit_kind == "escape" else "error"
    frame_cursors = []
    original_flip = screen.flip

    def observe_flip():
        frame_cursors.append(screen.winHandle._mouse_cursor)
        assert screen.mouseVisible
        assert not screen.recordFrameIntervals
        original_flip()

    def reject_legacy_mouse(**kwargs):
        raise AssertionError("Memory selection must retain the native queued-click path.")

    screen.flip = observe_flip
    screen.event.Mouse = reject_legacy_mouse
    engine = engine_module.PsychoPyEngine()
    engine._psychopy = object()
    engine._window = screen
    engine._visual = screen.visual
    engine._event = screen.event
    engine._core = screen.core
    engine._keyboard = screen.keyboard
    monkeypatch.setattr(engine_module, "sys", SimpleNamespace(platform="win32"))

    if exit_kind == "render_failure":
        with pytest.raises(RuntimeError, match="display failed"):
            engine.render_task_step(step, tmp_path)
    else:
        result = engine.render_task_step(step, tmp_path)
        assert result.selected_item_ids == ("image-1", "image-2", "image-3", "image-4")
        assert result.aborted is (exit_kind == "escape")
        if exit_kind == "submit":
            assert result.key == "mouse-submit"
            assert result.mouse_position_px == pytest.approx(submit_position)

    assert len(frame_cursors) == len(selections) + 1
    assert all(cursor is frame_cursors[0] and cursor.drawable for cursor in frame_cursors)
    assert screen.winHandle._mouse_cursor is harness.original
    assert harness.texture.id == 0
    assert screen.winHandle.handlers == []
    assert not screen.mouseVisible
    assert screen.recordFrameIntervals
    assert screen.frameIntervals == []
