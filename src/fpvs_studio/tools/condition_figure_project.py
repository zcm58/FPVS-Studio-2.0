"""Read-only bridge from the editable project to a condition figure."""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace
from itertools import chain, cycle, islice
from pathlib import Path

from fpvs_studio.core.compiler_assets import load_manifest, resolve_image_paths
from fpvs_studio.core.compiler_conditions import ordered_conditions
from fpvs_studio.core.condition_timing import effective_condition_base_hz
from fpvs_studio.core.enums import (
    DutyCycleMode,
    ExperimentCategory,
    StimulusModality,
    StimulusVariant,
)
from fpvs_studio.core.masking import condition_masking
from fpvs_studio.core.models import Condition, ProjectFile, StimulusSet
from fpvs_studio.core.paths import (
    STIMULI_DIRNAME,
    filesystem_path,
    resolve_project_relative_path,
)
from fpvs_studio.preprocessing.inspection import (
    MAX_BUNDLE_IMAGE_BYTES,
    ImageInspectionError,
    compute_file_sha256,
)
from fpvs_studio.preprocessing.models import StimulusManifest
from fpvs_studio.tools.condition_figure import ConditionFigureSpec, condition_figure_slot_roles

_BASE_SAMPLE_COUNT = 4
_FIGURE_CATEGORIES = {ExperimentCategory.FPVS_ODDBALL, ExperimentCategory.COGNITIVE_LOAD_FPVS}
_Stimulus = Path | str
_StimulusIdentity = tuple[StimulusModality, str]


@dataclass(frozen=True)
class ConditionFigureSources:
    """Resolved, distinct source choices for a periodic FPVS condition."""

    condition_name: str
    base_hz: float
    oddball_every_n: int
    base_stimuli: tuple[Path | str, ...]
    oddball_stimuli: tuple[Path | str, ...]
    duty_cycle_mode: DutyCycleMode = DutyCycleMode.CONTINUOUS
    background_color: str | tuple[int, int, int] = "#808080"

    def make_spec(
        self, base_stimuli: Sequence[Path | str], oddball_stimulus: Path | str,
    ) -> ConditionFigureSpec:
        """Build a figure from selections that belong to their configured pools."""
        if len(base_stimuli) != _BASE_SAMPLE_COUNT or any(
            stimulus not in self.base_stimuli for stimulus in base_stimuli
        ):
            raise ValueError("Select four examples from the configured Base stimuli.")
        if oddball_stimulus not in self.oddball_stimuli:
            raise ValueError("Select an example from the configured Oddball stimuli.")
        return ConditionFigureSpec(
            condition_name=self.condition_name,
            base_hz=self.base_hz,
            oddball_every_n=self.oddball_every_n,
            base_stimuli=tuple(base_stimuli),
            oddball_stimulus=oddball_stimulus,
            duty_cycle_mode=self.duty_cycle_mode,
            background_color=self.background_color,
        )

    def automatic_spec(self) -> ConditionFigureSpec:
        """Choose unique displayed examples from the configured pools."""
        if not self.base_stimuli or not self.oddball_stimuli:
            raise ValueError("Configure both Base and Oddball stimuli for this condition.")
        roles = condition_figure_slot_roles(self.oddball_every_n)
        sequence = _automatic_sequence(roles, self.base_stimuli, self.oddball_stimuli)
        selected = tuple(zip(roles, sequence, strict=True))
        selected_base = tuple(
            stimulus for oddball, stimulus in selected if not oddball and stimulus is not None
        )
        # Keep valid starting selections when switching to the five-example Manual mode.
        base_examples = tuple(islice(cycle(selected_base or self.base_stimuli), _BASE_SAMPLE_COUNT))
        oddball_example = next(
            (stimulus for oddball, stimulus in selected if oddball and stimulus is not None),
            self.oddball_stimuli[0],
        )
        return replace(self.make_spec(base_examples, oddball_example), sequence_stimuli=sequence)


def _automatic_sequence(
    roles: tuple[bool, ...], base_pool: Sequence[_Stimulus], oddball_pool: Sequence[_Stimulus],
) -> tuple[_Stimulus | None, ...]:
    digests: dict[Path, str] = {}
    oddball_count = roles.count(True)
    base_count = len(roles) - oddball_count
    oddball_candidates = _distinct_stimuli(oddball_pool, oddball_count, digests)
    oddballs = dict(islice(oddball_candidates, oddball_count))
    bases: dict[_StimulusIdentity, _Stimulus] = {}
    shared: dict[_StimulusIdentity, _Stimulus] = {}
    if base_count:
        for identity, stimulus in _distinct_stimuli(base_pool, base_count, digests):
            if identity in oddballs:
                shared[identity] = stimulus
                continue
            bases[identity] = stimulus
            if len(bases) == base_count:
                break

    # Reserve oddballs first. If that exhausts the Base pool, swap shared
    # examples for spare oddballs where possible so both roles stay populated.
    spare_oddballs = (item for item in oddball_candidates if item[0] not in bases)
    for (shared_id, base), (spare_id, oddball) in zip(
        islice(shared.items(), base_count - len(bases)), spare_oddballs, strict=False,
    ):
        del oddballs[shared_id]
        bases[shared_id] = base
        oddballs[spare_id] = oddball

    selected = {False: iter(bases.values()), True: iter(oddballs.values())}
    return tuple(next(selected[role], None) for role in roles)


