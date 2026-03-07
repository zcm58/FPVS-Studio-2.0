"""Template-library tests."""

from __future__ import annotations

from fpvs_studio.core.template_library import default_template, get_template


def test_default_template_retrieval() -> None:
    template = default_template()

    assert template == get_template("fpvs_6hz_every5_v1")
    assert template.base_hz == 6.0
    assert template.oddball_every_n == 5
    assert template.oddball_hz == 1.2
    assert template.default_oddball_cycle_repeats_per_sequence == 146
