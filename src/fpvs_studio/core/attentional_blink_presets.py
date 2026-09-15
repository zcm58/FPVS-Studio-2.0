"""Assemble the default five-second attentional-blink digit-recall study."""

from __future__ import annotations

from fpvs_studio.core.attentional_blink_stream import (
    DEFAULT_STREAM_SOAS,
    attentional_blink_burst_grid,
)
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
    TaskQuestion,
    TaskQuestionKind,
    TaskStep,
    TaskStepKind,
    TaskSubmissionMode,
)

DEFAULT_DIGITS = tuple("23456789")
DEFAULT_LETTERS = tuple("ABCDEFGHJKLMNPRSTUVWXYZ")
RECALL_TASK_ID = "ab-recall"
RECALL_QUESTION_PHASES = {"t1-recall": "t1", "t2-recall": "t2"}
DEFAULT_BURSTS_PER_SOA = 24


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


def create_attentional_blink_recall_task() -> TaskModule:
    """Build typed recall questions whose answer keys resolve from each compiled burst."""
    return TaskModule(
        task_id=RECALL_TASK_ID,
        name="Target number recall",
        steps=[TaskStep(
            step_id=question_id,
            kind=TaskStepKind.QUESTIONNAIRE,
            text="Type the number, or type unsure. Press Enter or click Next to continue.",
            submission_mode=TaskSubmissionMode.EXPLICIT,
            submit_label="Next",
            questions=[TaskQuestion(
                question_id=question_id,
                kind=TaskQuestionKind.SHORT_TEXT,
                prompt=prompt,
                required=True,
                max_text_length=32,
            )],
        ) for question_id, prompt in (
            ("t1-recall", "What was the green number?"),
            ("t2-recall", "What was the second number?"),
        )],
    )


def populate_attentional_blink_stream(project: ProjectFile) -> ProjectFile:
    """Populate a new project with shuffled bursts and separate target-recall questions."""
    if project.conditions or project.stimulus_sets or project.task_modules:
        raise ValueError("The letter-stream preset can only populate a new, empty project.")
    if project.experiment_category != ExperimentCategory.ATTENTIONAL_BLINK:
        raise ValueError("The letter-stream preset requires an Attentional-Blink experiment.")
    sets = [
        StimulusSet(set_id=set_id, name=name, modality=StimulusModality.WORD, words=list(words))
        for set_id, name, words in (
            ("base-letters", "Base letters", DEFAULT_LETTERS),
            ("t1-digits", "T1 digits", DEFAULT_DIGITS),
            ("t2-digits", "T2 digits", DEFAULT_DIGITS),
        )
    ]
    settings = project.settings.model_copy(deep=True)
    cycle_slots, t2_slot_index = attentional_blink_burst_grid(settings.protocol.base_hz)
    settings.protocol.oddball_every_n = cycle_slots
    settings.condition_defaults.sequence_count = 1
    settings.condition_defaults.oddball_cycle_repeats_per_sequence = 1
    settings.session.block_count = DEFAULT_BURSTS_PER_SOA
    settings.session.randomize_across_blocks = True
    settings.presentation.pre_stream_fixation_seconds = 0.0
    conditions = [
        Condition(
            condition_id=f"soa-{soa:g}ms",
            name=f"SOA {soa:g} ms",
            instructions=(
                "Watch the stream of white letters. Remember the green number (T1) "
                "and the later white number (T2). After each five-second burst, "
                "type each number separately and press Enter or click Next. "
                "Press Space when you are ready to begin each burst."
            ),
            base_stimulus_set_id="base-letters",
            oddball_stimulus_set_id="t1-digits",
            t2_stimulus_set_id="t2-digits",
            attentional_blink=AttentionalBlinkStreamSettings(
                soa_ms=soa, t2_slot_index=t2_slot_index, t1_color="#00FF00",
            ),
            sequence_count=1,
            oddball_cycle_repeats_per_sequence=1,
            trigger_code=int(soa / 100),
            order_index=index,
            post_task_bindings=[TaskBinding(task_id=RECALL_TASK_ID)],
        )
        for index, soa in enumerate(DEFAULT_STREAM_SOAS)
    ]
    return project.model_copy(update={
        "schema_version": ProjectSchemaVersion.V1_5,
        "settings": settings,
        "stimulus_sets": sets,
        "conditions": conditions,
        "task_modules": [create_attentional_blink_recall_task()],
    })
