"""Study defaults and atomic document edits without a Qt application."""

from pathlib import Path

import pytest

from fpvs_studio.core.attentional_blink_presets import is_attentional_blink_stream_project
from fpvs_studio.core.compiler import compile_run_spec, compile_session_plan
from fpvs_studio.core.condition_template_profiles import (
    ATTENTIONAL_BLINK_PROFILE_ID,
    ATTENTIONAL_BLINK_STREAM_PROFILE_ID,
    built_in_condition_template_profiles,
)
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.models import AttentionalBlinkSettings, ConditionTemplateProfile
from fpvs_studio.core.project_config import create_project_from_config, export_project_config
from fpvs_studio.core.project_service import build_starter_project, create_project
from fpvs_studio.core.serialization import load_project_file, save_project_file
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


def test_new_study_has_three_shared_native_streams_and_subjective_question(study):
    assert study.schema_version == ProjectSchemaVersion.V1_5
    assert is_attentional_blink_stream_project(study)
    assert study.settings.protocol.base_hz == 10
    assert not study.settings.fixation_task.show_cross
    assert build_starter_project("Oddball").settings.fixation_task.show_cross
    assert study.settings.protocol.oddball_every_n == 20
    assert study.settings.condition_profile_id == ATTENTIONAL_BLINK_STREAM_PROFILE_ID
    assert [c.attentional_blink.soa_ms for c in study.conditions] == [100, 300, 500]
    assert len(study.stimulus_sets) == 3
    assert all(s.modality == StimulusModality.WORD and s.source_dir is None
               for s in study.stimulus_sets)
    assert all(c.isi_stimulus_set_id is None for c in study.conditions)
    assert not study.settings.fixation_task.accuracy_task_enabled
    question = study.task_modules[0].steps[0].questions[0]
    assert [option.label for option in question.options] == ["Yes", "No", "Unsure"]
    assert all(option.correct is None and option.score is None for option in question.options)
    for c in study.conditions:
        assert c.post_task_bindings[0].task_id == study.task_modules[0].task_id
        assert c.post_task_bindings[0].occurrence.value == "every_entry"
        spec = compile_run_spec(study, condition_id=c.condition_id, refresh_hz=60)
        first_cycle = spec.stimulus_sequence[:20]
        assert len(first_cycle) == 20
        assert all(e.on_frames == 6 and e.off_frames == 0 for e in first_cycle)
        t1 = next(e for e in first_cycle if e.phase == "t1")
        t2 = next(e for e in first_cycle if e.phase == "t2")
        assert (t2.on_start_frame - t1.on_start_frame) * 1000 / 60 == c.attentional_blink.soa_ms
    session = compile_session_plan(study, refresh_hz=60)
    for block in session.blocks:
        for entry in block.entries:
            assert len(entry.post_tasks) == 1
            assert entry.post_tasks[0].task_id == study.task_modules[0].task_id


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


def test_shared_edit_updates_all_conditions_atomically_and_round_trips(study, tmp_path):
    document = _Document(study, tmp_path)
    intervals = {c.condition_id: c.attentional_blink.soa_ms for c in study.conditions}
    intervals[study.conditions[1].condition_id] = 400
    assert document.apply_attentional_blink_stream_design(
        ["2", "3"], ["A", "B"], ["C", "D"], intervals,
        t1_color="#FF0000", t2_color="#FFFFFF",
    )
    assert document.replacements == 1
    assert document._project.conditions[1].name == "SOA 400 ms"
    assert [s.words for s in document._project.stimulus_sets] == [
        ["2", "3"], ["A", "B"], ["C", "D"],
    ]
    assert not document.apply_attentional_blink_stream_design(
        ["2", "3"], ["A", "B"], ["C", "D"], intervals,
        t1_color="#FF0000", t2_color="#FFFFFF",
    )
    save_project_file(document._project, tmp_path / "project.json")
    assert load_project_file(tmp_path / "project.json") == document._project


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
            ["2", "3"], ["A"], ["A"] if invalid == "same_targets" else ["B"], intervals,
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