def _distinct_stimuli(
    pool: Sequence[_Stimulus], count: int, digests: dict[Path, str],
) -> Iterator[tuple[_StimulusIdentity, _Stimulus]]:
    # Spread the first picks across the pool. Visit the remaining configured
    # order only when a candidate is a duplicate or reserved for the other role.
    sample_count = min(count, len(pool))
    spread = tuple(index * (len(pool) - 1) // max(1, sample_count - 1)
                   for index in range(sample_count))
    sampled = set(spread)
    positions = chain(spread, (index for index in range(len(pool)) if index not in sampled))
    seen: set[_StimulusIdentity] = set()
    for index in positions:
        stimulus = pool[index]
        if isinstance(stimulus, Path):
            if stimulus not in digests:
                if not 0 < filesystem_path(stimulus).stat().st_size <= MAX_BUNDLE_IMAGE_BYTES:
                    raise ImageInspectionError(f"Image is too large or empty: {stimulus.name}")
                digests[stimulus] = compute_file_sha256(stimulus)
            identity = (StimulusModality.IMAGE, digests[stimulus])
        else:
            identity = (StimulusModality.WORD, stimulus)
        if identity not in seen:
            seen.add(identity)
            yield identity, stimulus


def condition_figure_candidates(project: ProjectFile) -> tuple[Condition, ...]:
    """List ordinary Base/Oddball conditions in Setup order without reading the disk."""
    if project.experiment_category not in _FIGURE_CATEGORIES:
        return ()
    return tuple(
        condition for condition in ordered_conditions(project)
        if condition.attentional_blink is None
        and not condition.masking_catch
        and condition_masking(project, condition) is None
    )


def load_condition_figure_sources(
    project: ProjectFile, project_root: Path, condition_id: str,
) -> ConditionFigureSources:
    """Resolve configured stimulus choices without compiling or changing the project."""
    condition = next((item for item in condition_figure_candidates(project)
                      if item.condition_id == condition_id), None)
    if condition is None:
        raise ValueError("Select a periodic FPVS condition with Base and Oddball stimuli.")
    sets = {stimulus_set.set_id: stimulus_set for stimulus_set in project.stimulus_sets}
    base_set = sets.get(condition.base_stimulus_set_id)
    oddball_set = sets.get(condition.oddball_stimulus_set_id)
    if base_set is None or oddball_set is None:
        raise ValueError("Assign Base and Oddball stimulus sets in Setup > Conditions.")
    if base_set.modality != oddball_set.modality:
        raise ValueError("Use the same stimulus type for Base and Oddball in Setup > Conditions.")
    manifest = (
        load_manifest(project_root, None) if base_set.modality == StimulusModality.IMAGE else None
    )
    return ConditionFigureSources(
        condition_name=condition.name,
        base_hz=effective_condition_base_hz(project, condition),
        oddball_every_n=project.settings.protocol.oddball_every_n,
        base_stimuli=_pool(
            base_set, condition.stimulus_variant, project_root, manifest, role="Base",
        ),
        oddball_stimuli=_pool(
            oddball_set, condition.stimulus_variant, project_root, manifest, role="Oddball",
        ),
        duty_cycle_mode=condition.duty_cycle_mode,
        background_color=project.settings.display.background_color,
    )


def _pool(
    stimulus_set: StimulusSet, variant: StimulusVariant, project_root: Path,
    manifest: StimulusManifest | None, *, role: str,
) -> tuple[Path | str, ...]:
    if stimulus_set.modality == StimulusModality.WORD:
        if not stimulus_set.words:
            raise ValueError(f"Add {role} words in Setup > Conditions.")
        return tuple(dict.fromkeys(stimulus_set.words))
    try:
        paths = resolve_image_paths(
            stimulus_set, variant=variant, project_root=project_root, manifest=manifest,
        )
        return tuple(dict.fromkeys(
            resolve_project_relative_path(project_root, path) for path in paths
        ))
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not load {role} images. {error}") from error


def validate_condition_figure_destination(
    project: ProjectFile, project_root: Path, output_path: Path,
) -> None:
    """Keep figure exports out of project stimulus folders and existing asset paths."""
    project_path = filesystem_path(Path(os.path.abspath(project_root)))
    destination = filesystem_path(Path(os.path.abspath(output_path)))
    root = project_path.resolve()
    # Replacement writes to the directory entry even when the filename is a symlink.
    targets = {destination, destination.parent.resolve() / destination.name, destination.resolve()}
    if not destination.is_relative_to(project_path) and not any(
        target.is_relative_to(root) for target in targets
    ):
        return

    source_dirs = {STIMULI_DIRNAME}
    source_dirs.update(
        item.source_dir for item in project.stimulus_sets if item.source_dir is not None
    )
    manifest = load_manifest(project_root, None)
    if manifest is not None:
        source_dirs.update(item.source_dir for item in manifest.sets)
    for folder in source_dirs:
        directory = project_path / Path(folder)
        resolved_directory = directory.resolve()
        if destination.is_relative_to(directory) or any(
            target.is_relative_to(resolved_directory) for target in targets
        ):
            raise ValueError("Choose an export location outside the project's stimulus folders.")

    if manifest is not None:
        for manifest_set in manifest.sets:
            for asset in manifest_set.assets:
                paths = (
                    asset.source.relative_path,
                    *(record.relative_path for record in asset.derivatives),
                )
                if any(
                    (project_path / Path(relative_path)).resolve() in targets
                    for relative_path in paths
                ):
                    raise ValueError("Choose an export location that does not replace a stimulus.")
