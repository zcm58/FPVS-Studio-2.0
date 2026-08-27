"""Focused tests for condition-local PsychoPy stimulus resource ownership."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

from fpvs_studio.core.enums import StimulusModality
from fpvs_studio.engines import psychopy_stimuli
from fpvs_studio.engines.psychopy_stimuli import (
    ConditionResourceCleanupError,
    ConditionResourcePreparationError,
    prepare_condition_resources,
)


class _FakeWindow:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.size = (1920, 1080)

    def clearBuffer(self) -> None:  # noqa: N802 - PsychoPy API
        self.events.append("clear")


class _FakeDrawable:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def draw(self) -> None:
        self.events.append(f"draw:{self.name}")


class _FakeTextureDrawable(_FakeDrawable):
    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        clear_error: bool = False,
    ) -> None:
        super().__init__(name, events)
        self._texID = object()
        self._maskID = object()
        self._pixbuffID = object()
        self._listID = object()
        self.clear_error = clear_error

    def clearTextures(self) -> None:  # noqa: N802 - PsychoPy API
        self.events.append(f"clear-textures:{self.name}")
        if self.clear_error:
            raise OSError(f"clear failed for {self.name}")


def _patch_stimulus_factory(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    *,
    fail_key: str | None = None,
    clear_error: bool = False,
) -> list[_FakeTextureDrawable]:
    created: list[_FakeTextureDrawable] = []
    monkeypatch.setattr(
        psychopy_stimuli,
        "stimulus_render_key",
        lambda event, *, run_spec: (event.key,),
    )

    def _prepare_stimulus(**kwargs: Any) -> _FakeTextureDrawable:
        event = kwargs["event"]
        events.append(f"prepare:{event.key}")
        if event.key == fail_key:
            raise RuntimeError(f"prepare failed for {event.key}")
        stimulus = _FakeTextureDrawable(
            event.key,
            events,
            clear_error=clear_error,
        )
        created.append(stimulus)
        return stimulus

    monkeypatch.setattr(psychopy_stimuli, "_prepare_stimulus", _prepare_stimulus)
    return created


def _run_spec(*keys: str) -> SimpleNamespace:
    return SimpleNamespace(
        stimulus_sequence=[SimpleNamespace(key=key) for key in keys],
    )


def test_condition_resources_prime_fixation_sync_cleanup_and_release_idempotently(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    events: list[str] = []
    created = _patch_stimulus_factory(monkeypatch, events)
    window = _FakeWindow(events)
    default_fixation = _FakeTextureDrawable("fixation-default", events)
    target_fixation = _FakeTextureDrawable("fixation-target", events)

    resources = prepare_condition_resources(
        visual=object(),
        window=window,
        project_root=tmp_path,
        run_spec=_run_spec("image-a", "image-a"),
        fixation_stimuli=(default_fixation, target_fixation),
        gpu_sync=lambda: events.append("gpu-sync"),
        delete_pixel_buffer=lambda buffer_id: events.append("delete-pixel-buffer"),
        delete_display_list=lambda list_id: events.append("delete-display-list"),
    )

    assert events == [
        "prepare:image-a",
        "draw:image-a",
        "draw:fixation-default",
        "draw:fixation-target",
        "clear",
        "gpu-sync",
    ]
    assert resources.ready is True
    assert resources.gpu_synchronized is True
    assert resources.released is False
    assert list(resources.prepared_sequence) == [created[0], created[0]]
    assert list(resources.fixation_stimuli) == [default_fixation, target_fixation]
    assert resources.fixation_stim is default_fixation

    prepared_sequence = resources.prepared_sequence
    fixation_stimuli = resources.fixation_stimuli
    report = resources.release()
    events_after_first_release = list(events)

    assert report.succeeded is True
    assert report.stimulus_count == 3
    assert events[-10:] == [
        "delete-display-list",
        "delete-pixel-buffer",
        "clear-textures:image-a",
        "delete-display-list",
        "delete-pixel-buffer",
        "clear-textures:fixation-default",
        "delete-display-list",
        "delete-pixel-buffer",
        "clear-textures:fixation-target",
        "gpu-sync",
    ]
    assert len(prepared_sequence) == 0
    assert len(fixation_stimuli) == 0
    assert resources.fixation_stim is None
    assert resources.ready is False
    assert resources.gpu_synchronized is False
    assert resources.released is True
    assert not hasattr(created[0], "_texID")
    assert not hasattr(created[0], "_maskID")
    assert not hasattr(created[0], "_pixbuffID")
    assert created[0]._listID == 0
    for fixation_stimulus in (default_fixation, target_fixation):
        assert not hasattr(fixation_stimulus, "_texID")
        assert not hasattr(fixation_stimulus, "_maskID")
        assert not hasattr(fixation_stimulus, "_pixbuffID")
        assert fixation_stimulus._listID == 0

    assert resources.release() is report
    assert events == events_after_first_release


def test_condition_resources_roll_back_a_partial_build(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    events: list[str] = []
    created = _patch_stimulus_factory(monkeypatch, events, fail_key="image-b")

    with pytest.raises(RuntimeError, match="prepare failed for image-b"):
        prepare_condition_resources(
            visual=object(),
            window=_FakeWindow(events),
            project_root=tmp_path,
            run_spec=_run_spec("image-a", "image-b"),
            fixation_stim=_FakeDrawable("fixation", events),
            gpu_sync=lambda: events.append("gpu-sync"),
            delete_pixel_buffer=lambda buffer_id: events.append("delete-pixel-buffer"),
            delete_display_list=lambda list_id: events.append("delete-display-list"),
        )

    assert events == [
        "prepare:image-a",
        "prepare:image-b",
        "delete-display-list",
        "delete-pixel-buffer",
        "clear-textures:image-a",
        "gpu-sync",
    ]
    assert not hasattr(created[0], "_pixbuffID")


def test_partial_build_surfaces_rollback_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    events: list[str] = []
    _patch_stimulus_factory(
        monkeypatch,
        events,
        fail_key="image-b",
        clear_error=True,
    )

    with pytest.raises(ConditionResourcePreparationError) as error_info:
        prepare_condition_resources(
            visual=object(),
            window=_FakeWindow(events),
            project_root=tmp_path,
            run_spec=_run_spec("image-a", "image-b"),
            fixation_stim=_FakeDrawable("fixation", events),
            gpu_sync=lambda: events.append("gpu-sync"),
            delete_pixel_buffer=lambda buffer_id: events.append("delete-pixel-buffer"),
            delete_display_list=lambda list_id: events.append("delete-display-list"),
        )

    assert isinstance(error_info.value.__cause__, RuntimeError)
    assert [failure.operation for failure in error_info.value.cleanup_report.failures] == [
        "clear_textures"
    ]
    assert events[-1] == "gpu-sync"


def test_cleanup_report_captures_pbo_and_texture_failures_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    created = _patch_stimulus_factory(monkeypatch, events, clear_error=True)
    resources = prepare_condition_resources(
        visual=object(),
        window=_FakeWindow(events),
        project_root=tmp_path,
        run_spec=_run_spec("image-a"),
        fixation_stim=_FakeDrawable("fixation", events),
        gpu_sync=lambda: events.append("gpu-sync"),
        delete_pixel_buffer=lambda buffer_id: (_ for _ in ()).throw(OSError("PBO failed")),
        delete_display_list=lambda list_id: events.append("delete-display-list"),
    )

    with caplog.at_level(logging.WARNING):
        report = resources.release()
    events_after_release = list(events)

    assert report.succeeded is False
    assert [failure.operation for failure in report.failures] == [
        "delete_pixel_buffer",
        "clear_textures",
    ]
    assert events[-1] == "gpu-sync"
    assert not hasattr(created[0], "_pixbuffID")
    assert "Ignored 2 PsychoPy stimulus texture cleanup error" in caplog.text
    with pytest.raises(ConditionResourceCleanupError):
        resources.release(raise_on_error=True)
    assert events == events_after_release


def test_cleanup_barrier_failure_is_reported_and_not_retried(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    events: list[str] = []
    _patch_stimulus_factory(monkeypatch, events)
    sync_count = 0

    def _sync() -> None:
        nonlocal sync_count
        sync_count += 1
        events.append(f"gpu-sync:{sync_count}")
        if sync_count == 2:
            raise OSError("cleanup barrier failed")

    resources = prepare_condition_resources(
        visual=object(),
        window=_FakeWindow(events),
        project_root=tmp_path,
        run_spec=_run_spec("image-a"),
        fixation_stim=_FakeDrawable("fixation", events),
        gpu_sync=_sync,
        delete_pixel_buffer=lambda buffer_id: events.append("delete-pixel-buffer"),
        delete_display_list=lambda list_id: events.append("delete-display-list"),
    )

    report = resources.release()
    events_after_release = list(events)

    assert report.succeeded is False
    assert [failure.operation for failure in report.failures] == ["synchronize_cleanup"]
    assert report.failures[0].stimulus_index is None
    assert events[-1] == "gpu-sync:2"
    assert resources.release() is report
    assert events == events_after_release


def test_default_gpu_helpers_finish_once_and_delete_lowercase_pbo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    fake_gl = SimpleNamespace(
        glFinish=lambda: events.append("finish"),
        glDeleteBuffers=lambda count, buffer_id: events.append(
            ("delete-buffers", count, buffer_id)
        ),
        glDeleteLists=lambda list_id, count: events.append(("delete-lists", list_id, count)),
    )
    monkeypatch.setattr(psychopy_stimuli, "_load_psychopy_gl", lambda: fake_gl)
    stimulus = _FakeTextureDrawable("image-a", [])
    pixel_buffer_id = stimulus._pixbuffID
    display_list_id = stimulus._listID

    psychopy_stimuli.synchronize_gpu()
    report = psychopy_stimuli.release_stimuli({"image-a": stimulus})

    assert events == [
        "finish",
        ("delete-lists", display_list_id, 1),
        ("delete-buffers", 1, pixel_buffer_id),
    ]
    assert report.succeeded is True
    assert not hasattr(stimulus, "_pixbuffID")
    assert stimulus._listID == 0


def test_image_preparation_rejects_project_root_escape(tmp_path) -> None:
    image_stim_calls: list[object] = []
    visual = SimpleNamespace(ImageStim=lambda *args, **kwargs: image_stim_calls.append(kwargs))
    event = SimpleNamespace(
        stimulus_modality=StimulusModality.IMAGE,
        image_path="../outside.png",
    )
    run_spec = SimpleNamespace(presentation=None, display=object())

    with pytest.raises(ValueError, match="may not escape the project directory"):
        psychopy_stimuli._prepare_stimulus(
            visual=visual,
            window=object(),
            project_root=tmp_path / "project",
            run_spec=run_spec,
            event=event,
        )

    assert image_stim_calls == []


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_cover_crop_returns_uint8_pil_with_orientation_and_alpha(mode: str) -> None:
    source = Image.new(mode, (200, 100))
    pixels = []
    for y in range(100):
        for x in range(200):
            color = (x, y, 17)
            pixels.append((*color, 127) if mode == "RGBA" else color)
    source.putdata(pixels)

    cropped = psychopy_stimuli._central_cover_crop(
        image=source,
        target_width_px=100,
        target_height_px=100,
    )

    assert isinstance(cropped, Image.Image)
    assert cropped.mode == mode
    assert cropped.size == (100, 100)
    expected_top_left = (50, 0, 17, 127) if mode == "RGBA" else (50, 0, 17)
    expected_bottom_right = (149, 99, 17, 127) if mode == "RGBA" else (149, 99, 17)
    assert cropped.getpixel((0, 0)) == expected_top_left
    assert cropped.getpixel((99, 99)) == expected_bottom_right
