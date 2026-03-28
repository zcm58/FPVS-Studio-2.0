"""Compiled multi-condition session contracts built above single-run plans.
Core compilation turns editable session settings into ordered SessionPlan entries that reference individual RunSpec artifacts and transition metadata.
This module owns session sequencing schema only; runtime executes that plan and engines render the screens it requests."""

from __future__ import annotations

from pydantic import Field, model_validator

from fpvs_studio.core.enums import InterConditionMode, SchemaVersion
from fpvs_studio.core.models import FPVSBaseModel
from fpvs_studio.core.run_spec import RunSpec


class InterConditionTransitionSpec(FPVSBaseModel):
    """Transition behavior applied between condition runs."""

    mode: InterConditionMode
    break_seconds: float | None = Field(default=None, ge=0)
    continue_key: str | None = None

    @model_validator(mode="after")
    def validate_transition_fields(self) -> "InterConditionTransitionSpec":
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

    @model_validator(mode="after")
    def validate_consistency(self) -> "SessionEntry":
        if self.run_id != self.run_spec.run_id:
            raise ValueError("SessionEntry.run_id must match run_spec.run_id.")
        if self.condition_id != self.run_spec.condition.condition_id:
            raise ValueError("SessionEntry.condition_id must match run_spec.condition.condition_id.")
        if self.condition_name != self.run_spec.condition.name:
            raise ValueError("SessionEntry.condition_name must match run_spec.condition.name.")
        return self


class SessionBlock(FPVSBaseModel):
    """One randomized block inside a session plan."""

    block_index: int = Field(ge=0)
    condition_order: list[str] = Field(default_factory=list)
    entries: list[SessionEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_entries(self) -> "SessionBlock":
        entry_order = [entry.condition_id for entry in self.entries]
        if self.condition_order != entry_order:
            raise ValueError("SessionBlock.condition_order must match the ordered entry condition ids.")
        return self


class SessionPlan(FPVSBaseModel):
    """Executable multi-condition session plan compiled from one project."""

    schema_version: str = SchemaVersion.V1.value
    session_id: str
    project_id: str
    project_name: str
    random_seed: int = Field(ge=0)
    refresh_hz: float = Field(gt=0)
    block_count: int = Field(ge=1)
    transition: InterConditionTransitionSpec
    blocks: list[SessionBlock] = Field(default_factory=list)
    total_runs: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_totals(self) -> "SessionPlan":
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
