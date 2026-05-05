"""Stimulus import and manifest helpers for the GUI project document facade."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fpvs_studio.core.models import ProjectFile, StimulusSet
from fpvs_studio.gui.document_support import validated_copy
from fpvs_studio.preprocessing.importer import (
    import_stimulus_source_directory,
    materialize_project_assets,
)
from fpvs_studio.preprocessing.inspection import inspect_source_directory, summary_to_stimulus_set
from fpvs_studio.preprocessing.manifest import (
    create_empty_manifest,
    inspection_summary_to_manifest_set,
    upsert_manifest_set,
    write_stimulus_manifest,
)
from fpvs_studio.preprocessing.models import StimulusManifest


class DocumentStimulusMixin:
    """Stimulus and preprocessing-manifest methods for `ProjectDocument`."""

    if TYPE_CHECKING:
        _project: ProjectFile
        _project_root: Path
        _manifest: StimulusManifest | None
        manifest_changed: Any

        def get_condition_stimulus_set(
            self,
            condition_id: str,
            role: str,
        ) -> StimulusSet: ...
        def get_stimulus_set(self, set_id: str) -> StimulusSet | None: ...
        def _replace_project(self, project: ProjectFile) -> None: ...

    def import_condition_stimulus_folder(
        self,
        condition_id: str,
        *,
        role: str,
        source_dir: Path,
    ) -> StimulusSet:
        """Import one base or oddball source folder directly into the project."""

        stimulus_set = self.get_condition_stimulus_set(condition_id, role)
        _, imported_set = import_stimulus_source_directory(
            source_dir=Path(source_dir),
            project_root=self._project_root,
            set_id=stimulus_set.set_id,
            set_name=stimulus_set.name,
        )
        updated_sets = [
            imported_set if item.set_id == imported_set.set_id else item
            for item in self._project.stimulus_sets
        ]
        project = validated_copy(self._project, stimulus_sets=updated_sets)
        self._replace_project(project)
        self._update_manifest_for_stimulus_set(imported_set.set_id)
        return imported_set

    def refresh_stimulus_inspection(self) -> None:
        """Re-inspect all imported source folders and refresh project metadata."""

        updated_sets: list[StimulusSet] = []
        manifest = self._manifest or create_empty_manifest(self._project.meta.project_id)

        for stimulus_set in self._project.stimulus_sets:
            source_dir = self._project_root / Path(stimulus_set.source_dir)
            summary = inspect_source_directory(
                source_dir,
                relative_prefix=stimulus_set.source_dir,
                strict=True,
            )
            refreshed_set = summary_to_stimulus_set(
                set_id=stimulus_set.set_id,
                name=stimulus_set.name,
                summary=summary,
            )
            refreshed_set = refreshed_set.model_copy(
                update={"available_variants": stimulus_set.available_variants}
            )
            updated_sets.append(refreshed_set)
            manifest = upsert_manifest_set(
                manifest,
                inspection_summary_to_manifest_set(
                    set_id=stimulus_set.set_id,
                    summary=summary,
                ),
            )

        project = validated_copy(self._project, stimulus_sets=updated_sets)
        self._replace_project(project)
        self._manifest = manifest
        write_stimulus_manifest(self._project_root, manifest)
        self.manifest_changed.emit()

    def materialize_assets(self) -> StimulusManifest:
        """Materialize configured stimulus variants via the preprocessing pipeline."""

        manifest = materialize_project_assets(self._project, project_root=self._project_root)
        self._manifest = manifest
        synced_sets = self._sync_stimulus_sets_from_manifest(manifest)
        project = validated_copy(self._project, stimulus_sets=synced_sets)
        self._replace_project(project)
        self.manifest_changed.emit()
        return manifest

    def _update_manifest_for_stimulus_set(self, set_id: str) -> None:
        stimulus_set = self.get_stimulus_set(set_id)
        if stimulus_set is None:
            return
        source_dir = self._project_root / Path(stimulus_set.source_dir)
        summary = inspect_source_directory(
            source_dir,
            relative_prefix=stimulus_set.source_dir,
            strict=True,
        )
        manifest = self._manifest or create_empty_manifest(self._project.meta.project_id)
        manifest = upsert_manifest_set(
            manifest,
            inspection_summary_to_manifest_set(
                set_id=set_id,
                summary=summary,
            ),
        )
        self._manifest = manifest
        write_stimulus_manifest(self._project_root, manifest)
        self.manifest_changed.emit()

    def _sync_stimulus_sets_from_manifest(
        self,
        manifest: StimulusManifest,
    ) -> list[StimulusSet]:
        manifest_sets = {manifest_set.set_id: manifest_set for manifest_set in manifest.sets}
        synced_sets: list[StimulusSet] = []
        for stimulus_set in self._project.stimulus_sets:
            manifest_set = manifest_sets.get(stimulus_set.set_id)
            if manifest_set is None:
                synced_sets.append(stimulus_set)
                continue
            resolution = (
                manifest_set.assets[0].source.resolution
                if manifest_set.assets
                else stimulus_set.resolution
            )
            synced_sets.append(
                stimulus_set.model_copy(
                    update={
                        "image_count": len(manifest_set.assets),
                        "resolution": resolution,
                        "available_variants": manifest_set.available_variants,
                    }
                )
            )
        return synced_sets
