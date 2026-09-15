"""Study defaults and atomic document edits without a Qt application."""

from collections import Counter
from pathlib import Path

import pytest

from fpvs_studio.core.attentional_blink_presets import is_attentional_blink_stream_project
from fpvs_studio.core.compiler import CompileError, compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_PROFILE_ID,
    ATTENTIONAL_BLINK_STREAM_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.models import AttentionalBlinkSettings, ConditionTemplateProfile
from fpvs_studio.core.project_config import create_project_from_config, export_project_config
from fpvs_studio.core.project_service import build_starter_project, create_project
from fpvs_studio.core.run_spec import event_presentation
from fpvs_studio.core.serialization import load_project_file, save_project_file
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskOccurrence,
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
)
from fpvs_studio.gui.document_conditions import DocumentConditionMixin


class _Document(DocumentConditionMixin):
    def __init__(self, project, root):
        self._project = project
        self._project_root = root
        self.replacements = 0

    def _replace_project(self, project):
        self._project = project
        self.replacements += 1


@pytest.fixture
def study():
    return build_starter_project(
        "AB study", experiment_category=ExperimentCategory.ATTENTIONAL_BLINK
    )


def test_new_study_has_five_second_bursts_and_separate_recall_questions(study):
    assert study.schema_version == ProjectSchemaVersion.V1_5
    assert is_attentional_blink_stream_project(study)
    assert study.settings.protocol.base_hz == 10
    assert not study.settings.fixation_task.show_cross
    assert build_starter_project("Oddball").settings.fixation_task.show_cross
    assert study.settings.protocol.oddball_every_n == 50
    assert study.settings.session.block_count == 24
    assert study.settings.session.randomize_across_blocks
    assert study.settings.condition_profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    assert [c.attentional_blink.soa_ms for c in study.conditions] == [100, 300, 500]
    assert [c.trigger_code for c in study.conditions] == [1, 3, 5]
    assert len(study.stimulus_sets) == 3
    assert all(s.modality == StimulusModality.WORD and s.source_dir is None
               for s in study.stimulus_sets)
    assert all(c.isi_stimulus_set_id is None for c in study.conditions)
    assert not study.settings.fixation_task.accuracy_task_enabled
    questions = [step.questions[0] for step in study.task_modules[0].steps]
    assert [question.prompt for question in questions] == [
        "What was the green number?", "What was the second number?",
    ]
    assert [question.question_id for question in questions] == ["t1-recall", "t2-recall"]
    assert all(question.kind == TaskQuestionKind.SHORT_TEXT and question.required
               and question.max_text_length == 32 and question.correct_text is None
               and not question.options for question in questions)
    assert all(step.submit_label == "Next" and step.submission_mode.value == "explicit"
               for step in study.task_modules[0].steps)
    for c in study.conditions:
        assert c.post_task_bindings[0].task_id == study.task_modules[0].task_id
        assert c.post_task_bindings[0].occurrence.value == "every_entry"
        spec = compile_run_spec(study, condition_id=c.condition_id, refresh_hz=60)
        first_cycle = spec.stimulus_sequence
        assert len(first_cycle) == 50
        assert spec.display.total_frames == 300
        assert spec.pre_stream_fixation_frames == 0
        assert all(e.on_frames == 6 and e.off_frames == 0 for e in first_cycle)
        t1 = next(e for e in first_cycle if e.phase == "t1")
        t2 = next(e for e in first_cycle if e.phase == "t2")
        assert sum(e.phase == "t1" for e in first_cycle) == 1
        assert sum(e.phase == "t2" for e in first_cycle) == 1
        assert t1.text.isdigit() and t2.text.isdigit() and t1.text != t2.text
        assert all(e.text.isalpha() for e in first_cycle if e.phase == "base")
        assert event_presentation(spec, t1).text.color == "#00FF00"
        assert event_presentation(spec, t2).text.color == "#FFFFFF"
        assert t2.on_start_frame == 180
        assert [(event.label, event.code) for event in spec.trigger_events] == [
            ("condition_start", c.trigger_code), ("t1_onset", 55), ("t2_onset", 56),
        ]
        assert (t2.on_start_frame - t1.on_start_frame) * 1000 / 60 == c.attentional_blink.soa_ms
    session = compile_session_plan(study, refresh_hz=60)
    assert session.block_count == 1 and session.total_runs == 72
    assert Counter(e.condition_id for e in session.ordered_entries()) == {
        c.condition_id: 24 for c in study.conditions
    }
    for block in session.blocks:
        for entry in block.entries:
            assert len(entry.post_tasks) == 1
            assert entry.post_tasks[0].task_id == study.task_modules[0].task_id
            targets = {e.phase: e.text for e in entry.run_spec.stimulus_sequence
                       if e.phase in ("t1", "t2")}
            for step, phase in zip(entry.post_tasks[0].steps, ("t1", "t2"), strict=True):
                assert step.questions[0].correct_text == targets[phase]
                assert step.submit_label == "Next"
    assert all(entry.show_condition_start_gate for entry in session.ordered_entries())
    assert session.transition.continue_key == "space"


