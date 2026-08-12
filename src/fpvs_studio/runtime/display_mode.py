"""Platform-neutral selection of the active primary/default display mode."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from math import isfinite


class DisplayModeError(RuntimeError):
    """Raised when the active native display mode cannot be determined safely."""


@dataclass(frozen=True)
class NativeDisplayMode:
    """Native configured mode for the display used by default fullscreen playback."""

    platform_name: str
    display_name: str
    refresh_hz: float
    source_name: str
    exact_refresh: bool
    mode_reference: str | None = None
    variable_refresh_enabled: bool = False
    variable_refresh_label: str | None = None

    def __post_init__(self) -> None:
        if not isfinite(self.refresh_hz) or self.refresh_hz <= 0:
            raise ValueError("Native display refresh rate must be finite and positive.")
        if not self.platform_name.strip():
            raise ValueError("Native display platform name must not be blank.")
        if not self.display_name.strip():
            raise ValueError("Native display name must not be blank.")
        if not self.source_name.strip():
            raise ValueError("Native display source name must not be blank.")

    @property
    def hz(self) -> float:
        """Return the native configured refresh rate."""

        return self.refresh_hz

    @property
    def mode_text(self) -> str:
        """Return user-facing mode details with platform-appropriate precision."""

        precision = 6 if self.exact_refresh else 3
        details = self.mode_reference or f"{self.source_name}, {self.display_name}"
        return f"{self.refresh_hz:.{precision}f} Hz ({details})"

    @property
    def status_text(self) -> str:
        """Return the shorter mode text used by compact GUI status surfaces."""

        details = self.mode_reference or f"{self.source_name}, {self.display_name}"
        return f"{self.refresh_hz:.3f} Hz ({details})"


def query_primary_native_display_mode() -> NativeDisplayMode:
    """Return the native mode for the primary/default fullscreen display."""

    if sys.platform == "win32":
        from fpvs_studio.runtime.windows_display import (
            WindowsDisplayModeError,
            query_primary_windows_display_mode,
        )

        try:
            windows_mode = query_primary_windows_display_mode()
        except WindowsDisplayModeError as exc:
            raise DisplayModeError(f"Exact Windows display mode could not be read: {exc}") from exc
        return NativeDisplayMode(
            platform_name="Windows",
            display_name=windows_mode.display_device_name,
            refresh_hz=windows_mode.hz,
            source_name="QueryDisplayConfig",
            exact_refresh=True,
            mode_reference=windows_mode.fraction_text,
            variable_refresh_enabled=windows_mode.dynamic_refresh_enabled,
            variable_refresh_label=(
                "Dynamic Refresh Rate" if windows_mode.dynamic_refresh_enabled else None
            ),
        )

    if sys.platform.startswith("linux"):
        from fpvs_studio.runtime.linux_display import query_primary_linux_display_mode

        return query_primary_linux_display_mode()

    raise DisplayModeError(
        f"Native display-mode detection is not supported on platform {sys.platform!r}."
    )
