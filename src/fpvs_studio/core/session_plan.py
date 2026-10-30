"""Compiled multi-condition session contracts built above single-run plans. Core
compilation turns editable session settings into ordered SessionPlan entries that
reference individual RunSpec artifacts and transition metadata. This module owns session
sequencing schema only; runtime executes that plan and engines render the screens it
requests."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    StrictInt,
    model_serializer,
    model_validator,
)

from fpvs_studio.core.enums import InterConditionMode, SchemaVersion
from fpvs_studio.core.models import FPVSBaseModel, RandomizationAlgorithmVersion, RandomizationSeeds
from fpvs_studio.core.run_spec import RunSpec
from fpvs_studio.core.task_models import TaskModuleSpec, task_requires_text_alignment_schema


class InterConditionTransitionSpec(FPVSBaseModel):
    """Transition behavior applied between condition runs."""

    mode: InterConditionMode
    break_seconds: float | None = Field(default=None, ge=0)
    continue_key: str | None = None

    @model_validator(mode="after")
    def validate_transition_fields(self) -> InterConditionTransitionSpec:
        if self.mode == InterConditionMode.FIXED_BREAK and self.break_seconds is None:
            raise ValueError("break_seconds is required when mode is 'fixed_break'.")
        if self.mode == InterConditionMode.MANUAL_CONTINUE:
            if self.continue_key is None or not self.continue_key.strip():
                raise ValueError("continue_key is required when mode is 'manual_continue'.")
        return self


class SessionEntry(FPVSBaseModel):
    """One executable run occurrence inside a compiled session."""

    global_order_index: int = Field(ge=0)
    block_index: int = Field(ge=0)
    index_within_block: int = Field(ge=0)
    condition_id: str
    condition_name: str
    run_id: str
    run_spec: RunSpec
    pre_tasks: list[TaskModuleSpec] = Field(default_factory=list)
    post_tasks: list[TaskModuleSpec] = Field(default_factory=list)
    show_condition_start_gate: bool = True
    condition_presentation_index: StrictInt | None = Field(default=None, ge=1)
    condition_presentation_count: StrictInt | None = Field(default=None, ge=1)

    @model_serializer(mode="wrap")
    def serialize_optional_presentations(
        self, handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.condition_presentation_index is None:
            payload.pop("condition_presentation_index", None)
        if self.condition_presentation_count is None:
            payload.pop("condition_presentation_count", None)
        return payload

    @model_validator(mode="after")
    def validate_consistency(self) -> SessionEntry:
        if ((self.condition_presentation_index is None)
                != (self.condition_presentation_count is None)):
            raise ValueError("Condition presentation index and count must be supplied together.")
        if (self.condition_presentation_index is not None
                and self.condition_presentation_count is not None
                and self.condition_presentation_index > self.condition_presentation_count):
            raise ValueError("Condition presentation index may not exceed its total count.")
        if (self.run_spec.randomization is not None and self.condition_presentation_index
                != self.run_spec.randomization.condition_presentation_index):
            raise ValueError("Session and run presentation indices must match.")
        if self.run_id != self.run_spec.run_id:
            raise ValueError("SessionEntry.run_id must match run_spec.run_id.")
        if self.condition_id != self.run_spec.condition.condition_id:
            raise ValueError(
                "SessionEntry.condition_id must match run_spec.condition.condition_id."
            )
        if self.condition_name != self.run_spec.condition.name:
            raise ValueError("SessionEntry.condition_name must match run_spec.condition.name.")
        return self


class SessionBlock(FPVSBaseModel):
    """One randomized block inside a session plan."""

    block_index: int = Field(ge=0)
    condition_order: list[str] = Field(default_factory=list)
    entries: list[SessionEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entries(self) -> SessionBlock:
        entry_order = [entry.condition_id for entry in self.entries]
        if self.condition_order != entry_order:
            raise ValueError(
                "SessionBlock.condition_order must match the ordered entry condition ids."
            )
        return self


class SessionPlan(FPVSBaseModel):
    """Executable multi-condition session plan compiled from one project."""

    schema_version: str = SchemaVersion.V1_2.value
    session_id: str
    project_id: str
    project_name: str
    random_seed: int = Field(ge=0)
    refresh_hz: float = Field(gt=0)
    block_count: int = Field(ge=1)
    transition: InterConditionTransitionSpec
    blocks: list[SessionBlock] = Field(default_factory=list)
    total_runs: int = Field(ge=0)
    authored_task_flow: bool | None = None
    ordering_policy: Literal["pooled_no_adjacent", "saved_no_adjacent"] | None = None
    randomization_mode: Literal["fixed", "new"] | None = None
    randomization_seeds: RandomizationSeeds | None = None
    randomization_algorithm_version: RandomizationAlgorithmVersion | None = None

    @model_serializer(mode="wrap")
    def serialize_optional_flow(
        self, handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = handler(self)
        if self.authored_task_flow is None:
            payload.pop("authored_task_flow", None)
        if self.ordering_policy is None:
            payload.pop("ordering_policy", None)
        for name in (
            "randomization_mode", "randomization_seeds", "randomization_algorithm_version",
        ):
            if getattr(self, name) is None:
                payload.pop(name, None)
        return payload

    @model_validator(mode="after")
    def validate_totals(self) -> SessionPlan:
        entries = [entry for block in self.blocks for entry in block.entries]
        if self.schema_version == "1.8.0" and self.randomization_mode != "fixed":
            raise ValueError("Saved condition ordering requires fixed randomization mode.")
        if self.schema_version in {"1.7.0", "1.8.0"}:
            if (self.randomization_mode is None or self.randomization_seeds is None
                    or self.randomization_algorithm_version is None):
                raise ValueError(
                    "Independent sessions require the resolved seed triplet and policy."
                )
            if (type(self.randomization_algorithm_version) is not int
                    or self.randomization_algorithm_version != 1):
                raise ValueError("Independent randomization algorithm version must be integer 1.")
            RandomizationSeeds.model_validate(self.randomization_seeds.model_dump())
            if self.random_seed != self.randomization_seeds.condition_order_seed:
                raise ValueError("Session seed must match the resolved condition-order seed.")
            if any(entry.run_spec.randomization is None
                   or entry.run_spec.randomization.mode != self.randomization_mode
                   or entry.run_spec.randomization.seeds != self.randomization_seeds
                   or entry.run_spec.randomization.algorithm_version
                   != self.randomization_algorithm_version for entry in entries):
                raise ValueError("Session and run randomization provenance must match.")
        elif (self.randomization_mode is not None or self.randomization_seeds is not None
              or self.randomization_algorithm_version is not None
              or any(entry.run_spec.randomization is not None for entry in entries)):
            raise ValueError("Independent randomization requires SessionPlan schema 1.7.0.")
        has_presentations = any(entry.condition_presentation_index is not None for entry in entries)
        if self.schema_version in {"1.6.0", "1.7.0", "1.8.0"}:
            expected_policy = ("saved_no_adjacent" if self.schema_version == "1.8.0"
                               else "pooled_no_adjacent")
            if self.ordering_policy != expected_policy or any(
                entry.condition_presentation_index is None for entry in entries
            ):
                raise ValueError(
                    "Pooled sessions require an ordering policy and presentation indices."
                )
        elif self.ordering_policy is not None or has_presentations:
            raise ValueError("Presentation ordering metadata requires SessionPlan schema 1.6.0.")
        if self.authored_task_flow is not None and self.schema_version not in {
            "1.3.0", "1.4.0", "1.5.0", "1.6.0", "1.7.0", "1.8.0",
        }:
            raise ValueError("Authored task session flow requires SessionPlan schema 1.3.0.")
        if any(entry.run_spec.scene_stream is not None
               and entry.run_spec.scene_stream.is_catch_trial
               for block in self.blocks for entry in block.entries):
            if self.schema_version not in {"1.4.0", "1.5.0", "1.6.0", "1.7.0", "1.8.0"}:
                raise ValueError("Catch trials require SessionPlan schema 1.4.0.")
        if any(task_requires_text_alignment_schema(task)
               for block in self.blocks for entry in block.entries
               for task in [*entry.pre_tasks, *entry.post_tasks]):
            if self.schema_version not in {"1.5.0", "1.6.0", "1.7.0", "1.8.0"}:
                raise ValueError("Task text alignment requires SessionPlan schema 1.5.0.")
        if self.block_count != len(self.blocks):
            raise ValueError("block_count must match the number of blocks.")
        total_entries = sum(len(block.entries) for block in self.blocks)
        if self.total_runs != total_entries:
            raise ValueError("total_runs must match the number of session entries.")
        return self

    def ordered_entries(self) -> list[SessionEntry]:
        """Return session entries in execution order."""

        return [
            entry
            for block in sorted(self.blocks, key=lambda item: item.block_index)
            for entry in sorted(block.entries, key=lambda item: item.index_within_block)
        ]
