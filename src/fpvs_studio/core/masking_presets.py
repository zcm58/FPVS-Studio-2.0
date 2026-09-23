"""Editable native masking workflows; source media remain explicit project inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fpvs_studio.core.condition_modifiers import ConditionModifier, ModifierDefinition
from fpvs_studio.core.enums import PresentationUnit
from fpvs_studio.core.masking import MaskingSettings
from fpvs_studio.core.scene_models import SceneVisual
from fpvs_studio.core.task_models import (
    ConditionModifierKind,
    TaskDisplayItem,
    TaskFontFamily,
    TaskItemModality,
    TaskLayoutMode,
    TaskModule,
    TaskStep,
    TaskStepKind,
)

if TYPE_CHECKING:
    from fpvs_studio.core.models import ProjectFile

MASKING_COLORS = {
    "red": (0.97, 0.36, 0.37),
    "green": (0.23, 0.64, 0.39),
    "blue": (0.23, 0.57, 0.98),
    "yellow": (0.67, 0.56, 0.09),
}
MASKING_LETTERS = ("C", "E", "F", "H", "K", "M", "N", "P", "R", "T", "V", "W", "X", "A")
MASKING_NUMBERS = ("3", "5", "7", "9")
MASKING_INSTRUCTIONS = (
    "Instructions:\nSeveral images will be shown to you in rapid succession. \n"
    "However, all you have to do is fixate on the red cross in the middle of the screen.\n"
    "Please try not to blink during the stimuli presentation\n\n"
    "Press space when you're ready to begin"
)
MASKING_BREAK = (
    "Take a break. As long as you need.\n\nReady for the next trial?\n\nPress space to go again\n"
)


def apply_masking_timing_defaults(project: ProjectFile) -> ProjectFile:
    """Explicit authoring action; never invoked merely by opening a modifier."""
    from fpvs_studio.core.enums import DutyCycleMode
    from fpvs_studio.core.masking import condition_masking
    from fpvs_studio.core.models import FixationTaskSettings

    draft = project.model_copy(deep=True)
    draft.settings.protocol.base_hz = 5
    draft.settings.protocol.oddball_every_n = 5
    draft.settings.session.block_count = 3
    draft.settings.session.randomize_across_blocks = False
    draft.settings.fixation_task = FixationTaskSettings(
        show_cross=False,
        enabled=False,
        accuracy_task_enabled=False,
        participant_tutorial_enabled=False,
    )
    if draft.settings.display.preferred_refresh_hz is None:
        draft.settings.display.preferred_refresh_hz = 60
    for condition in draft.conditions:
        if condition_masking(draft, condition) is not None:
            condition.sequence_count = 1
            condition.oddball_cycle_repeats_per_sequence = 40
            condition.duty_cycle_mode = DutyCycleMode.CONTINUOUS
    return type(project).model_validate(draft.model_dump())


def _message(
    step_id: str,
    text: str,
    *,
    seconds: float | None = None,
    cross: bool = False,
    font: TaskFontFamily = TaskFontFamily.OPEN_SANS,
) -> TaskStep:
    return TaskStep(
        step_id=step_id,
        kind=TaskStepKind.INSTRUCTION,
        font_family=font,
        layout_mode=TaskLayoutMode.EXACT,
        show_footer=False,
        degree_geometry="linear",
        continue_key="space" if seconds is None else None,
        duration_seconds=seconds,
        items=[
            TaskDisplayItem(
                item_id=step_id,
                modality=TaskItemModality.TEXT,
                text=text,
                width=1,
                height=0.025 if cross else 0.05,
                unit=PresentationUnit.WINDOW_HEIGHT_FRACTION,
                color_rgb=(1.0, -1.0, -1.0) if cross else (1.0, 1.0, 1.0),
            )
        ],
    )


def _rating(step_id: str, prompt: str, labels: list[str]) -> TaskStep:
    return TaskStep(
        step_id=step_id,
        kind=TaskStepKind.CHOICE_GRID,
        layout_mode=TaskLayoutMode.EXACT,
        text=prompt,
        prompt_y=6,
        prompt_height=1.5,
        prompt_width=30,
        degree_geometry="linear",
        show_footer=False,
        require_response=True,
        items=[
            TaskDisplayItem(
                item_id=f"{step_id}-{index + 1}",
                modality=TaskItemModality.TEXT,
                text=label,
                x=0,
                y=2 - 2 * index,
                width=15,
                height=1,
                selectable=True,
            )
            for index, label in enumerate(labels)
        ],
    )


def create_masking_modifier(
    *,
    variant: Literal["color", "faces", "number"] = "color",
    modifier_id: str = "masking",
    name: str | None = None,
    soa_ms: float = 50.0,
) -> ModifierDefinition:
    """Create a reusable, fully editable workflow; Faces requires imported image pools."""
    settings = MaskingSettings(variant=variant, soa_ms=soa_ms)
    settings.fixation_visual = SceneVisual(
        visual_id="masking-fixation",
        kind="text",
        text="+",
        units="height",
        text_height=0.025,
        font="Open Sans",
        rgb=(1, -1, -1),
    )
    if variant == "color":
        settings.base_visuals = [
            SceneVisual(
                visual_id="gray-base",
                kind="circle",
                units="deg",
                size=(5, 5),
                rgb=(0.57, 0.57, 0.57),
                line_rgb=(0.57, 0.57, 0.57),
            )
        ]
        settings.mask_visuals = [
            settings.base_visuals[0].model_copy(
                update={"visual_id": "gray-mask"},
                deep=True,
            )
        ]
        settings.target_visuals = [
            SceneVisual(
                visual_id=color,
                kind="circle",
                units="deg",
                size=(5, 5),
                rgb=rgb,
                line_rgb=rgb,
            )
            for color, rgb in MASKING_COLORS.items()
        ]
        choices = [
            TaskDisplayItem(
                item_id=color,
                modality=TaskItemModality.CIRCLE,
                x=x,
                y=y,
                width=5,
                height=5,
                color_rgb=rgb,
                line_color_rgb=(1, 1, 1),
                selectable=True,
            )
            for (color, rgb), (x, y) in zip(
                MASKING_COLORS.items(),
                ((-5, 5), (5, 5), (-5, -5), (5, -5)),
                strict=True,
            )
        ]
        prompt, prompt_y, prompt_height, prompt_width = (
            "What target color did you see? ",
            10,
            2.5,
            40,
        )
    else:
        if variant == "number":
            settings.base_visuals = [
                SceneVisual(
                    visual_id=f"letter-{letter.lower()}",
                    kind="text",
                    text=letter,
                    units="deg",
                    text_height=5,
                    font="Arial Black",
                    rgb=(0.57, 0.57, 0.57),
                )
                for letter in MASKING_LETTERS
            ]
            settings.target_visuals = [
                SceneVisual(
                    visual_id=f"number-{number}",
                    kind="text",
                    text=number,
                    units="deg",
                    text_height=5,
                    font="Arial Black",
                    rgb=(0.57, 0.57, 0.57),
                )
                for number in MASKING_NUMBERS
            ]
            settings.base_overlays = [
                SceneVisual(
                    visual_id="letter-backdrop",
                    kind="rectangle",
                    units="deg",
                    position=(0, -0.5),
                    size=(5, 5),
                    rgb=(0.4, 0.4, 0.4),
                    line_rgb=(-1, -1, -1),
                )
            ]
            labels = list(MASKING_NUMBERS)
            ids = [f"number-{number}" for number in labels]
            y_top, text_height = 3, 3
            prompt = "What number did you see? "
        else:
            labels = ["Angry", "Happy", "Fearful", "Sad"]
            ids = [label.lower() for label in labels]
            y_top, text_height = 1, 2
            prompt = "What facial expression did you see? "
        choices = [
            TaskDisplayItem(
                item_id=item_id,
                modality=TaskItemModality.TEXT,
                text=label,
                x=x,
                y=y,
                width=15,
                height=text_height,
                selectable=True,
            )
            for item_id, label, (x, y) in zip(
                ids,
                labels,
                ((-5, y_top), (5, y_top), (-5, -5), (5, -5)),
                strict=True,
            )
        ]
        prompt_y, prompt_height, prompt_width = 6, 2, 30
    settings.target_answers = {
        visual.visual_id: visual.visual_id for visual in settings.target_visuals
    }
    before = TaskModule(
        task_id=f"{modifier_id}-before",
        name="Instructions and fixation",
        steps=[
            _message("masking-instructions", MASKING_INSTRUCTIONS),
            _message("masking-start-fixation", "+", seconds=2, cross=True),
        ],
    )
    after = TaskModule(
        task_id=f"{modifier_id}-after",
        name="Visibility, identity and frequency",
        steps=[
            _rating(
                "masking-pas",
                "How clearly did you see the brief target stimulus during the sequence?",
                [
                    "1 — No experience",
                    "2 — A vague glimpse",
                    "3 — An almost clear experience",
                    "4 — A clear experience",
                ],
            ),
            TaskStep(
                step_id="masking-identification",
                kind=TaskStepKind.CHOICE_GRID,
                layout_mode=TaskLayoutMode.EXACT,
                text=prompt,
                prompt_y=prompt_y,
                prompt_height=prompt_height,
                prompt_width=prompt_width,
                degree_geometry="linear",
                show_footer=False,
                require_response=True,
                randomize_positions=True,
                items=choices,
            ),
            _rating(
                "masking-frequency",
                "How often did you see the brief target stimulus during the sequence?",
                [
                    "1 — Never",
                    "2 — Rarely",
                    "3 — Sometime",
                    "4 — Often",
                    "5 — Almost always",
                ],
            ),
            _message("masking-break", MASKING_BREAK, font=TaskFontFamily.ARIAL),
            _message("masking-break-fixation", "+", seconds=2, cross=True),
        ],
    )
    thanks = TaskModule(
        task_id=f"{modifier_id}-thanks",
        name="Completion",
        steps=[
            _message("masking-thanks", "ALL done!\n\nThanks for your time! ", seconds=1),
        ],
    )
    return ModifierDefinition(
        modifier=ConditionModifier(
            modifier_id=modifier_id,
            name=name or f"Masking — {variant.title()}",
            description="Brief repeated target, delayed mask and immediate visibility questions.",
            kind=ConditionModifierKind.MASKING,
            pre_task_ids=[before.task_id],
            post_task_ids=[after.task_id, thanks.task_id],
            masking=settings,
        ),
        task_modules=[before, after, thanks],
    )
