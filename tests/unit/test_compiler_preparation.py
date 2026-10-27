"""Invocation-local preparation preserves the complete seeded compilation contract."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

import fpvs_studio.core.compiler as compiler
import fpvs_studio.core.compiler_assets as compiler_assets
import fpvs_studio.core.compiler_inputs as compiler_inputs
import fpvs_studio.core.compiler_presentation as compiler_presentation
import fpvs_studio.core.compiler_schedules as compiler_schedules
import fpvs_studio.core.compiler_tasks as compiler_tasks
from fpvs_studio.core.attentional_blink_presets import populate_attentional_blink_stream
from fpvs_studio.core.compiler import CompileError, compile_session_plan
from fpvs_studio.core.compiler_limits import CompilationLimits, validate_compilation_workload
from fpvs_studio.core.compiler_support import (
    check_compilation_cancelled,
    compilation_cancellation,
    consume_compilation_work,
)
from fpvs_studio.core.condition_modifiers import (
    MemoryImage,
    assign_modifier,
    create_backward_counting_modifier,
    create_image_memory_modifier,
)
from fpvs_studio.core.enums import (
    ExperimentCategory,
    StimulusModality,
    StimulusVariant,
    TextHeightMode,
)
from fpvs_studio.core.models import ProjectFile, StimulusSet, TextHeightScheduleSettings
from fpvs_studio.core.task_models import TaskBinding, TaskModule, TaskStep, TaskStepKind
from fpvs_studio.preprocessing.importer import materialize_project_assets


def _memory_definition(root: Path):
    targets, foils = [], []
    for index in range(8):
        image_id = f"image-{index}"
        for role in (["study", "recognition"] if index < 4 else ["recognition"]):
            path = f"stimuli/task-assets/image-memory-{role}/{image_id}.png"
            absolute = root / path
            absolute.parent.mkdir(parents=True, exist_ok=True)
            absolute.write_bytes(f"unique-image-content-{index}".encode())
            if role == "study":
                targets.append(MemoryImage(image_id=image_id, image_path=path))
            elif index >= 4:
                foils.append(MemoryImage(image_id=image_id, image_path=path))
    return create_image_memory_modifier(target_images=targets, foil_images=foils)


def _scenario(project: ProjectFile, root: Path, kind: str) -> ProjectFile:
    if kind == "word":
        project.stimulus_sets = [
            StimulusSet(
                set_id=item.set_id, name=item.name, modality=StimulusModality.WORD,
                words=[f"{item.set_id}-{index}" for index in range(7)],
            )
            for item in project.stimulus_sets
        ]
        project.settings.presentation.defaults.text_height = TextHeightScheduleSettings(
            mode=TextHeightMode.BALANCED_RANDOMIZED, values=[1.0, 1.5, 2.0],
        )
    elif kind == "ab":
        settings = project.settings.model_copy(deep=True)
        settings.protocol.base_hz = 10
        project = populate_attentional_blink_stream(ProjectFile(
            meta=project.meta.model_copy(deep=True), settings=settings,
            experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
        ))
        project.settings.session.block_count = 2
    elif kind in {"counting", "memory"}:
        definition = (
            create_backward_counting_modifier(baseline_duration_seconds=30)
            if kind == "counting" else _memory_definition(root)
        )
        project = assign_modifier(
            project, definition, [condition.condition_id for condition in project.conditions],
        )
    return project


# Captured from the pre-refactor compiler on 2026-09-18. Every serialized field,
# including all schedules, task orders, answer keys and seeds, contributes to the digest.
_BASELINE_DIGESTS = {
    ("image", 42): "786b1d71fad4db2adb7d4a134062a7dfa69fa8bd4ed9ab52e3fb17a212431846",
    ("image", 83): "f742c97a50978cb6cf63f397022afe054da74ab2ead3a6e4af53ab7d023c2754",
    ("word", 42): "1d861c6f8b261cfe5414f20f572bf06ff9d9e921ef88eb4a942bbd06430e5599",
    ("word", 83): "45eb0b1ba7c05c15ec8088b4a2a46094c8cd7d135af980aee4fded1f075f2202",
    ("ab", 42): "fe6618028685e8267b3a057153baf5f55e88560bd10c8ff8fb18f0c887136301",
    ("ab", 83): "221d8dcbc373e3055e0b2b91dabd7a6e6eed2d28f4e4b0b01f35238e8a13cba3",
    ("counting", 42): "7aab544d020aaef30b4e487424489b709220e9e22a3e99609459bbfb927d28bc",
    ("counting", 83): "8140f5b277ab0ef3ef1807fb7ebba884d16959ba6042bfd8d4fb8791db92f6e3",
    ("memory", 42): "42de4865f5974e7eee4bca0ba3accf57f35b9014a98ed9a09c18d5b5f51a9d49",
    ("memory", 83): "48e6587af41574aa74b6277904e19d498caf4634839c7cb813008f47277d6648",
}


@pytest.mark.parametrize("kind", ["image", "word", "ab", "counting", "memory"])
@pytest.mark.parametrize("seed", [42, 83])
@pytest.mark.parametrize("limits", [None, CompilationLimits()])
def test_complete_seeded_plan_matches_preparation_baseline(
    multi_condition_project, multi_condition_project_root, kind, seed, limits,
) -> None:
    project = _scenario(multi_condition_project, multi_condition_project_root, kind)
    plan = compile_session_plan(
        project, refresh_hz=60, project_root=multi_condition_project_root,
        random_seed=seed, session_id="preparation-parity",
        limits=limits,
    )
    payload = json.dumps(plan.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode()).hexdigest()
    assert digest == _BASELINE_DIGESTS[(kind, seed)]


@pytest.mark.parametrize("field", ["sequence_count", "oddball_cycle_repeats_per_sequence"])
@pytest.mark.parametrize("kind", ["image", "word", "ab"])
def test_untrusted_event_expansion_fails_before_any_run_compilation(
    sample_project, sample_project_root, monkeypatch, field, kind,
) -> None:
    project = _scenario(sample_project, sample_project_root, kind)
    setattr(project.conditions[0], field, 1_000_000_000)

    def unexpected(*args, **kwargs):
        raise AssertionError("A rejected workload must not allocate run schedules.")

    monkeypatch.setattr(compiler, "_compile_prepared_run", unexpected)
    with pytest.raises(CompileError, match="events per run limit"):
        compile_session_plan(
            project, refresh_hz=60, project_root=sample_project_root,
            limits=CompilationLimits(),
        )


@pytest.mark.parametrize("shuffle_all", [False, True])
def test_untrusted_session_repetitions_fail_before_expanding_conditions(
    sample_project, monkeypatch, shuffle_all,
) -> None:
    sample_project.settings.session.block_count = 1_000_000_000
    sample_project.settings.session.randomize_across_blocks = shuffle_all
    monkeypatch.setattr(
        compiler, "_compile_session_plan",
        lambda *args, **kwargs: pytest.fail("Session expansion started before its budget check."),
    )
    with pytest.raises(CompileError, match="session entries limit"):
        compile_session_plan(sample_project, refresh_hz=60, limits=CompilationLimits())


@pytest.mark.parametrize("field", ["module", "step", "attempts"])
def test_untrusted_task_repeat_products_are_bounded(sample_project, field) -> None:
    module = TaskModule(task_id="large", name="Large", steps=[TaskStep(
        step_id="instructions", kind=TaskStepKind.INSTRUCTION,
        text="Review instructions", continue_key="space",
    )])
    if field == "module":
        module.repeat_count = 1_000_000_000
    elif field == "step":
        module.steps[0].repeat_count = 1_000_000_000
    else:
        module.steps[0].max_attempts = 1_000_000_000
    sample_project.task_modules = [module]
    sample_project.conditions[0].pre_task_bindings = [TaskBinding(task_id="large")]
    with pytest.raises(CompileError, match="task expansion limit"):
        validate_compilation_workload(
            sample_project, sample_project.conditions, refresh_hz=60,
            limits=CompilationLimits(),
        )


def test_untrusted_fixation_candidate_range_is_bounded(sample_project) -> None:
    fixation = sample_project.settings.fixation_task
    fixation.target_count_mode = "randomized"
    fixation.target_count_max = 1_000_000_000
    with pytest.raises(CompileError, match="fixation count candidates limit"):
        compile_session_plan(sample_project, refresh_hz=60, limits=CompilationLimits())


def test_untrusted_total_events_and_frames_are_bounded(sample_project) -> None:
    with pytest.raises(CompileError, match="total events limit"):
        compile_session_plan(
            sample_project, refresh_hz=60, limits=CompilationLimits(max_total_events=1),
        )
    sample_project.settings.presentation.pre_stream_fixation_seconds = 1_000_000_000
    with pytest.raises(CompileError, match="total frames limit"):
        compile_session_plan(sample_project, refresh_hz=60, limits=CompilationLimits())


@pytest.mark.parametrize("refresh_hz", [float("inf"), float("nan"), 0.0, -60.0, 75.0, 1e308])
def test_untrusted_refresh_rate_has_actionable_compile_error(sample_project, refresh_hz) -> None:
    with pytest.raises(CompileError, match="refresh rate must be an approved value"):
        compile_session_plan(
            sample_project, refresh_hz=refresh_hz, limits=CompilationLimits(),
        )


@pytest.mark.parametrize("field", ["base_rate", "lead_in"])
def test_untrusted_timing_overflow_is_rejected_before_frame_conversion(sample_project, field):
    if field == "base_rate":
        sample_project.settings.protocol.base_hz = 5e-324
    else:
        sample_project.settings.presentation.pre_stream_fixation_seconds = 1e308
    with pytest.raises(CompileError, match="total frames limit"):
        compile_session_plan(sample_project, refresh_hz=60, limits=CompilationLimits())


def test_large_word_cadence_uses_constant_time_role_boundary_lookup(
    sample_project, sample_project_root, monkeypatch,
) -> None:
    project = _scenario(sample_project, sample_project_root, "word")
    project.settings.session.block_count = 1
    project.settings.protocol.oddball_every_n = 80_000
    project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    validate_compilation_workload(
        project, project.conditions, refresh_hz=60, limits=CompilationLimits(),
    )

    def bounded_range(*args):
        result = range(*args)
        if len(args) == 2 and len(result) > 256:
            raise AssertionError("Role-boundary lookup must not scan the remaining stimulus tail.")
        return result

    # The former per-event tail scan would perform 3.2 billion iterations here;
    # reject its first long scan without making the regression itself expensive.
    monkeypatch.setattr(compiler_presentation, "range", bounded_range, raising=False)
    values = compiler_presentation.build_interleaved_text_height_values(
        {"base": TextHeightScheduleSettings(values=[1.0]),
         "oddball": TextHeightScheduleSettings(values=[2.0])},
        total_stimuli=80_000, oddball_every_n=80_000, random_seed=42,
    )
    assert values == {"base": [1.0] * 79_999, "oddball": [2.0]}


def test_untrusted_small_schedule_cannot_exhaust_recursive_search_budget():
    # Only fifty words can induce combinatorial feasibility search. Count search
    # work itself rather than assuming a small event count implies a cheap compile.
    with pytest.raises(CompileError, match="schedule work limit"):
        with compilation_cancellation(None, max_work_units=4_096):
            compiler_schedules._counts_after_selection_can_bridge_to_forced(
                Counter({"A": 30, "B": 10, "C": 10}),
                previous_key="A", draws_before_forced=49, forced_key="A",
            )
    consume_compilation_work(4_097)  # The failed invocation must not retain its budget.


def test_untrusted_small_word_project_enforces_work_budget(sample_project, sample_project_root):
    project = _scenario(sample_project, sample_project_root, "word")
    project.settings.session.block_count = 1
    project.settings.protocol.oddball_every_n = 51
    project.settings.fixation_task.enabled = False
    project.conditions[0].oddball_cycle_repeats_per_sequence = 1
    project.stimulus_sets[0].words = ["A"] * 30 + ["B"] * 10 + ["C"] * 10
    project.stimulus_sets[1].words = ["A"]
    project.settings.presentation.defaults.text_height = TextHeightScheduleSettings(values=[1.0])
    validate_compilation_workload(
        project, project.conditions, refresh_hz=60, limits=CompilationLimits(),
    )
    with pytest.raises(CompileError, match="schedule work limit"):
        compile_session_plan(
            project, refresh_hz=60, project_root=sample_project_root, random_seed=0,
            limits=CompilationLimits(max_schedule_work=4_096),
        )
    consume_compilation_work(4_097)


@pytest.mark.parametrize("kind", ["image", "word", "ab"])
def test_compilation_cancels_inside_schedules_and_resets_invocation_context(
    sample_project, sample_project_root, monkeypatch, kind,
) -> None:
    project = _scenario(sample_project, sample_project_root, kind)
    schedule_started = False
    checks_inside = 0
    name = ("compile_attentional_blink_stream_sequence" if kind == "ab"
            else "build_interleaved_text_height_values" if kind == "word"
            else "build_stimulus_sequence")
    original = getattr(compiler, name)

    def schedule(*args, **kwargs):
        nonlocal schedule_started
        schedule_started = True
        return original(*args, **kwargs)

    class CancelledProbe(Exception):
        pass

    def cancel():
        nonlocal checks_inside
        if schedule_started:
            checks_inside += 1
            if checks_inside == 2:
                raise CancelledProbe("cancelled during schedule construction")

    monkeypatch.setattr(compiler, name, schedule)
    with pytest.raises(CancelledProbe, match="during schedule"):
        compile_session_plan(
            project, refresh_hz=60, project_root=sample_project_root,
            limits=CompilationLimits(), cancel_check=cancel,
        )
    assert checks_inside == 2
    check_compilation_cancelled()
    assert checks_inside == 2
    # A later invocation must not retain the previous cancellation callback.
    assert compile_session_plan(
        project, refresh_hz=60, project_root=sample_project_root,
        limits=CompilationLimits(),
    ).total_runs > 0


def test_compilation_context_resets_after_preflight_cancellation(sample_project) -> None:
    def cancel():
        raise InterruptedError("cancelled before compilation")

    with pytest.raises(InterruptedError, match="before compilation"):
        compile_session_plan(sample_project, refresh_hz=60, cancel_check=cancel)
    check_compilation_cancelled()


def test_compilation_can_cancel_during_task_media_hashing(
    sample_project, sample_project_root, monkeypatch,
) -> None:
    project = _scenario(sample_project, sample_project_root, "memory")
    hashing = False
    original = compiler_tasks.TaskCompilationInputs.asset_hash

    def asset_hash(*args, **kwargs):
        nonlocal hashing
        hashing = True
        return original(*args, **kwargs)

    def cancel():
        if hashing:
            raise InterruptedError("cancelled task media hash")

    monkeypatch.setattr(compiler_tasks.TaskCompilationInputs, "asset_hash", asset_hash)
    with pytest.raises(InterruptedError, match="task media hash"):
        compile_session_plan(
            project, refresh_hz=60, project_root=sample_project_root,
            limits=CompilationLimits(), cancel_check=cancel,
        )
    check_compilation_cancelled()


def test_repeated_session_media_work_scales_with_unique_inputs(
    multi_condition_project, multi_condition_project_root, monkeypatch,
) -> None:
    project = _scenario(multi_condition_project, multi_condition_project_root, "memory")
    project.settings.session.block_count = 10
    counts: Counter[str] = Counter()

    def count_calls(module, name):
        original = getattr(module, name)

        def counted(*args, **kwargs):
            counts[name] += 1
            return original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)

    for module, name in (
        (compiler, "require_valid_experiment_category"),
        (compiler_inputs, "load_manifest"),
        (compiler_inputs, "validate_selected_condition"),
        (compiler_inputs, "resolve_stimulus_items"),
        (compiler_assets, "_resolve_filesystem_image_paths"),
        (compiler_tasks, "_validate_task_asset"),
        (compiler_tasks, "_prepare_image_memory_pair"),
    ):
        count_calls(module, name)
    original_open = Path.open

    def counted_open(path, mode="r", *args, **kwargs):
        if mode == "rb" and "task-assets" in path.parts:
            counts["hash_file_open"] += 1
        return original_open(path, mode, *args, **kwargs)

    def reject_unbounded_read(path):
        raise AssertionError(f"Compilation must stream media hashes: {path}")

    monkeypatch.setattr(Path, "open", counted_open)
    monkeypatch.setattr(Path, "read_bytes", reject_unbounded_read)
    plan = compile_session_plan(
        project, refresh_hz=60, project_root=multi_condition_project_root,
        random_seed=42, session_id="preparation-counts",
    )
    assert plan.total_runs == 40
    assert counts == {
        "require_valid_experiment_category": 1,
        "load_manifest": 1,
        "validate_selected_condition": 4,
        "resolve_stimulus_items": 2,
        "_resolve_filesystem_image_paths": 2,
        "_validate_task_asset": 12,
        "_prepare_image_memory_pair": 40,
        "hash_file_open": 12,
    }


@pytest.mark.parametrize("change", ["remove", "replace"])
def test_later_compilation_rechecks_memory_media(
    multi_condition_project, multi_condition_project_root, change,
) -> None:
    project = _scenario(multi_condition_project, multi_condition_project_root, "memory")
    compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)
    path = multi_condition_project_root / "stimuli/task-assets/image-memory-study/image-0.png"
    if change == "remove":
        path.unlink()
        message = "Task asset is missing"
    else:
        path.write_bytes(b"changed target")
        message = "identical images"
    with pytest.raises(CompileError, match=message):
        compile_session_plan(project, refresh_hz=60, project_root=multi_condition_project_root)


def test_later_compilation_rechecks_absent_manifest_and_source_pools(
    multi_condition_project, multi_condition_project_root,
) -> None:
    project, root = multi_condition_project, multi_condition_project_root
    first = compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=42)
    source = root / project.stimulus_sets[0].source_dir
    deleted = sorted(source.iterdir())[0]
    relative = deleted.relative_to(root).as_posix()
    assert any(event.image_path == relative
               for event in first.ordered_entries()[0].run_spec.stimulus_sequence)
    deleted.unlink()
    second = compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=42)
    assert all(event.image_path != relative for entry in second.ordered_entries()
               for event in entry.run_spec.stimulus_sequence)
    (root / "stimuli/manifest.json").write_text("invalid manifest", encoding="utf-8")
    with pytest.raises(ValueError):
        compile_session_plan(project, refresh_hz=60, project_root=root, random_seed=42)


def test_prepared_inputs_do_not_share_mutable_run_or_task_outputs(
    multi_condition_project, multi_condition_project_root,
) -> None:
    project = _scenario(multi_condition_project, multi_condition_project_root, "memory")
    original_project = project.model_dump()
    plan = compile_session_plan(
        project, refresh_hz=60, project_root=multi_condition_project_root, random_seed=42,
    )
    first = plan.ordered_entries()[0]
    repeated = next(entry for entry in plan.ordered_entries()[1:]
                    if entry.condition_id == first.condition_id)
    repeated_before = repeated.model_dump()
    post_before = first.post_tasks[0].model_dump()
    assert first.run_spec.random_seed != repeated.run_spec.random_seed
    first.run_spec.presentation.base.image_geometry.source_resolution.width_px = 999
    first.run_spec.presentation.oddball.image_geometry.width_degrees = 999
    first.run_spec.stimulus_sequence[0].image_path = "stimuli/mutated.png"
    first.pre_tasks[0].image_memory.study_order.reverse()
    first.pre_tasks[0].steps[0].items[0].image_path = "stimuli/mutated-task.png"
    assert repeated.model_dump() == repeated_before
    assert first.post_tasks[0].model_dump() == post_before
    assert project.model_dump() == original_project


def test_streamed_memory_hash_reads_bounded_chunks(sample_project, tmp_path, monkeypatch) -> None:
    path = tmp_path / "stimuli/task-assets/probe/image.png"
    path.parent.mkdir(parents=True)
    payload = b"large image bytes" * 20_000
    path.write_bytes(payload)
    original_open = Path.open
    sizes = []

    class CheckedReader:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size=-1):
            assert 0 < size <= 65_536
            sizes.append(size)
            return self.handle.read(size)

    def checked_open(path, mode="r", *args, **kwargs):
        handle = original_open(path, mode, *args, **kwargs)
        return CheckedReader(handle) if mode == "rb" else handle

    monkeypatch.setattr(Path, "open", checked_open)
    inputs = compiler_tasks.TaskCompilationInputs(sample_project, tmp_path)
    result = inputs.asset_hash("probe", "stimuli/task-assets/probe/image.png")
    assert result == hashlib.sha256(payload).hexdigest()
    assert len(sizes) > 2


@pytest.mark.parametrize("change", ["missing", "escape"])
def test_later_compilation_revalidates_supplied_manifest_paths(
    multi_condition_project, multi_condition_project_root, change,
) -> None:
    project, root = multi_condition_project, multi_condition_project_root
    manifest = materialize_project_assets(
        project, project_root=root, variants=[StimulusVariant.ORIGINAL],
    )
    compile_session_plan(project, refresh_hz=60, project_root=root, manifest=manifest)
    asset = manifest.sets[0].assets[0]
    if change == "missing":
        (root / asset.source.relative_path).unlink()
        message = "does not exist"
    else:
        # Editable models are mutable; compilation still checks lexical containment.
        asset.source.relative_path = "../outside.png"
        message = "escapes the project root"
    with pytest.raises(CompileError, match=message):
        compile_session_plan(project, refresh_hz=60, project_root=root, manifest=manifest)


def test_shared_sets_keep_distinct_variant_pools(
    multi_condition_project, multi_condition_project_root,
) -> None:
    project, root = multi_condition_project, multi_condition_project_root
    manifest = materialize_project_assets(
        project, project_root=root, variants=[StimulusVariant.GRAYSCALE],
    )
    grayscale_ids = set()
    for condition in project.conditions[::2]:
        condition.stimulus_variant = StimulusVariant.GRAYSCALE
        grayscale_ids.add(condition.condition_id)
    plan = compile_session_plan(project, refresh_hz=60, project_root=root, manifest=manifest)
    for entry in plan.ordered_entries():
        prefix = ("stimuli/generated-variants/" if entry.condition_id in grayscale_ids
                  else "stimuli/original-images/")
        assert all(event.image_path.startswith(prefix)
                   for event in entry.run_spec.stimulus_sequence)
