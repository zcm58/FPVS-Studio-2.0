"""Measured participant-instruction layout without opening graphics windows."""

from __future__ import annotations

import textwrap
from types import SimpleNamespace

import pytest

from fpvs_studio.engines.psychopy_text_screens import show_text_screen

BIRTH_CONTROL_INSTRUCTIONS = (
    "Instructions:\n\n"
    "Several images will be shown to you in rapid succession. \n"
    "However, all you have to do is fixate on the cross in the middle of the screen "
    'and press "space" everytime it turns from blue to red.\n'
    "Please try not to blink during the stimuli presentation\n"
    "Press space when you're ready to begin"
)
BIRTH_CONTROL_BODY = BIRTH_CONTROL_INSTRUCTIONS + "\n\nBlock 1, item 1"


class _MeasuredText:
    """A wrapped renderer with PsychoPy's delayed font/wrap metric refresh."""

    def __init__(self, window, *, text, **kwargs):
        self.window = window
        self._text = text
        self.height = kwargs.get("height", 28)
        self.wrapWidth = kwargs.get("wrapWidth", 1200)
        self.pos = kwargs.get("pos", (0, 0))
        self.units = kwargs.get("units")
        self.anchorHoriz = kwargs.get("anchorHoriz", "center")
        self.anchorVert = kwargs.get("anchorVert", "center")
        self.draw_count = 0
        self.cleanup_count = 0
        self.metric_reads = 0
        self.refresh_count = 0
        self._refresh()

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        if value != self._text:
            self._text = value
            self._refresh()

    def _refresh(self):
        # Glyph width and line leading are deterministic; layout consumes the
        # rendered result, including explicit blank lines and unbreakable words.
        advance = self.height * 0.55
        capacity = max(1, int(self.wrapWidth / advance))
        lines = []
        for paragraph in self._text.split("\n"):
            lines.extend(textwrap.wrap(
                paragraph, width=capacity, break_long_words=False, break_on_hyphens=False,
            ) or [""])
        self._bounds = (
            max(len(line) for line in lines) * advance,
            len(lines) * self.height * 1.3,
        )
        self.refresh_count += 1

    @property
    def boundingBox(self):
        self.metric_reads += 1
        return self._bounds

    def setText(self, text=None, log=None):  # noqa: N802 - PsychoPy API
        # PsychoPy treats an explicitly supplied unchanged string as a no-op.
        if text == self._text:
            return
        if text is not None:
            self._text = str(text)
        self._refresh()

    def draw(self):
        self.draw_count += 1
        width, height = self._bounds
        x, y = self.pos
        top = y if self.anchorVert == "top" else y + height / 2
        self.window.pending.append({
            "text": self.text, "height": self.height, "wrap": self.wrapWidth,
            "units": self.units, "anchor": self.anchorVert,
            "left": x - width / 2, "right": x + width / 2,
            "top": top, "bottom": top - height,
        })

    def clearTextures(self):  # noqa: N802 - PsychoPy API
        self.cleanup_count += 1


class _Screen:
    def __init__(self, size=(1920, 1080), *, key_batches=None, interval=1 / 60,
                 resize_after_first=None, fail_flip=False):
        self.size = size
        self.time = 0.0
        self.frames = []
        self.pending = []
        self.created = []
        self.interval = interval
        self.resize_after_first = resize_after_first
        self.fail_flip = fail_flip
        self.key_batches = iter(key_batches if key_batches is not None else [["space"]])
        self.key_clears = 0
        self.aborted = False

    def text_stim(self, *args, **kwargs):
        stimulus = _MeasuredText(*args, **kwargs)
        self.created.append(stimulus)
        return stimulus

    def flip(self):
        if self.fail_flip:
            raise RuntimeError("flip failed")
        self.frames.append({"size": self.size, "texts": self.pending})
        self.pending = []
        self.time += self.interval
        if len(self.frames) == 1 and self.resize_after_first is not None:
            self.size = self.resize_after_first

    def clear_events(self):
        self.key_clears += 1

    def get_keys(self, **kwargs):
        return [SimpleNamespace(name=name) for name in next(self.key_batches, [])]

    def abort(self):
        self.aborted = True

    def render(self, *, heading="Condition 1 of 4", body=BIRTH_CONTROL_BODY,
               countdown=None, continue_key="space", continue_prompt="Press Space to begin."):
        start = self.time
        return show_text_screen(
            visual=SimpleNamespace(TextStim=self.text_stim),
            core=SimpleNamespace(Clock=lambda: SimpleNamespace(getTime=lambda: self.time - start)),
            window=self,
            keyboard=SimpleNamespace(clearEvents=self.clear_events, getKeys=self.get_keys),
            is_aborted=lambda: self.aborted, set_aborted=self.abort,
            heading=heading, body=body, countdown_seconds=countdown,
            continue_key=continue_key, continue_prompt=continue_prompt,
        )


