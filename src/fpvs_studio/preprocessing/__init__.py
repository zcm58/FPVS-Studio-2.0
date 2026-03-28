"""Preprocessing package for stimulus intake and derived-asset materialization.
These modules turn source image sets into validated manifest-backed originals and control variants consumed later by core compilation.
The package owns preprocessing provenance and determinism, not RunSpec generation, session flow, or engine presentation."""

from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)

__all__ = ["import_stimulus_source_directory", "materialize_project_assets"]
