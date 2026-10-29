"""Built-in acquisition declarations shared by config and execution exports.

These are selected hardware definitions, never observations of a connected device.
Transport adapters and recording qualification remain runtime responsibilities.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LabelMappingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["declared"] = "declared"
    reference: str = Field(min_length=1)


class AcquisitionProfile(BaseModel):
    """Versioned Toolbox identity and an explicitly declared channel mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    montage_id: str = Field(min_length=1)
    montage_version: str = Field(min_length=1)
    event_decoder_id: str = Field(min_length=1)
    event_decoder_version: str = Field(min_length=1)
    reference_policy: str = Field(min_length=1)
    source_to_canonical: dict[str, str] | None = None
    label_mapping_evidence: LabelMappingEvidence | None = None


class RecordingHardwareDefinition(BaseModel):
    """One selectable hardware declaration, independent of its adapter code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    recording_backend: Literal[
        "serial", "biosemi_active_three", "brainproducts_triggerbox", "brainproducts_parallel",
        "unicorn_udp"
    ]
    acquisition_profile: AcquisitionProfile | None = None


_HARDWARE = (
    RecordingHardwareDefinition(
        label="BioSemi ActiveTwo (64 channels)", recording_backend="serial",
        acquisition_profile=AcquisitionProfile(
            id="biosemi_active_two_64", version="1.0", montage_id="biosemi64",
            montage_version="1.0", event_decoder_id="biosemi_edge",
            event_decoder_version="1.0", reference_policy="biosemi_exg_pair_then_average",
        ),
    ),
    RecordingHardwareDefinition(
        label="BioSemi ActiveThree", recording_backend="biosemi_active_three",
    ),
    RecordingHardwareDefinition(
        label="Brain Products / BrainVision (TriggerBox/Plus)",
        recording_backend="brainproducts_triggerbox",
    ),
    RecordingHardwareDefinition(
        label="Brain Products / BrainVision (Parallel port)",
        recording_backend="brainproducts_parallel",
    ),
    RecordingHardwareDefinition(
        label="Unicorn Hybrid Black (factory 8 channels)", recording_backend="unicorn_udp",
        acquisition_profile=AcquisitionProfile(
            id="unicorn_hybrid_black", version="1.0", montage_id="unicorn8",
            montage_version="1.0", event_decoder_id="unicorn_sample",
            event_decoder_version="1.0", reference_policy="average_scalp",
            source_to_canonical=dict(zip(
                (f"EEG {index}" for index in range(1, 9)),
                ("Fz", "C3", "Cz", "C4", "Pz", "PO7", "Oz", "PO8"), strict=True,
            )),
            label_mapping_evidence=LabelMappingEvidence(reference=(
                "Manufacturer factory numbered cap layout; declared factory wiring, "
                "not measured hardware qualification"
            )),
        ),
    ),
)


def recording_hardware_definitions() -> tuple[RecordingHardwareDefinition, ...]:
    """Return independent definitions so callers cannot change registry mappings."""

    return tuple(item.model_copy(deep=True) for item in _HARDWARE)


def acquisition_profile_for_recording(recording_backend: str) -> AcquisitionProfile | None:
    """Resolve the authored recording choice; unsupported choices fail explicitly."""

    for item in _HARDWARE:
        if item.recording_backend == recording_backend:
            profile = item.acquisition_profile
            return profile.model_copy(deep=True) if profile is not None else None
    raise ValueError(f"Unsupported recording hardware choice: {recording_backend}")