def test_legacy_image_profile_is_not_offered_and_creation_is_blocked():
    assert all(p.profile_id != ATTENTIONAL_BLINK_PROFILE_ID
               for p in built_in_condition_template_profiles())
    legacy = ConditionTemplateProfile(
        profile_id=ATTENTIONAL_BLINK_PROFILE_ID, display_name="Old image pairs",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    with pytest.raises(ValueError, match="no longer supported"):
        build_starter_project(
            "Image pairs", experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
            condition_template_profile=legacy,
        )


def test_bursts_are_balanced_shuffled_and_seeded_with_independent_target_draws(study):
    first = compile_session_plan(study, refresh_hz=60, random_seed=47)
    again = compile_session_plan(study, refresh_hz=60, random_seed=47)
    different = compile_session_plan(study, refresh_hz=60, random_seed=48)
    assert first == again
    entries = first.ordered_entries()
    order = [entry.condition_id for entry in entries]
    assert order != [entry.condition_id for entry in different.ordered_entries()]
    assert Counter(order) == {condition.condition_id: 24 for condition in study.conditions}
    assert any(left == right for left, right in zip(order, order[1:], strict=False))
    assert [entry.global_order_index for entry in entries] == list(range(72))
    assert len({entry.run_id for entry in entries}) == 72
    for condition in study.conditions:
        condition_entries = [
            entry for entry in entries if entry.condition_id == condition.condition_id
        ]
        assert sum(entry.run_spec.display.total_frames / 60 for entry in condition_entries) == 120
        targets = {tuple(event.text for event in entry.run_spec.stimulus_sequence
                         if event.phase in ("t1", "t2")) for entry in condition_entries}
        assert len(targets) > 1
    assert all(step.questions[0].correct_text is None for step in study.task_modules[0].steps)


def test_session_wide_shuffle_keeps_first_and_last_condition_task_occurrences(study):
    study.settings.session.block_count = 3
    for task_id, occurrence in (("first-note", TaskOccurrence.FIRST_OCCURRENCE),
                                ("last-note", TaskOccurrence.LAST_OCCURRENCE)):
        study.task_modules.append(TaskModule(
            task_id=task_id, name=task_id,
            steps=[TaskStep(step_id="note", kind=TaskStepKind.INSTRUCTION,
                            text="Ready", continue_key="space")],
        ))
        for condition in study.conditions:
            condition.pre_task_bindings.append(TaskBinding(task_id=task_id, occurrence=occurrence))
    plan = compile_session_plan(study, refresh_hz=60, random_seed=47)
    for condition in study.conditions:
        entries = [entry for entry in plan.ordered_entries()
                   if entry.condition_id == condition.condition_id]
        assert [[task.task_id for task in entry.pre_tasks] for entry in entries] == [
            ["first-note"], [], ["last-note"],
        ]


@pytest.mark.parametrize("bursts", [1, 20, 24, 30])
def test_burst_count_edit_controls_per_soa_exposure_and_survives_config(study, tmp_path, bursts):
    document = _Document(study, tmp_path)
    document.apply_attentional_blink_stream_design(
        *[source.words for source in study.stimulus_sets],
        {condition.condition_id: condition.attentional_blink.soa_ms
         for condition in study.conditions},
        t1_color="#00FF00", t2_color="#FFFFFF", bursts_per_soa=bursts,
    )
    config = export_project_config(document._project, project_root=None)
    restored = create_project_from_config(tmp_path, config).project
    assert restored.settings.session.block_count == bursts
    assert restored.settings.session.randomize_across_blocks
    plan = compile_session_plan(restored, refresh_hz=60, random_seed=47)
    assert plan.total_runs == bursts * 3
    assert Counter(entry.condition_id for entry in plan.ordered_entries()) == {
        condition.condition_id: bursts for condition in study.conditions
    }


@pytest.mark.parametrize("mutation", ["cycles", "duration", "missing_answer"])
def test_recall_compilation_rejects_ambiguous_targets_or_incomplete_answer_options(study, mutation):
    if mutation == "cycles":
        study.conditions[0].oddball_cycle_repeats_per_sequence = 2
    elif mutation == "duration":
        study.settings.protocol.oddball_every_n = 60
    else:
        question = study.task_modules[0].steps[0].questions[0]
        study.task_modules[0].steps[0].questions[0] = TaskQuestion(
            question_id=question.question_id, kind=TaskQuestionKind.SINGLE_CHOICE,
            prompt=question.prompt, options=[TaskOption(option_id="unsure", label="Unsure")],
        )
    with pytest.raises(CompileError, match="one five-second burst|single-choice option"):
        compile_session_plan(study, refresh_hz=60, random_seed=47)


def test_saved_choice_recall_stays_scored_and_every_burst_requires_space(study):
    study.settings.session.block_count = 2
    for step in study.task_modules[0].steps:
        question = step.questions[0]
        step.questions = [TaskQuestion(
            question_id=question.question_id, kind=TaskQuestionKind.SINGLE_CHOICE,
            prompt=question.prompt,
            options=[TaskOption(option_id=digit, label=digit) for digit in "0123456789"],
        )]
    study.task_modules.append(TaskModule(
        task_id="old-start-note", name="Old start note",
        steps=[TaskStep(step_id="ready", kind=TaskStepKind.INSTRUCTION,
                        text="Ready", continue_key="return")],
    ))
    for condition in study.conditions:
        condition.pre_task_bindings = [TaskBinding(
            task_id="old-start-note", replaces_condition_start_gate=True,
        )]
    plan = compile_session_plan(study, refresh_hz=60, random_seed=47)
    assert all(entry.show_condition_start_gate for entry in plan.ordered_entries())
    for entry in plan.ordered_entries():
        targets = {event.phase: event.text for event in entry.run_spec.stimulus_sequence
                   if event.phase in ("t1", "t2")}
        for step, phase in zip(entry.post_tasks[0].steps, ("t1", "t2"), strict=True):
            assert [option.option_id for option in step.questions[0].options if option.correct] == [
                targets[phase]
            ]


def test_study_saved_and_config_imported_without_character_loss(tmp_path):
    scaffold = create_project(
        tmp_path, "AB", experiment_category=ExperimentCategory.ATTENTIONAL_BLINK
    )
    restored = load_project_file(scaffold.project_root / "project.json")
    assert restored == scaffold.project
    assert not restored.settings.fixation_task.show_cross
    config = export_project_config(restored, project_root=scaffold.project_root)
    assert config.schema_version == "1.3.0"
    imported = create_project_from_config(tmp_path, config)
    assert imported.project.conditions == restored.conditions
    assert imported.project.stimulus_sets == restored.stimulus_sets
    assert imported.project.task_modules == restored.task_modules
    assert imported.project.settings.session == restored.settings.session


def test_shared_edit_updates_all_conditions_atomically_and_round_trips(study, tmp_path):
    document = _Document(study, tmp_path)
    intervals = {c.condition_id: c.attentional_blink.soa_ms for c in study.conditions}
    intervals[study.conditions[1].condition_id] = 400
    assert document.apply_attentional_blink_stream_design(
        ["A", "B"], ["2", "3"], ["4", "5"], intervals,
        t1_color="#FF0000", t2_color="#FFFFFF",
    )
    assert document.replacements == 1
    assert document._project.conditions[1].name == "SOA 400 ms"
    assert [s.words for s in document._project.stimulus_sets] == [
        ["A", "B"], ["2", "3"], ["4", "5"],
    ]
    assert not document.apply_attentional_blink_stream_design(
        ["A", "B"], ["2", "3"], ["4", "5"], intervals,
        t1_color="#FF0000", t2_color="#FFFFFF",
    )
    save_project_file(document._project, tmp_path / "project.json")
    assert load_project_file(tmp_path / "project.json") == document._project


@pytest.mark.parametrize("rate", [10.0, 12.0, 20.0])
def test_shared_rate_and_soa_edit_persists_exact_compiled_timing(study, tmp_path, rate):
    document = _Document(study, tmp_path)
    intervals = {
        condition.condition_id: lag * 1000 / rate
        for condition, lag in zip(study.conditions, (1, 3, 5), strict=True)
    }
    assert document.apply_attentional_blink_stream_design(
        ["A", "B"], ["2", "3"], ["4", "5"], intervals,
        t1_color="#FF0000", t2_color="#FFFFFF", base_hz=rate,
    )
    assert document.replacements == 1
    assert document._project.settings.protocol.base_hz == rate
    save_project_file(document._project, tmp_path / "project.json")
    restored = load_project_file(tmp_path / "project.json")
    assert restored == document._project
    for condition in restored.conditions:
        spec = compile_run_spec(restored, condition_id=condition.condition_id, refresh_hz=60)
        assert spec.condition.base_hz == rate
        assert all(event.on_frames == 60 / rate for event in spec.stimulus_sequence)
        assert spec.display.total_frames == 300
        first_cycle = spec.stimulus_sequence
        t1 = next(event for event in first_cycle if event.phase == "t1")
        t2 = next(event for event in first_cycle if event.phase == "t2")
        assert t2.on_start_frame == 180
        assert (t2.on_start_frame - t1.on_start_frame) * 1000 / 60 == pytest.approx(
            intervals[condition.condition_id]
        )


def test_rate_only_edit_preserves_authored_soas_and_condition_tasks(study, tmp_path):
    document = _Document(study, tmp_path)
    intervals = {condition.condition_id: condition.attentional_blink.soa_ms
                 for condition in study.conditions}
    sources = [source.words for source in study.stimulus_sets]
    assert document.apply_attentional_blink_stream_design(
        *sources, intervals, t1_color="#00FF00", t2_color="#FFFFFF", base_hz=20,
    )
    for previous, updated in zip(study.conditions, document._project.conditions, strict=True):
        assert updated.attentional_blink.soa_ms == previous.attentional_blink.soa_ms
        assert updated.post_task_bindings == previous.post_task_bindings
        assert updated.attentional_blink.t2_slot_index == 60
    assert document._project.task_modules == study.task_modules
    assert document._project.stimulus_sets == study.stimulus_sets
    assert document._project.settings.protocol.base_hz == 20
    assert document._project.settings.protocol.oddball_every_n == 100


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), 7.5, 40])
def test_invalid_rate_edit_leaves_all_project_state_unchanged(study, rate):
    study.settings.display.preferred_refresh_hz = 60
    document = _Document(study, Path("unused"))
    # 7.5 Hz keeps incompatible old SOAs; 40 Hz uses valid lags but fractional frames.
    intervals = {
        condition.condition_id: (lag * 1000 / rate if rate == 40
                                 else condition.attentional_blink.soa_ms)
        for condition, lag in zip(study.conditions, (1, 3, 5), strict=True)
    }
    with pytest.raises(ValueError):
        document.apply_attentional_blink_stream_design(
            ["A", "B"], ["2", "3"], ["4", "5"], intervals,
            t1_color="#123456", t2_color="#FFFFFF", base_hz=rate,
        )
    assert document._project == study
    assert document.replacements == 0