def _assert_readable_frames(screen):
    for frame in screen.frames:
        width, height = frame["size"]
        previous_bottom = None
        for block in frame["texts"]:
            assert block["left"] >= -width * 0.45 - 0.01
            assert block["right"] <= width * 0.45 + 0.01
            assert block["top"] <= height * 0.45 + 0.01
            assert block["bottom"] >= -height * 0.45 - 0.01
            if previous_bottom is not None:
                assert previous_bottom > block["top"], "Instruction blocks overlap"
            previous_bottom = block["bottom"]
        for block in frame["texts"]:
            assert block["units"] == "pix"
            assert block["anchor"] == "top"


@pytest.mark.parametrize("size", [(1920, 1080), (1280, 720), (800, 600), (640, 480)])
def test_birth_control_instructions_fit_without_overlap_or_text_changes(size):
    screen = _Screen(size)
    assert screen.render() is False
    assert len(screen.created) == 3
    assert screen.created[1].text == BIRTH_CONTROL_BODY
    assert screen.created[0].text == "Condition 1 of 4"
    assert screen.created[2].text == "Press Space to begin. Press Escape to abort."
    assert screen.key_clears == 1
    _assert_readable_frames(screen)
    scales = [stimulus.height / base for stimulus, base in zip(
        screen.created, (36, 28, 24), strict=True,
    )]
    assert all(2 / 3 <= scale <= 1 for scale in scales)
    assert scales == pytest.approx([scales[0]] * 3)
    if size[0] >= 1280:
        assert [stimulus.height for stimulus in screen.created] == [36, 28, 24]
    assert [stimulus.cleanup_count for stimulus in screen.created] == [1, 1, 1]


def test_resize_rewraps_existing_stimuli_before_the_next_visible_frame():
    screen = _Screen(key_batches=[[], ["space"]], resize_after_first=(640, 480))
    assert screen.render() is False
    assert [frame["size"] for frame in screen.frames] == [(1920, 1080), (640, 480)]
    assert len(screen.created) == 3
    assert screen.frames[0]["texts"][1]["text"] == screen.frames[1]["texts"][1]["text"]
    assert screen.frames[1]["texts"][1]["wrap"] <= 576
    assert screen.created[1].refresh_count > 1
    _assert_readable_frames(screen)
    assert all(stimulus.cleanup_count == 1 for stimulus in screen.created)


def test_countdown_changes_reflow_without_changing_automatic_completion():
    screen = _Screen((640, 480), key_batches=[], interval=600)
    assert screen.render(countdown=1200, continue_key=None) is False
    assert len(screen.frames) == 2
    assert "1200.0 s" in screen.frames[0]["texts"][-1]["text"]
    assert "600.0 s" in screen.frames[1]["texts"][-1]["text"]
    assert screen.time == 1200
    assert len(screen.created) == 3
    _assert_readable_frames(screen)
    assert all(stimulus.cleanup_count == 1 for stimulus in screen.created)


def test_unchanged_instruction_frames_reuse_layout_and_stimuli():
    screen = _Screen(key_batches=[[]] * 49 + [["space"]])
    assert screen.render(body="Ready.") is False
    assert len(screen.frames) == 50
    assert len(screen.created) == 3
    assert [stimulus.draw_count for stimulus in screen.created] == [50, 50, 50]
    assert sum(stimulus.metric_reads for stimulus in screen.created) < 15
    assert [stimulus.height for stimulus in screen.created] == [36, 28, 24]
    _assert_readable_frames(screen)


@pytest.mark.parametrize("body", ["Instruction line.\n" * 200, "X" * 500])
def test_unreadable_overflow_fails_explicitly_and_releases_all_stimuli(body):
    screen = _Screen((640, 480))
    with pytest.raises(RuntimeError, match="readable text size"):
        screen.render(body=body)
    assert len(screen.created) == 3
    assert screen.frames == []
    assert all(stimulus.draw_count == 0 for stimulus in screen.created)
    assert all(stimulus.cleanup_count == 1 for stimulus in screen.created)


@pytest.mark.parametrize("termination", ["escape", "flip_error"])
def test_measured_instruction_layout_preserves_abort_and_error_cleanup(termination):
    screen = _Screen(key_batches=[["escape"]], fail_flip=termination == "flip_error")
    if termination == "flip_error":
        with pytest.raises(RuntimeError, match="flip failed"):
            screen.render()
    else:
        assert screen.render() is True
        assert screen.aborted
    assert len(screen.created) == 3
    assert all(stimulus.cleanup_count == 1 for stimulus in screen.created)


def test_heading_and_footer_fit_without_a_body():
    screen = _Screen((640, 480))
    assert screen.render(body=None) is False
    assert len(screen.created) == 2
    _assert_readable_frames(screen)
