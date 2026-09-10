"""Assemble the default continuous digit-and-letter attentional-blink study."""

from __future__ import annotations

from fpvs_studio.core.attentional_blink_stream import DEFAULT_STREAM_SOAS
from fpvs_studio.core.enums import ExperimentCategory, ProjectSchemaVersion, StimulusModality
from fpvs_studio.core.models import (
    AttentionalBlinkStreamSettings,
    Condition,
    ProjectFile,
    StimulusSet,
)
from fpvs_studio.core.task_models import (
    TaskBinding,
    TaskModule,
    TaskOption,
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
)

DEFAULT_DIGITS = tuple("23456789")
DEFAULT_TARGET_LETTERS = tuple("ABCDEFGHJKLMNPRSTUVWXYZ")
VISIBILITY_TASK_ID = "letter-visibility"


def is_attentional_blink_stream_project(project: ProjectFile) -> bool:
    """Identify the new authoring surface without inferring layout from frequency."""
    return (
        project.experiment_category == ExperimentCategory.ATTENTIONAL_BLINK
        and (
            any(isinstance(c.attentional_blink, AttentionalBlinkStreamSettings)
                for c in project.conditions)
            or (not project.conditions and project.schema_version == ProjectSchemaVersion.V1_5)
        )
    )


def populate_attentional_blink_stream(project: ProjectFile) -> ProjectFile:
    """Populate a new project with shared pools, three SOAs, and a visibility question."""
    if project.conditions or project.stimulus_sets or project.task_modules:
        raise ValueError("The letter-stream preset can only populate a new, empty project.")
    if project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK:
        raise ValueError("The letter-stream preset requires an Attentional-Blink experiment.")
    sets = [
        StimulusSet(set_id=set_id, name=name, modality=StimulusModality.WORD, words=list(words))
        for set_id, name, words in (
            ("base-digits", "Base digits", DEFAULT_DIGITS),
            ("t1-letters", "T1 letters", DEFAULT_TARGET_LETTERS),
            ("t2-letters", "T2 letters", DEFAULT_TARGET_LETTERS),
        )
    ]
    visibility = TaskModule(
        task_id=VISIBILITY_TASK_ID,
        name="White-letter visibility",
        steps=[TaskStep(
            step_id="visibility",
            kind=TaskStepKind.QUESTIONNAIRE,
            questions=[TaskQuestion(
                question_id="white-letter-seen",
                kind=TaskQuestionKind.SINGLE_CHOICE,
                prompt="Did you notice any white letters during that sequence?",
                options=[TaskOption(option_id=key, label=label)
                         for key, label in (("yes", "Yes"), ("no", "No"), ("unsure", "Unsure"))],
            )],
        )],
    )
    defaults = project.settings.condition_defaults
    conditions = [
        Condition(
            condition_id=f"soa-{soa:g}ms",
            name=f"SOA {soa:g} ms",
            instructions=(
                "Watch the stream of numbers. Attend to both the red letter (T1) and "
                "the white letter (T2). After the sequence, report whether you noticed "
                "any white letters."
            ),
            base_stimulus_set_id="base-digits",
            oddball_stimulus_set_id="t1-letters",
            t2_stimulus_set_id="t2-letters",
            attentional_blink=AttentionalBlinkStreamSettings(soa_ms=soa),
            sequence_count=defaults.sequence_count,
            oddball_cycle_repeats_per_sequence=defaults.oddball_cycle_repeats_per_sequence,
            trigger_code=index + 1,
            order_index=index,
            post_task_bindings=[TaskBinding(task_id=VISIBILITY_TASK_ID)],
        )
        for index, soa in enumerate(DEFAULT_STREAM_SOAS)
    ]
    return project.model_copy(update={
        "schema_version": ProjectSchemaVersion.V1_5,
        "stimulus_sets": sets,
        "conditions": conditions,
        "task_modules": [visibility],
    })