@pytest.mark.parametrize("invalid", ["off_grid", "missing_condition", "same_targets", "bad_color"])
def test_invalid_shared_edit_does_not_mutate_project(study, invalid):
    document = _Document(study, Path("unused"))
    intervals = {c.condition_id: c.attentional_blink.soa_ms for c in study.conditions}
    if invalid == "off_grid":
        intervals[study.conditions[0].condition_id] = 250
    if invalid == "missing_condition":
        intervals.pop(study.conditions[0].condition_id)
    with pytest.raises(ValueError):
        document.apply_attentional_blink_stream_design(
            ["A", "B"], ["2"], ["2"] if invalid == "same_targets" else ["3"], intervals,
            t1_color="bad" if invalid == "bad_color" else "#FF0000", t2_color="#FFFFFF",
        )
    assert document._project == study
    assert document.replacements == 0


def test_add_duplicate_and_recreate_keep_stream_layout_and_shared_pools(study, tmp_path):
    document = _Document(study, tmp_path)
    created = document.create_condition()
    duplicate = document.duplicate_condition(created)
    assert len(document._project.stimulus_sets) == 3
    assert document.get_condition(duplicate).attentional_blink.layout == "letter_stream"
    for c in list(document._project.conditions):
        document.remove_condition(c.condition_id)
    recreated = document.create_condition()
    assert document.get_condition(recreated).attentional_blink.layout == "letter_stream"
    assert len(document._project.stimulus_sets) == 3


