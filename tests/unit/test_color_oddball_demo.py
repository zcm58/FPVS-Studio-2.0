from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from PIL import Image
from scripts.create_color_oddball_demo import prepare_demo, write_preview_strips

from fpvs_studio.core.compiler import compile_session_plan
from fpvs_studio.core.enums import DutyCycleMode
from fpvs_studio.core.project_bundle import import_project_bundle


def test_packaged_demo_strips_match_generated_stimuli(tmp_path):
    write_preview_strips(tmp_path)
    packaged = Path(__file__).resolve().parents[2] / "src/fpvs_studio/assets/oddball-demo"
    for color in ("red", "green"):
        with Image.open(tmp_path / f"{color}.png") as generated, Image.open(
            packaged / f"{color}.png",
        ) as bundled:
            assert bundled.size == (1452, 132)
            assert bundled.mode == "RGBA"
            assert bundled.tobytes() == generated.tobytes()


def test_public_color_demo_imports_and_compiles_on_supported_displays(tmp_path):
    bundle = prepare_demo(tmp_path / "publication")
    assert bundle.stat().st_size < 1024 * 1024
    with ZipFile(bundle) as archive:
        images = [name for name in archive.namelist() if name.endswith(".png")]
        assert len(images) == 36
        for name in images:
            with archive.open(name) as source, Image.open(source) as image:
                assert image.mode == "RGB" and image.size == (256, 256)

    imported = import_project_bundle(bundle, tmp_path / "studio", library_safe=True)
    project = imported.project
    assert project.settings.protocol.base_hz == 6
    assert project.settings.protocol.oddball_every_n == 5
    assert {condition.base_stimulus_set_id for condition in project.conditions} == {"gray"}
    oddball_sets = {condition.oddball_stimulus_set_id for condition in project.conditions}
    assert oddball_sets == {"red", "green"}
    for hz in (59.94, 60, 60.02, 120, 144, 240):
        plan = compile_session_plan(project, project_root=imported.project_root, refresh_hz=hz)
        assert plan.total_runs == 6
        runs = [entry.run_spec for block in plan.blocks for entry in block.entries]
        assert Counter(run.condition.condition_id for run in runs) == {
            "red-oddballs": 3, "green-oddballs": 3,
        }
        for run in runs:
            assert run.display.duty_cycle_mode == DutyCycleMode.SINUSOIDAL
            assert run.condition.total_oddball_cycles == 48
            assert len(run.stimulus_sequence) == 240
            assert len(run.fixation_events) == 4
