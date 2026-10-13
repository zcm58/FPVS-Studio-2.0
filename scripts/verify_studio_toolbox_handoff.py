"""Create real completed Studio exports with synthetic presentation and marker I/O.

Run from the repository with its Python environment. This uses no Qt, acquisition
hardware, sockets, credentials or HTTP. Outputs are isolated beneath a fresh run ID.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from tests.unit.runtime_launcher_helpers import StubEngine  # noqa: E402

from fpvs_studio.core.compiler import compile_session_plan  # noqa: E402
from fpvs_studio.core.data_sharing import SharingProfile, protocol_fingerprint  # noqa: E402
from fpvs_studio.core.enums import StimulusModality  # noqa: E402
from fpvs_studio.core.models import (  # noqa: E402
    Condition,
    FixationTaskSettings,
    ProjectFile,
    ProjectMeta,
    ProjectRecordingSettings,
    ProjectSettings,
    StimulusSet,
)
from fpvs_studio.core.project_config import (  # noqa: E402
    export_project_config,
    read_project_config,
)
from fpvs_studio.core.serialization import atomic_text_write, save_project_file  # noqa: E402
from fpvs_studio.runtime.data_sharing import CaptureIntent, build_session_report  # noqa: E402
from fpvs_studio.runtime.run_worker import RuntimeWorker  # noqa: E402
from fpvs_studio.triggers.null_backend import NullBackend  # noqa: E402

STUDY_ID = "7cfa432a-3a31-4b46-b699-510ca41f0594"
EXPERIMENT_ID = "synthetic-fpvs-integration"
EXPERIMENT_VERSION = "1.0"


class InMemoryMarkers(NullBackend):
    """Preserve the chosen transport identity without accessing any transport."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def backend_name(self) -> str:
        return self._name

    @property
    def emits_external_markers(self) -> bool:
        return True


def create_acceptance_artifacts(output_base: Path) -> dict[str, object]:
    output = output_base.resolve() / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for backend in ("serial", "unicorn_udp"):
        root = output / backend
        root.mkdir()
        project = ProjectFile(
            meta=ProjectMeta(
                project_id=EXPERIMENT_ID, name="Synthetic FPVS integration",
                template_id="fpvs_6hz_every5_v1",
            ),
            settings=ProjectSettings(
                recording=ProjectRecordingSettings(recording_backend=backend),
                fixation_task=FixationTaskSettings(
                    enabled=False, accuracy_task_enabled=False,
                    participant_tutorial_enabled=False,
                ),
            ),
            stimulus_sets=[
                StimulusSet(set_id="base", name="Base", modality=StimulusModality.WORD,
                            words=["BASE", "NEUTRAL"]),
                StimulusSet(set_id="oddball", name="Oddball", modality=StimulusModality.WORD,
                            words=["ODDBALL", "TARGET"]),
            ],
            conditions=[Condition(
                condition_id="synthetic", name="Synthetic", trigger_code=1,
                base_stimulus_set_id="base", oddball_stimulus_set_id="oddball",
                # Keep at least 30 analyzed cycles after normal endpoint exclusions.
                sequence_count=1, oddball_cycle_repeats_per_sequence=42,
            )],
        )
        project.settings.session.block_count = 1
        save_project_file(project, root / "project.json")
        fingerprint = protocol_fingerprint(project, root)
        config = export_project_config(project, root)
        config.toolbox = config.toolbox.model_copy(update={
            "experiment_id": EXPERIMENT_ID, "experiment_version": EXPERIMENT_VERSION,
            "protocol_sha256": fingerprint, "study_id": STUDY_ID,
        })
        plan = compile_session_plan(project, project_root=root, refresh_hz=60.0, random_seed=83)
        markers = InMemoryMarkers(backend)
        adapter = "SerialBackend" if backend == "serial" else "UnicornUDPBackend"
        with patch(f"fpvs_studio.runtime.triggers.{adapter}", Mock(return_value=markers)):
            summary = RuntimeWorker(StubEngine({})).execute_session(
                root, plan, root / "runs" / "P900001_session01",
                participant_number="900001", participant_session_number=1,
                relative_output_dir="runs/P900001_session01",
                runtime_options={
                    "recording_backend": backend, "recording_selection_source": "project_settings",
                    "export_mode": "compact",
                    "toolbox_handoff_config": config.model_dump(mode="json"),
                },
            )
        if summary.aborted:
            raise RuntimeError("Synthetic Studio session aborted.")
        intent = CaptureIntent(
            report_id=str(uuid4()),
            profile=SharingProfile(
                experiment_id=EXPERIMENT_ID, experiment_version=EXPERIMENT_VERSION,
                protocol_sha256=fingerprint, title=project.meta.name,
                device_id=f"synthetic-{backend}", project_id=STUDY_ID,
            ),
            actual_protocol_sha256=fingerprint, project_id=plan.project_id,
            session_id=plan.session_id, participant_number="900001",
            participant_session_number=1,
            run_ids=tuple(entry.run_id for entry in plan.ordered_entries()),
            experiment_test_mode=False, pilot_mode=False,
        )
        report = build_session_report(plan, summary, intent)
        report_path = root / "logs" / "synthetic-session-report.json"
        atomic_text_write(report_path, report.model_dump_json())
        handoffs = list((root / "logs" / "acquisition").glob("*-completed.fpvsconfig"))
        if len(handoffs) != 1:
            raise RuntimeError("Expected one completed handoff per synthetic recording choice.")
        completed = read_project_config(handoffs[0])
        evidence = completed.completed_session.acquisition_evidence
        if any(len(run.attempted_events) != run.planned_event_count for run in evidence.runs):
            raise RuntimeError("Completed handoff lost actual marker attempt evidence.")
        results.append({
            "recording_backend": backend, "project_root": str(root),
            "handoff_path": str(handoffs[0]), "session_id": plan.session_id,
            "execution_id": evidence.execution_id, "protocol_sha256": fingerprint,
            "planned_event_count": sum(run.planned_event_count for run in evidence.runs),
            "report_path": str(report_path),
        })
    manifest = {
        "schema_version": "1.0", "synthetic": True, "study_id": STUDY_ID,
        "experiment_id": EXPERIMENT_ID, "experiment_version": EXPERIMENT_VERSION,
        "outputs": results,
    }
    manifest_path = output / "acceptance-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"manifest_path": str(manifest_path), **manifest}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / "build/studio-toolbox-acceptance",
    )
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.info(json.dumps(create_acceptance_artifacts(arguments.output), indent=2))