def test_stream_rejects_legacy_template_without_mutation(study):
    document = _Document(study, Path("unused"))
    legacy = ConditionTemplateProfile(
        profile_id=ATTENTIONAL_BLINK_PROFILE_ID, display_name="Old image pairs",
        experiment_category=ExperimentCategory.ATTENTIONAL_BLINK,
    )
    with pytest.raises(ValueError, match="no longer supported"):
        document.apply_condition_template_profile(legacy)
    assert document._project == study


@pytest.mark.parametrize("settings", [AttentionalBlinkSettings(), {"isi_ms": 50}])
def test_direct_condition_edit_cannot_change_layout(study, settings):
    document = _Document(study, Path("unused"))
    with pytest.raises(ValueError, match="layout is fixed"):
        document.update_condition(study.conditions[0].condition_id, attentional_blink=settings)
    assert document._project == study
    assert document.replacements == 0


def test_adding_after_removal_keeps_condition_and_target_markers_distinct(study):
    document = _Document(study, Path("unused"))
    document.remove_condition(study.conditions[1].condition_id)
    added = document.create_condition()
    document.duplicate_condition(added)
    markers = [c.trigger_code for c in document._project.conditions]
    assert len(set(markers)) == len(markers)
    assert not set(markers).intersection({55, 56})
