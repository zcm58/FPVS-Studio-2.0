"""Runtime orchestration package for launched FPVS sessions.
Its modules consume compiled RunSpec and SessionPlan artifacts, add machine-specific launch settings, and return neutral execution summaries plus exports.
The package owns execution flow above the engine seam, not editable project modeling or preprocessing."""

from fpvs_studio.runtime.launcher import (
    LaunchSettings,
    LaunchSettingsError,
    launch_run,
    launch_session,
)

__all__ = ["LaunchSettings", "LaunchSettingsError", "launch_run", "launch_session"]
