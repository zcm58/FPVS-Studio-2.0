"""A simple PsychoPy example: fade an image in and out at a chosen frequency.

FPVS Studio uses a modular sinusoidal contrast modulation script that automatically adjusts to
your chosen image presentation frequency. Our lab has defaulted to 6 Hz, but if you run FPVS at
different frequencies, then Studio will auto-adjust the speed of the contrast modulation
accordingly. Studio also supports different screen refresh rates and has some auto detection
features in place here rather than hard coding 60 Hz or 120 Hz, etc etc. So you'll see some of
that code in place here.

This file is an example of how Studio implements this feature. To do this, we set the background
of the screen to a neutral gray, then fade the image in and out from that neutral gray color.

The example repeats a demo image (checkerboard), or you can use your own
image, for the chosen number of cycles. One cycle is one complete fade in and out.
At 6 Hz, 60 cycles take about 10 seconds. Press Space to start or Escape to quit.

The screen can change only once per refresh. We round each image's duration to
a whole number of screen refreshes and show the resulting frequency before starting.
For example, 8 Hz works exactly on a 120 Hz screen, but becomes 7.5 Hz on a 60 Hz screen. This
changes the actual image presentation frequency. For exact timing, choose an image frequency
that divides your monitor's refresh rate evenly.

The contrast curve matches FPVS Studio: 0.5 * (1 - cos(2*pi*k/N)), where N is the
number of refreshes per cycle and k counts from 0 to N-1. The next cycle supplies
the next zero.

API references:
https://psychopy.org/api/visual/imagestim.html
https://psychopy.org/api/visual/window.html
"""

from __future__ import annotations

import importlib
import logging
import math
from pathlib import Path

# 1. Choose how fast the image fades, how many times it repeats, and which image to use.
# NERD Lab uses 6 Hz as an image presentation frequency, but feel free to change this number
# if you'd like to test different frequencies
IMAGE_FREQUENCY_HZ = 6.0
NUMBER_OF_CYCLES = 60  # 60 cycles at 6 hz is a 10 second image demo
IMAGE_PATH: str | None = None  # None = checkerboard, or e.g. "my_image.jpg".


def sinusoidal_contrast_envelope(frames_per_stimulus: int) -> tuple[float, ...]:
    """2. Calculate one contrast value per refresh: gray, full image, then back toward gray."""
    if frames_per_stimulus < 4:
        raise ValueError("Contrast modulation requires at least 4 frames per image cycle.")

    envelope = tuple(
        0.5 * (1.0 - math.cos(math.tau * k / frames_per_stimulus))
        for k in range(frames_per_stimulus)
    )
    if frames_per_stimulus % 2 == 0:
        return envelope
    # With an odd number of refreshes, adjust the values so the peak still reaches 1.
    sampled_peak = max(envelope)
    return tuple(value / sampled_peak for value in envelope)


def main() -> None:
    # 3. Check the settings before opening the presentation window.
    if not math.isfinite(IMAGE_FREQUENCY_HZ) or IMAGE_FREQUENCY_HZ <= 0:
        raise ValueError("IMAGE_FREQUENCY_HZ must be finite and greater than zero.")
    if not isinstance(NUMBER_OF_CYCLES, int) or NUMBER_OF_CYCLES < 1:
        raise ValueError("NUMBER_OF_CYCLES must be a positive integer.")

    # Load the tools for making the image, opening the window, and reading key presses.
    import numpy as np
    event = importlib.import_module("psychopy.event")
    visual = importlib.import_module("psychopy.visual")

    # 4. Make a checkerboard, or find your image beside this script.
    if IMAGE_PATH is None:
        y, x = np.indices((256, 256))
        image_source = (2 * ((x // 32 + y // 32) % 2) - 1).astype(float)
    else:
        image_path = Path(IMAGE_PATH).expanduser()
        if not image_path.is_absolute():
            image_path = Path(__file__).resolve().parent / image_path
        if not image_path.is_file():
            raise FileNotFoundError(f"Image does not exist: {image_path}")
        image_source = str(image_path)

    # 5. Open a full-screen window with the same gray as an image at zero contrast.
    win = visual.Window(
        fullscr=True,
        screen=0,
        units="height",
        color=(0, 0, 0),  # In PsychoPy's "rgb" scale, zero means middle gray.
        colorSpace="rgb",
        waitBlanking=True,
        autoLog=False,
    )
    try:
        # 6. Measure how often this screen refreshes, then work out the image timing.
        refresh_hz = win.getActualFrameRate(
            nIdentical=30, nMaxFrames=240, nWarmUpFrames=30,
        )
        if refresh_hz is None or not math.isfinite(refresh_hz) or refresh_hz <= 0:
            raise RuntimeError("Could not measure a stable display refresh rate.")

        frames_per_image = math.floor(refresh_hz / IMAGE_FREQUENCY_HZ + 0.5)
        envelope = sinusoidal_contrast_envelope(frames_per_image)
        realized_hz = refresh_hz / frames_per_image

        # 7. Load and resize the image before starting, keeping its original proportions.
        image = visual.ImageStim(win, image=image_source, contrast=0.0, autoLog=False)
        image.size = image.size * (0.7 / max(image.size))
        image.draw()  # Get the image ready while it is still at zero contrast.
        win.flip()

        # 8. Show the timing that will actually be used and wait for Space to start.
        ready = visual.TextStim(
            win,
            text=(
                f"Requested image rate: {IMAGE_FREQUENCY_HZ:g} Hz\n"
                f"Measured display rate: {refresh_hz:.3f} Hz\n"
                f"Frames per image: {frames_per_image}\n"
                f"Realized image rate: {realized_hz:.3f} Hz\n\n"
                "Space: start     Escape: quit"
            ),
            height=0.035,
            wrapWidth=1.5,
            autoLog=False,
        )
        ready.draw()
        win.flip()
        event.clearEvents()
        if "escape" in event.waitKeys(keyList=["space", "escape"]):
            return

        # 9. Repeat the fade, applying one contrast value on each screen refresh.
        win.flip()  # Clear the instructions before timing starts.
        win.refreshThreshold = 1.5 / refresh_hz  # Count unusually slow refreshes.
        win.nDroppedFrames = 0  # Count only the image presentation, not startup.
        win.recordFrameIntervals = True
        for _cycle in range(NUMBER_OF_CYCLES):
            for contrast in envelope:
                if event.getKeys(keyList=["escape"]):
                    return
                image.contrast = contrast  # 0 = gray; 1 = the image's original contrast.
                image.draw()
                win.flip()  # Show the newly drawn image on the next screen refresh.

        # 10. Finish on gray and report any late frames in PsychoPy's output.
        win.flip()  # Let the last image frame finish before returning to gray.
        win.recordFrameIntervals = False
        if win.nDroppedFrames:
            logging.warning("Display timing recorded %d late frames.", win.nDroppedFrames)
    finally:
        win.close()  # Always close the window, including after Escape or an error.


if __name__ == "__main__":
    main()  # Start the example when this file is run.
