"""Built-in FPVS protocol templates."""

from __future__ import annotations

from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.models import TemplateLibraryRecord, TemplateSpec

DEFAULT_TEMPLATE_ID = "fpvs_6hz_every5_v1"

_TEMPLATES = TemplateLibraryRecord(
    templates={
        DEFAULT_TEMPLATE_ID: TemplateSpec(
            template_id=DEFAULT_TEMPLATE_ID,
            display_name="FPVS 6 Hz Every 5 v1",
            description="Fixed 6.0 Hz base stream with an oddball every 5th image.",
            base_hz=6.0,
            oddball_every_n=5,
            oddball_hz=1.2,
            supported_duty_cycle_modes=(
                DutyCycleMode.CONTINUOUS,
                DutyCycleMode.BLANK_50,
            ),
            default_oddball_cycle_repeats_per_sequence=146,
        )
    }
)


def list_templates() -> list[TemplateSpec]:
    """Return all built-in templates."""

    return list(_TEMPLATES.templates.values())


def get_template(template_id: str) -> TemplateSpec:
    """Return a built-in template by id."""

    try:
        return _TEMPLATES.templates[template_id]
    except KeyError as exc:
        raise KeyError(f"Unknown template_id '{template_id}'.") from exc


def default_template() -> TemplateSpec:
    """Return the single built-in v1 template."""

    return get_template(DEFAULT_TEMPLATE_ID)
