"""Draft-based authoring of complete FPVS condition modifier workflows."""

from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, cast
from uuid import uuid4

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fpvs_studio.core.backward_counting import (
    backward_counting_steps,
    create_backward_counting_baseline_task,
)
from fpvs_studio.core.condition_modifiers import (
    ConditionModifierKind,
    MemoryImage,
    ModifierDefinition,
    adopt_backward_counting_modifier,
    apply_modifier_draft,
    create_backward_counting_modifier,
    create_image_memory_modifier,
    modifier_condition_ids,
    validate_image_memory_definition,
)
from fpvs_studio.core.masking import MaskingSettings
from fpvs_studio.core.masking_presets import (
    apply_masking_timing_defaults,
    create_masking_modifier,
)
from fpvs_studio.core.models import ProjectFile
from fpvs_studio.core.modifier_presets import (
    ModifierPreset,
    apply_modifier_project,
    import_modifier_definition,
    list_modifier_presets,
    load_modifier_preset,
    modifier_preset_root,
    modifier_presets_dir,
    save_modifier_preset,
)
from fpvs_studio.core.paths import filesystem_path
from fpvs_studio.core.task_assets import modifier_image_references, task_image_references
from fpvs_studio.core.task_models import (
    BackwardCountingRole,
    BackwardCountingSpec,
    TaskBinding,
    TaskModule,
)
from fpvs_studio.gui.components import (
    DialogHeader,
    apply_condition_modifier_theme,
    mark_destructive_action,
    mark_error_text,
    mark_primary_action,
    mark_secondary_action,
    refresh_widget_style,
)
from fpvs_studio.gui.condition_task_dialog import ConditionTaskDialog
from fpvs_studio.gui.document import ProjectDocument
from fpvs_studio.gui.masking_source_dialog import MaskingSourceDialog
from fpvs_studio.gui.modifier_library_dialog import (
    ModifierLibraryDialog,
    ModifierScopeDialog,
    SaveModifierPresetDialog,
)
from fpvs_studio.gui.workers import BackgroundTask


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    return label


def _read_preview_thumbnails(paths: list[Path]) -> dict[str, bytes]:
    """Decode full-size image files only in the background worker."""
    results = {}
    for path in paths:
        with Image.open(filesystem_path(path)) as source:
            source.thumbnail((192, 152))
            with BytesIO() as output:
                source.convert("RGBA").save(output, format="PNG")
                results[str(path)] = output.getvalue()
    return results


def condition_modifier_summary(document: ProjectDocument, condition_id: str) -> str:
    """Summarize declared activities without interpreting legacy free text."""
    names = [
        modifier.name
        for modifier in document.project.condition_modifiers
        if condition_id in modifier_condition_ids(document.project, modifier.modifier_id)
    ]
    if names:
        return ", ".join(names)
    condition = document.get_condition(condition_id)
    if condition is not None and (condition.pre_task_bindings or condition.post_task_bindings):
        return "Existing custom tasks"
    return "No modifiers"


class _ModifierTabs(QTabWidget):
    """Let the dialog allocate page height without hidden pages enlarging it."""

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return False

    def heightForWidth(self, _width: int) -> int:  # noqa: N802
        return -1


class ConditionModifierDialog(QDialog):
    """Keep participant instructions, sustained activity and reports together."""

    def __init__(
        self,
        document: ProjectDocument,
        *,
        condition_id: str,
        fpvs_root: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if document.get_condition(condition_id) is None:
            raise ValueError(f"Unknown condition '{condition_id}'.")
        self.setObjectName("condition_modifier_dialog")
        self.setWindowTitle("FPVS Condition Modifiers")
        self.setMinimumSize(1100, 720)
        self.resize(1120, 760)
        self._document = document
        self._condition_id = condition_id
        self._fpvs_root = fpvs_root
        self._project = document.project.model_copy(deep=True)
        self._asset_sources: dict[str, Path] = {}
        self._thumbnail_icons: dict[str, QIcon] = {}
        self._staging = TemporaryDirectory(prefix="fpvs-modifiers-")
        self._active_task: BackgroundTask | None = None
        self._job_result: object = None
        self._job_error: object = None
        self._loading = False
        self._fields_dirty = False
        self._custom_edited = False
        self._masking_timing_edited = False
        self._selected_id: str | None = None
        self._definitions: dict[str, ModifierDefinition] = {}
        self._scopes: dict[str, list[str]] = {}
        self._target_images: list[MemoryImage] = []
        self._foil_images: list[MemoryImage] = []
        self._recognition_targets: list[MemoryImage] = []
        self._instructions: tuple[str | None, str | None] = (None, None)
        self._baseline_instructions: str | None = None
        self._baseline_endpoint_prompt: str | None = None
        self._loaded_controls: dict[str, int | float] = {}
        self._loaded_instructions: tuple[str | None, str | None] = (None, None)
        for modifier in self._project.condition_modifiers:
            owned = {*modifier.pre_task_ids, *modifier.post_task_ids, modifier.baseline_task_id}
            self._definitions[modifier.modifier_id] = ModifierDefinition(
                modifier=modifier,
                task_modules=[task for task in self._project.task_modules if task.task_id in owned],
            )
            self._scopes[modifier.modifier_id] = modifier_condition_ids(
                self._project,
                modifier.modifier_id,
            )
        self._original_definitions = {
            key: definition.model_copy(deep=True) for key, definition in self._definitions.items()
        }
        self._original_scopes = {key: ids[:] for key, ids in self._scopes.items()}
        self._build_ui()
        self._refresh_list()
        apply_condition_modifier_theme(self)

    def _adopt_typed_counting(self) -> None:
        """Recognize typed linked counting only; never infer a task from its text."""
        owned = {
            task_id
            for modifier in self._project.condition_modifiers
            for task_id in [*modifier.pre_task_ids, *modifier.post_task_ids]
        }
        tasks = self._project.task_modules
        baselines = [
            task
            for task in tasks
            if task.backward_counting is not None
            and task.backward_counting.role == BackwardCountingRole.BASELINE
        ]
        for start in tasks:
            config = start.backward_counting
            if start.task_id in owned or config is None:
                continue
            if config.role != BackwardCountingRole.LOAD_START:
                continue
            reports = [
                task
                for task in tasks
                if task.backward_counting is not None
                and task.backward_counting.role == BackwardCountingRole.LOAD_REPORT
                and task.backward_counting.link_id == config.link_id
            ]
            if len(reports) != 1 or len(baselines) > 1:
                continue
            try:
                self._project = adopt_backward_counting_modifier(
                    self._project,
                    start_task_id=start.task_id,
                    report_task_id=reports[0].task_id,
                    baseline_task_id=baselines[0].task_id if baselines else None,
                    modifier_id=f"counting-{uuid4().hex[:8]}",
                )
            except ValueError:
                # Unsupported legacy arrangements remain available in the full task editor.
                continue

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(
            DialogHeader(
                "FPVS Condition Modifiers",
                "Add participant activities around your FPVS conditions, with instructions "
                "and responses kept together.",
                parent=self,
            )
        )
        body = QHBoxLayout()
        sidebar = QWidget(self)
        sidebar.setFixedWidth(232)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 0, 0)
        side.addWidget(_label("Added to this condition", sidebar))
        self.modifier_list = QListWidget(sidebar)
        self.modifier_list.setObjectName("modifier_added_list")
        self.modifier_list.setWordWrap(True)
        self.modifier_list.currentItemChanged.connect(self._select_item)
        side.addWidget(self.modifier_list, 1)
        self.add_button = QPushButton("Add modifier…", sidebar)
        self.add_button.clicked.connect(self._open_library)
        side.addWidget(self.add_button)
        self.remove_button = QPushButton("Remove from condition", sidebar)
        self.remove_button.clicked.connect(self._remove_selected)
        mark_destructive_action(self.remove_button)
        side.addWidget(self.remove_button)
        self.custom_button = QPushButton("Existing custom tasks…", sidebar)
        self.custom_button.clicked.connect(self._open_advanced)
        side.addWidget(self.custom_button)
        self.convert_button = QPushButton("Convert existing counting…", sidebar)
        self.convert_button.clicked.connect(self._convert_counting)
        self.convert_button.setVisible(
            any(task.backward_counting is not None for task in self._project.task_modules)
            and not self._project.condition_modifiers
        )
        side.addWidget(self.convert_button)
        body.addWidget(sidebar)
        self.detail = QWidget(self)
        detail = QVBoxLayout(self.detail)
        detail.setContentsMargins(0, 0, 0, 0)
        self.title_label = _label("Select or add a modifier", self.detail)
        self.title_label.setProperty("dialogHeading", "true")
        detail.addWidget(self.title_label)
        self.description_label = _label("", self.detail)
        detail.addWidget(self.description_label)
        scope = QHBoxLayout()
        self.scope_label = _label("", self.detail)
        scope.addWidget(self.scope_label, 1)
        self.scope_button = QPushButton("Choose conditions…", self.detail)
        self.scope_button.clicked.connect(self._choose_conditions)
        scope.addWidget(self.scope_button)
        self.copy_button = QPushButton("Make a copy for this condition", self.detail)
        self.copy_button.clicked.connect(self._copy_for_condition)
        scope.addWidget(self.copy_button)
        detail.addLayout(scope)
        self.tabs = _ModifierTabs(self.detail)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.tabs.setObjectName("modifier_editor_tabs")
        self.overview = QWidget(self.tabs)
        overview = QVBoxLayout(self.overview)
        self.workflow_labels: list[QLabel] = []
        flow = QGridLayout()
        for index, title in enumerate(
            ("Session baseline", "Before FPVS", "During FPVS", "After FPVS")
        ):
            group = QGroupBox(title, self.overview)
            group_layout = QVBoxLayout(group)
            label = _label("", group)
            group_layout.addWidget(label)
            self.workflow_labels.append(label)
            flow.addWidget(group, index // 2, index % 2)
        overview.addLayout(flow, 1)
        self.recorded_label = _label("", self.overview)
        overview.addWidget(self.recorded_label)
        self.advanced_button = QPushButton("Advanced steps…", self.overview)
        self.advanced_button.clicked.connect(self._open_advanced)
        overview.addWidget(self.advanced_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.tabs.addTab(self.overview, "Overview")
        self._build_settings()
        self._build_preview()
        self._build_masking_catch_settings()
        self.tabs.currentChanged.connect(self._tab_changed)
        detail.addWidget(self.tabs, 1)
        body.addWidget(self.detail, 1)
        layout.addLayout(body, 1)
        self.status = _label("Changes remain in this draft until Apply.", self)
        self.status.setObjectName("modifier_status")
        self.status.setMinimumHeight(38)
        layout.addWidget(self.status)
        footer = QHBoxLayout()
        self.save_button = QPushButton("Save as local preset…", self)
        self.save_button.clicked.connect(self._save_preset)
        footer.addWidget(self.save_button)
        footer.addStretch()
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        self.apply_button = QPushButton("Apply modifiers", self)
        self.apply_button.clicked.connect(self.accept)
        mark_primary_action(self.apply_button)
        mark_secondary_action(self.cancel_button)
        footer.addWidget(self.apply_button)
        layout.addLayout(footer)

    def _build_settings(self) -> None:
        settings = QWidget(self.tabs)
        layout = QVBoxLayout(settings)
        form = QFormLayout()
        self.name_edit = QLineEdit(settings)
        self.name_edit.setObjectName("modifier_name")
        self.purpose_edit = QLineEdit(settings)
        form.addRow("Name", self.name_edit)
        form.addRow("Purpose", self.purpose_edit)
        layout.addLayout(form)
        self.settings_stack = QStackedWidget(settings)
        self.settings_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        counting = QWidget(settings)
        counting_form = QFormLayout(counting)
        self.step_spin = QSpinBox(counting)
        self.step_spin.setObjectName("modifier_subtraction_step")
        self.step_spin.setRange(1, 999999)
        self.minimum_spin = QSpinBox(counting)
        self.maximum_spin = QSpinBox(counting)
        for spin in (self.minimum_spin, self.maximum_spin):
            spin.setRange(1, 999999999)
        self.baseline_checkbox = QCheckBox("Run once before the selected session", counting)
        self.duration_spin = QDoubleSpinBox(counting)
        self.duration_spin.setObjectName("modifier_baseline_duration")
        self.duration_spin.setDecimals(3)
        self.duration_spin.setRange(0.001, 86400)
        self.duration_spin.setSuffix(" s")
        counting_form.addRow("Subtract each time", self.step_spin)
        counting_form.addRow("Lowest starting number", self.minimum_spin)
        counting_form.addRow("Highest starting number", self.maximum_spin)
        counting_form.addRow("Session baseline", self.baseline_checkbox)
        counting_form.addRow("Baseline duration", self.duration_spin)
        counting_form.addRow(
            _label(
                "Counting during FPVS follows each condition's stream duration. "
                "The baseline runs once, even when a no-load condition appears first.",
                counting,
            )
        )
        self.settings_stack.addWidget(counting)
        memory = QWidget(settings)
        memory_layout = QVBoxLayout(memory)
        image_row = QHBoxLayout()
        self.target_list = QListWidget(memory)
        self.foil_list = QListWidget(memory)
        for title, image_list, callback in (
            ("Four target images", self.target_list, lambda: self._choose_images(True)),
            ("Four foil images", self.foil_list, lambda: self._choose_images(False)),
        ):
            group = QGroupBox(title, memory)
            group_layout = QVBoxLayout(group)
            image_list.setIconSize(QSize(34, 34))
            image_list.setMinimumHeight(90)
            image_list.setMaximumHeight(140)
            group_layout.addWidget(image_list)
            button = QPushButton("Choose four images…", group)
            button.clicked.connect(callback)
            group_layout.addWidget(button)
            image_row.addWidget(group)
        memory_layout.addLayout(image_row)
        timing = QHBoxLayout()
        timing.addWidget(QLabel("Study presentation", memory))
        self.study_mode = QComboBox(memory)
        self.study_mode.addItems(["Self-paced", "Fixed duration"])
        timing.addWidget(self.study_mode, 1)
        self.study_duration = QDoubleSpinBox(memory)
        self.study_duration.setDecimals(3)
        self.study_duration.setRange(0.001, 86400)
        self.study_duration.setValue(10)
        self.study_duration.setSuffix(" s")
        timing.addWidget(self.study_duration)
        memory_layout.addLayout(timing)
        memory_layout.addWidget(
            _label(
                "After FPVS: select exactly four of eight images, revise choices, then Submit. "
                "Incorrect choices are recorded; no corrective feedback is shown.",
                memory,
            )
        )
        self.settings_stack.addWidget(memory)
        masking = QWidget(settings)
        masking_form = QFormLayout(masking)
        self.masking_timing_spins: dict[str, QDoubleSpinBox] = {}
        for key, title in (
            ("soa_ms", "Target-to-mask SOA"), ("target_duration_ms", "Target duration"),
            ("mask_duration_ms", "Mask duration"), ("base_duration_ms", "Base duration"),
        ):
            timing_spin = QDoubleSpinBox(masking)
            timing_spin.setObjectName(f"modifier_masking_{key}")
            timing_spin.setDecimals(9)
            timing_spin.setRange(0.000001, 100000)
            timing_spin.setSuffix(" ms")
            timing_spin.setAccessibleName(title)
            timing_spin.setToolTip(title)
            timing_spin.valueChanged.connect(self._mark_dirty)
            self.masking_timing_spins[key] = timing_spin
        for title, keys in (
            ("SOA / target duration", ("soa_ms", "target_duration_ms")),
            ("Mask / base duration", ("mask_duration_ms", "base_duration_ms")),
        ):
            holder = QWidget(masking)
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            for key in keys:
                row.addWidget(self.masking_timing_spins[key])
            masking_form.addRow(title, holder)
        rgb_row = QWidget(masking)
        rgb_layout = QHBoxLayout(rgb_row)
        rgb_layout.setContentsMargins(0, 0, 0, 0)
        self.masking_background_spins: list[QDoubleSpinBox] = []
        for _index in range(3):
            channel_spin = QDoubleSpinBox(rgb_row)
            channel_spin.setRange(-1, 1)
            channel_spin.setDecimals(9)
            channel_spin.valueChanged.connect(self._mark_dirty)
            self.masking_background_spins.append(channel_spin)
            rgb_layout.addWidget(channel_spin)
        masking_form.addRow("Background RGB (−1 to 1)", rgb_row)
        self.masking_sources_label = _label("", masking)
        self.masking_sources_button = QPushButton("Edit native sources…", masking)
        self.masking_sources_button.clicked.connect(self._edit_masking_sources)
        masking_form.addRow(self.masking_sources_label, self.masking_sources_button)
        self.masking_timing_label = _label("", masking)
        masking_form.addRow(self.masking_timing_label)
        self.masking_defaults_button = QPushButton("Use source experiment timing…", masking)
        self.masking_defaults_button.clicked.connect(self._apply_masking_defaults)
        masking_form.addRow(self.masking_defaults_button)
        self.settings_stack.addWidget(masking)
        layout.addWidget(self.settings_stack, 1)
        self.instructions_button = QPushButton("Edit participant instructions…", settings)
        self.instructions_button.clicked.connect(self._edit_instructions)
        instruction_actions = QHBoxLayout()
        instruction_actions.addWidget(self.instructions_button)
        self.screens_button = QPushButton("Edit modifier screens…", settings)
        self.screens_button.clicked.connect(self._edit_modifier_screens)
        instruction_actions.addWidget(self.screens_button)
        instruction_actions.addStretch()
        layout.addLayout(instruction_actions)
        self.tabs.addTab(settings, "Settings")
        self.name_edit.textChanged.connect(self._mark_dirty)
        self.purpose_edit.textChanged.connect(self._mark_dirty)
        for setting_spin in (
            self.step_spin,
            self.minimum_spin,
            self.maximum_spin,
            self.duration_spin,
            self.study_duration,
        ):
            setting_spin.valueChanged.connect(self._mark_dirty)
        self.baseline_checkbox.toggled.connect(self.duration_spin.setEnabled)
        self.baseline_checkbox.toggled.connect(self._mark_dirty)
        self.study_mode.currentIndexChanged.connect(
            lambda index: self.study_duration.setEnabled(index == 1)
        )
        self.study_mode.currentIndexChanged.connect(self._mark_dirty)

    def _build_preview(self) -> None:
        page = QWidget(self.tabs)
        layout = QVBoxLayout(page)
        self.preview_phase = QComboBox(page)
        self.preview_phase.addItems(
            ["Before FPVS", "During FPVS", "After FPVS", "Session baseline"]
        )
        self.preview_phase.currentIndexChanged.connect(self._refresh_preview)
        layout.addWidget(self.preview_phase)
        self.preview_text = _label("", page)
        self.preview_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview_text)
        self.preview_grid_widget = QWidget(page)
        self.preview_grid = QGridLayout(self.preview_grid_widget)
        self.preview_images: list[QPushButton] = []
        for index in range(8):
            button = QPushButton(self.preview_grid_widget)
            button.setCheckable(True)
            button.setMinimumHeight(100)
            button.setIconSize(QSize(96, 76))
            button.clicked.connect(self._preview_selection_changed)
            self.preview_grid.addWidget(button, index // 4, index % 4)
            self.preview_images.append(button)
        layout.addWidget(self.preview_grid_widget, 1)
        self.preview_endpoint = QLineEdit(page)
        self.preview_endpoint.setPlaceholderText("Type an example final number")
        layout.addWidget(self.preview_endpoint)
        self.preview_submit = QPushButton("Submit preview response", page)
        self.preview_submit.clicked.connect(self._submit_preview)
        layout.addWidget(self.preview_submit, 0, Qt.AlignmentFlag.AlignHCenter)
        self.preview_result = _label(
            "Preview only. No session seed or participant data is used.", page
        )
        layout.addWidget(self.preview_result)
        self.tabs.addTab(page, "Participant preview")

    def _build_masking_catch_settings(self) -> None:
        page = QWidget(self.tabs)
        layout = QVBoxLayout(page)
        self.masking_catch_checkbox = QCheckBox(
            "Add one catch trial per variant block", page,
        )
        self.masking_catch_checkbox.setObjectName("modifier_masking_catch_enabled")
        layout.addWidget(self.masking_catch_checkbox)
        form = QFormLayout()
        self.masking_catch_trigger_spin = QSpinBox(page)
        self.masking_catch_trigger_spin.setObjectName("modifier_masking_catch_trigger")
        self.masking_catch_trigger_spin.setRange(1, 255)
        self.masking_catch_trigger_spin.setAccessibleName("Catch EEG code")
        form.addRow("Catch EEG code", self.masking_catch_trigger_spin)
        layout.addLayout(form)
        self.masking_catch_help = _label(
            "Adds one full-length target-absent sequence at a random position in each variant "
            "block, using a randomly selected SOA from that block. Masks and base stimuli remain."
            "\n\nAll SOAs in the same variant must use matching catch settings and code. "
            "Use a code distinct from ordinary conditions and other variants. Other modifiers "
            "are not changed automatically."
            "\n\nEdit modifier screens to explain that targets may be absent. Enabling catches "
            "does not rewrite participant instructions. PAS 'No experience' scores a correct "
            "rejection; the four-choice identity response remains unscored on catch trials.", page,
        )
        layout.addWidget(self.masking_catch_help)
        layout.addStretch()
        self.masking_catch_checkbox.toggled.connect(self.masking_catch_trigger_spin.setEnabled)
        self.masking_catch_checkbox.toggled.connect(self._mark_dirty)
        self.masking_catch_trigger_spin.valueChanged.connect(self._mark_dirty)
        self.masking_catch_tab_index = self.tabs.addTab(page, "Catch trials")
        self.tabs.setTabVisible(self.masking_catch_tab_index, False)

    def _mark_dirty(self, *_args: object) -> None:
        if not self._loading:
            self._fields_dirty = True
            self._set_status("Unsaved modifier edits. Apply updates the experiment copy only.")

    def _save_fields(self) -> bool:
        if self._selected_id is None or not self._fields_dirty:
            return True
        existing = self._definitions[self._selected_id]
        try:
            definition = existing.model_copy(deep=True)
            definition.modifier.name = self.name_edit.text().strip()
            definition.modifier.description = self.purpose_edit.text().strip()
            if existing.modifier.kind == ConditionModifierKind.BACKWARD_COUNTING:
                baseline_id = definition.modifier.baseline_task_id
                new_baseline = self.baseline_checkbox.isChecked() and baseline_id is None
                if self.baseline_checkbox.isChecked() and baseline_id is None:
                    baseline = create_backward_counting_baseline_task(
                        task_id=f"{self._selected_id}-baseline",
                        link_id=f"{self._selected_id}-baseline",
                    )
                    definition.task_modules.append(baseline)
                    definition.modifier.baseline_task_id = baseline.task_id
                elif not self.baseline_checkbox.isChecked() and baseline_id is not None:
                    definition.task_modules = [
                        task for task in definition.task_modules if task.task_id != baseline_id
                    ]
                    definition.modifier.baseline_task_id = None
                for task in definition.task_modules:
                    config = task.backward_counting
                    if config is None:
                        continue
                    for key, attribute, value in (
                        ("step", "subtraction_step", self.step_spin.value()),
                        ("minimum", "start_min", self.minimum_spin.value()),
                        ("maximum", "start_max", self.maximum_spin.value()),
                    ):
                        if value != self._loaded_controls.get(key) or (
                            new_baseline and config.role == BackwardCountingRole.BASELINE
                        ):
                            setattr(config, attribute, value)
                    if config.role == BackwardCountingRole.BASELINE:
                        if (self.duration_spin.value() != self._loaded_controls.get("baseline")
                                or new_baseline):
                            config.duration_seconds = self.duration_spin.value()
                        config.instructions = self._baseline_instructions
                        config.endpoint_prompt = self._baseline_endpoint_prompt
                    else:
                        if self._instructions[0] != self._loaded_instructions[0]:
                            config.instructions = self._instructions[0]
                        if self._instructions[1] != self._loaded_instructions[1]:
                            config.endpoint_prompt = self._instructions[1]
            elif existing.modifier.kind == ConditionModifierKind.MASKING:
                settings = definition.modifier.masking
                assert settings is not None
                values = settings.model_dump()
                for key, spin in self.masking_timing_spins.items():
                    if spin.value() != self._loaded_controls.get(key):
                        values[key] = spin.value()
                for index, spin in enumerate(self.masking_background_spins):
                    if spin.value() != self._loaded_controls.get(f"background_{index}"):
                        background = list(values["background_rgb"])
                        background[index] = spin.value()
                        values["background_rgb"] = tuple(background)
                values["catch_trial"] = (
                    {"trigger_code": self.masking_catch_trigger_spin.value()}
                    if self.masking_catch_checkbox.isChecked() else None
                )
                definition.modifier.masking = MaskingSettings.model_validate(values)
            else:
                kwargs = {}
                if self._instructions[0] is not None:
                    kwargs["study_instructions"] = self._instructions[0]
                if self._instructions[1] is not None:
                    kwargs["recognition_instructions"] = self._instructions[1]
                generated = create_image_memory_modifier(
                    modifier_id=self._selected_id,
                    target_images=self._target_images,
                    foil_images=self._foil_images,
                    recognition_target_images=self._recognition_targets or None,
                    study_duration_seconds=(
                        self.study_duration.value() if self.study_mode.currentIndex() == 1 else None
                    ),
                    **kwargs,
                )
                for task, generated_task in zip(
                    (self._study_module(definition), self._recognition_module(definition)),
                    (self._study_module(generated), self._recognition_module(generated)),
                    strict=True,
                ):
                    if not task.steps:
                        task.steps = generated_task.steps
                        continue
                    if not generated_task.steps:
                        continue
                    original, updated = task.steps[0], generated_task.steps[0]
                    fields: tuple[str, ...] = ("text", "items")
                    if task.task_id in definition.modifier.pre_task_ids:
                        fields += ("kind",)
                        if (self.study_duration.value() != self._loaded_controls.get("study")
                                or self.study_mode.currentIndex()
                                != self._loaded_controls.get("study_mode")):
                            fields += ("continue_key", "duration_seconds")
                    # Keep authored fonts, geometry, submission labels and response settings.
                    item_by_id = {item.item_id: item for item in original.items}
                    updated.items = [
                        item_by_id[item.item_id].model_copy(update={"image_path": item.image_path})
                        if item.item_id in item_by_id
                        else item
                        for item in updated.items
                    ]
                    task.steps[0] = original.model_copy(
                        update={field: getattr(updated, field) for field in fields},
                        deep=True,
                    )
            self._definitions[self._selected_id] = ModifierDefinition.model_validate(
                definition.model_dump(),
            )
        except ValueError as error:
            self._show_error(error)
            return False
        self._fields_dirty = False
        self._snapshot_controls()
        return True

    def _snapshot_controls(self) -> None:
        self._loaded_controls = {
            "step": self.step_spin.value(), "minimum": self.minimum_spin.value(),
            "maximum": self.maximum_spin.value(), "baseline": self.duration_spin.value(),
            "study": self.study_duration.value(), "study_mode": self.study_mode.currentIndex(),
            **{key: spin.value() for key, spin in self.masking_timing_spins.items()},
            **{f"background_{index}": spin.value()
               for index, spin in enumerate(self.masking_background_spins)},
        }
        self._loaded_instructions = self._instructions

    def _refresh_list(self, selected_id: str | None = None) -> None:
        self._loading = True
        self.modifier_list.blockSignals(True)
        self.modifier_list.clear()
        selected_row = 0
        for key, definition in self._definitions.items():
            if self._condition_id not in self._scopes[key] and (
                self._scopes[key] or key in self._original_definitions
            ):
                continue
            count = len(self._scopes[key])
            scope_text = f"{count} {'condition' if count == 1 else 'conditions'}"
            item = QListWidgetItem(f"{definition.modifier.name}\n{scope_text}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(definition.modifier.name)
            self.modifier_list.addItem(item)
            if key == selected_id:
                selected_row = self.modifier_list.count() - 1
        self.modifier_list.setCurrentRow(selected_row)
        self.modifier_list.blockSignals(False)
        self._loading = False
        self._selected_id = None
        self._select_item(self.modifier_list.currentItem(), None)

    def _select_item(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        if not self._save_fields():
            self.modifier_list.blockSignals(True)
            if previous is not None:
                self.modifier_list.setCurrentItem(previous)
            self.modifier_list.blockSignals(False)
            return
        self._selected_id = str(current.data(Qt.ItemDataRole.UserRole)) if current else None
        enabled = self._selected_id is not None
        self.detail.setEnabled(enabled)
        self.remove_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled and self._fpvs_root is not None)
        self.save_button.setToolTip(
            "" if self._fpvs_root is not None else "Choose an FPVS Studio Root Folder in Settings."
        )
        if not enabled:
            self.title_label.setText("Add a modifier to get started")
            self._refresh_details()
            return
        definition = self._definitions[cast(str, self._selected_id)]
        self._loading = True
        self.name_edit.setText(definition.modifier.name)
        self.purpose_edit.setText(definition.modifier.description)
        self.purpose_edit.setToolTip(definition.modifier.description)
        is_counting = definition.modifier.kind == ConditionModifierKind.BACKWARD_COUNTING
        is_masking = definition.modifier.kind == ConditionModifierKind.MASKING
        self.settings_stack.setCurrentIndex(0 if is_counting else 2 if is_masking else 1)
        self.tabs.setTabVisible(self.masking_catch_tab_index, is_masking)
        self.screens_button.setVisible(not is_counting)
        self.instructions_button.setVisible(not is_masking)
        if is_counting:
            start = next(
                task
                for task in definition.task_modules
                if task.backward_counting
                and task.backward_counting.role == BackwardCountingRole.LOAD_START
            )
            config = start.backward_counting
            assert config is not None
            baseline = next(
                (
                    task.backward_counting
                    for task in definition.task_modules
                    if task.task_id == definition.modifier.baseline_task_id
                ),
                None,
            )
            self.step_spin.setValue(config.subtraction_step)
            self.minimum_spin.setValue(config.start_min)
            self.maximum_spin.setValue(config.start_max)
            self.baseline_checkbox.setChecked(baseline is not None)
            self.duration_spin.setValue(baseline.duration_seconds if baseline else 120)
            self.duration_spin.setEnabled(baseline is not None)
            self._instructions = (config.instructions, config.endpoint_prompt)
            self._baseline_instructions = baseline.instructions if baseline else None
            self._baseline_endpoint_prompt = baseline.endpoint_prompt if baseline else None
        elif is_masking:
            settings = definition.modifier.masking
            assert settings is not None
            for key, spin in self.masking_timing_spins.items():
                spin.setValue(getattr(settings, key))
            for spin, channel in zip(
                self.masking_background_spins, settings.background_rgb, strict=True,
            ):
                spin.setValue(channel)
            catch = settings.catch_trial
            self.masking_catch_trigger_spin.setValue(
                catch.trigger_code if catch is not None
                else {"color": 10, "faces": 11, "number": 12}[settings.variant]
            )
            self.masking_catch_checkbox.setChecked(catch is not None)
            self.masking_catch_trigger_spin.setEnabled(catch is not None)
            self._refresh_masking_sources(settings)
        else:
            study = self._study_module(definition)
            recognition = self._recognition_module(definition)
            step = study.steps[0]
            self._target_images = [
                MemoryImage(image_id=item.item_id, image_path=item.image_path)
                for item in step.items
                if item.image_path is not None
            ]
            recognition_items = recognition.steps[0].items if recognition.steps else []
            self._recognition_targets = [
                MemoryImage(image_id=item.item_id, image_path=item.image_path)
                for item in recognition_items
                if item.correct and item.image_path is not None
            ]
            self._foil_images = [
                MemoryImage(image_id=item.item_id, image_path=item.image_path)
                for item in recognition_items
                if not item.correct and item.image_path is not None
            ]
            self.study_mode.setCurrentIndex(0 if step.duration_seconds is None else 1)
            self.study_duration.setValue(step.duration_seconds or 10)
            self.study_duration.setEnabled(step.duration_seconds is not None)
            self._instructions = (
                step.text,
                recognition.steps[0].text
                if recognition.steps
                else "Select the four images you studied, then press Submit.",
            )
            self._refresh_image_lists()
        self._loading = False
        self._fields_dirty = False
        self._snapshot_controls()
        self._refresh_details()
        if not is_counting and not is_masking:
            self._request_thumbnails()

    @staticmethod
    def _study_module(definition: ModifierDefinition) -> TaskModule:
        return next(
            task
            for task in definition.task_modules
            if task.task_id in definition.modifier.pre_task_ids
        )

    @staticmethod
    def _recognition_module(definition: ModifierDefinition) -> TaskModule:
        return next(
            task
            for task in definition.task_modules
            if task.task_id in definition.modifier.post_task_ids
        )

    def _refresh_details(self) -> None:
        affected = {self._condition_id} if self._custom_edited else set()
        if self._masking_timing_edited:
            affected.update(condition.condition_id for condition in self._project.conditions)
        for key in self._original_definitions.keys() | self._definitions.keys():
            before = set(self._original_scopes.get(key, []))
            after = set(self._scopes.get(key, []))
            definition_changed = (
                self._definitions.get(key) != self._original_definitions.get(key)
                or (key == self._selected_id and self._fields_dirty)
            )
            affected.update(before | after if definition_changed else before ^ after)
        self.apply_button.setText(
            f"Apply to {len(affected)} {'condition' if len(affected) == 1 else 'conditions'}"
            if affected else "Apply modifiers"
        )
        if self._selected_id is None:
            return
        definition = self._definitions[self._selected_id]
        modifier = definition.modifier
        self.title_label.setText(modifier.name)
        description = modifier.description
        self.description_label.setText(
            description if len(description) <= 220 else description[:217] + "…"
        )
        self.description_label.setToolTip(description)
        count = len(self._scopes[self._selected_id])
        self.copy_button.setVisible(
            count > 1 and self._condition_id in self._scopes[self._selected_id]
        )
        self.scope_label.setText(
            f"Assigned to {count} {'condition' if count == 1 else 'conditions'} · Project copy"
        )
        names = [
            condition.name
            for condition in self._project.conditions
            if condition.condition_id in self._scopes[self._selected_id]
        ]
        self.scope_label.setToolTip("\n".join(names))
        if modifier.kind == ConditionModifierKind.BACKWARD_COUNTING:
            phase_copy = (
                f"Count for {self.duration_spin.value():g} seconds, then report the final number. "
                "Once before the first FPVS stream."
                if self.baseline_checkbox.isChecked()
                else "No counting baseline requested.",
                f"Show a random starting number from {self.minimum_spin.value()} to "
                f"{self.maximum_spin.value()}. Subtract {self.step_spin.value()} each time.",
                "Count silently while watching the images. The counting interval ends "
                "when the FPVS images disappear.",
                "Type the final number immediately after the stream, then continue.",
            )
            self.recorded_label.setText(
                "Recorded data: starting and final numbers, subtraction step, interval duration, "
                "estimated steps and counting rate, and available baseline comparison. "
                "The estimate does not verify arithmetic accuracy."
            )
        elif modifier.kind == ConditionModifierKind.MASKING:
            settings = modifier.masking
            assert settings is not None
            catch_enabled = self.masking_catch_checkbox.isChecked()
            phase_copy = (
                "No separate baseline.",
                "Instructions and two-second fixation before each experiment variant.",
                "Brief target followed by a mask at "
                f"{self.masking_timing_spins['soa_ms'].value():g} ms SOA. "
                "The same target repeats throughout the run. "
                + ("One extra target-absent catch per variant block." if catch_enabled else ""),
                "Visibility → target identity → frequency → self-paced break and fixation.",
            )
            self.recorded_label.setText(
                "Recorded data: realized frame timing, target identity, selected answers, "
                "identity correctness and response times. "
                + ("Catch trials use PAS to score absence; identity is unscored."
                   if catch_enabled else "Native source properties are retained.")
            )
            self._refresh_masking_sources(settings)
        else:
            study_key = self._study_module(definition).steps[0].continue_key or "space"
            phase_copy = (
                "No session baseline.",
                "Study four target images. "
                + (
                    f"Press {study_key.title()} when ready."
                    if self.study_mode.currentIndex() == 0
                    else f"Shown for {self.study_duration.value():g} seconds."
                ),
                "Keep the four targets in mind while watching the unchanged FPVS stream.",
                "Choose exactly four of eight images and Submit. Choices can be revised.",
            )
            self.recorded_label.setText(
                "Recorded data: target and foil identities, presentation order, selected images, "
                "response time, target hits out of four and exact-set correctness."
            )
        for label, text in zip(self.workflow_labels, phase_copy, strict=True):
            label.setText(text)
        self._refresh_preview()

    def _refresh_masking_sources(self, settings: MaskingSettings) -> None:
        masks = len(settings.mask_visuals) if settings.mask_visuals else len(settings.base_visuals)
        self.masking_sources_label.setText(
            f"{len(settings.base_visuals)} base · "
            f"{len(settings.target_visuals)} target · {masks} mask"
        )
        self.masking_timing_label.setText(
            f"Project: {self._project.settings.protocol.base_hz:g} Hz; target every "
            f"{self._project.settings.protocol.oddball_every_n} items. Source: 5 Hz, "
            "40 cycles/run, three randomized SOA triplets. Native sources replace "
            "ordinary condition pools while Masking is assigned."
        )

    def _edit_masking_sources(self) -> None:
        if self._selected_id is None or not self._save_fields():
            return
        definition = self._definitions[self._selected_id]
        settings = definition.modifier.masking
        assert settings is not None
        dialog = MaskingSourceDialog(
            settings, project_root=self._document.project_root,
            task_id=definition.modifier.pre_task_ids[0], parent=self,
            answers={item.item_id: item.text or item.item_id
                     for task in definition.task_modules for step in task.steps
                     if step.step_id == "masking-identification" for item in step.items
                     if item.selectable},
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if settings.variant == "color":
            previous_colors = {visual.visual_id: visual.rgb for visual in settings.target_visuals}
            changed_colors = {
                visual.visual_id: visual.rgb for visual in dialog.settings.target_visuals
                if visual.visual_id in previous_colors
                and visual.rgb != previous_colors[visual.visual_id]
            }
            for task in definition.task_modules:
                for step in task.steps:
                    if step.step_id == "masking-identification":
                        for item in step.items:
                            if item.item_id in changed_colors:
                                item.color_rgb = changed_colors[item.item_id]
        definition.modifier.masking = dialog.settings
        self._asset_sources.update(dialog.asset_sources)
        self._refresh_details()
        self._set_status(
            "Native sources updated in the draft. Matching color answer swatches follow changed "
            "target colors. Apply modifiers saves changes."
            if settings.variant == "color" else
            "Native sources updated in the draft. Apply modifiers saves changes."
        )

    def _apply_masking_defaults(self) -> None:
        if not self._save_fields():
            return
        answer = QMessageBox.question(
            self, "Use source experiment timing",
            "Set this experiment to 5 Hz with a target every five items, 40 cycles per "
            "Masking run, three repetitions of each configured SOA, and steady fixation? "
            "The 5 Hz cadence is project-wide; ordinary conditions keep their own run counts. "
            "These changes remain pending until Apply modifiers.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._project = apply_masking_timing_defaults(self._build_project())
        self._masking_timing_edited = True
        self._refresh_details()
        self._set_status("Source timing is staged. Apply modifiers saves the experiment settings.")

    def _tab_changed(self, *_args: object) -> None:
        if self._loading:
            return
        if self._save_fields():
            self._refresh_details()

    def _choose_conditions(self) -> None:
        if self._selected_id is None or not self._save_fields():
            return
        conflicts = {
            condition_id: self._definitions[key].modifier.name
            for key, ids in self._scopes.items()
            if key != self._selected_id
            for condition_id in ids
        }
        dialog = ModifierScopeDialog(
            self._project,
            selected_ids=self._scopes[self._selected_id],
            conflicts=conflicts,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._scopes[self._selected_id] = dialog.condition_ids
            self._refresh_list(self._selected_id)
            self._set_status(
                "Condition assignments changed in this draft. Review and Apply to keep them."
            )

    def _remove_selected(self) -> None:
        if self._selected_id is None:
            return
        key = self._selected_id
        self._scopes[key] = [
            condition_id for condition_id in self._scopes[key]
            if condition_id != self._condition_id
        ]
        if not self._scopes[key]:
            del self._definitions[key]
            del self._scopes[key]
        self._fields_dirty = False
        self._selected_id = None
        self._refresh_list()
        self._set_status(
            "Modifier removed from this condition in the draft. Apply to keep this change."
        )

    def _convert_counting(self) -> None:
        answer = QMessageBox.question(
            self,
            "Convert existing counting",
            "Group the existing typed counting tasks into one modifier, preserving their "
            "saved numbers, duration and instructions? The baseline will run once when the "
            "selected session includes a counting condition. A no-load-only test will have "
            "no counting baseline. This conversion remains a draft until Apply.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._adopt_typed_counting()
        for modifier in self._project.condition_modifiers:
            if modifier.modifier_id in self._definitions:
                continue
            owned = {*modifier.pre_task_ids, *modifier.post_task_ids, modifier.baseline_task_id}
            definition = ModifierDefinition(
                modifier=modifier,
                task_modules=[task for task in self._project.task_modules if task.task_id in owned],
            )
            self._definitions[modifier.modifier_id] = definition
            self._scopes[modifier.modifier_id] = modifier_condition_ids(
                self._project,
                modifier.modifier_id,
            )
            self._original_definitions[modifier.modifier_id] = definition.model_copy(deep=True)
            self._original_scopes[modifier.modifier_id] = self._scopes[modifier.modifier_id][:]
        self._refresh_list()
        self.convert_button.setVisible(not self._definitions)
        self._set_status(
            "Existing counting grouped in the draft. Saved settings are retained; Apply commits "
            "the reviewed baseline scope."
            if self._definitions
            else "These counting tasks use a custom arrangement. "
            "Edit them under Existing custom tasks."
        )

    def _copy_for_condition(self) -> None:
        if self._selected_id is None or not self._save_fields():
            return
        original_id = self._selected_id
        definition = self._definitions[original_id].model_copy(deep=True)
        staging = Path(self._staging.name)
        sources = dict(self._asset_sources)
        source_root = self._document.project_root

        def copied(value: object) -> None:
            clone = cast(ModifierDefinition, value)
            clone.modifier.name += " (condition copy)"
            if original_id in self._original_definitions:
                self._definitions[original_id] = self._original_definitions[original_id].model_copy(
                    deep=True,
                )
            for task in clone.task_modules:
                for path in task_image_references(task):
                    self._asset_sources[path] = staging / path
            for path in modifier_image_references(clone.modifier):
                self._asset_sources[path] = staging / path
            self._scopes[original_id] = [
                condition_id
                for condition_id in self._scopes[original_id]
                if condition_id != self._condition_id
            ]
            key = clone.modifier.modifier_id
            self._definitions[key] = clone
            self._scopes[key] = [self._condition_id]
            self._refresh_list(key)
            self._set_status(
                "This condition now has its own draft copy. Other conditions retain the original."
            )

        self._run_job(
            lambda: import_modifier_definition(
                staging, definition, source_root, asset_sources=sources
            ),
            copied,
            "Copying modifier settings and images into the draft…",
        )

    def _open_library(self) -> None:
        if not self._save_fields():
            return
        if self._fpvs_root is None:
            self._show_library([])
        else:
            root = self._fpvs_root
            self._run_job(
                lambda: list_modifier_presets(root),
                self._show_library,
                "Reading local modifier presets…",
            )

    def _show_library(self, value: object) -> None:
        presets = cast(list[ModifierPreset], value)
        dialog = ModifierLibraryDialog(
            presets,
            library_path=modifier_presets_dir(self._fpvs_root)
            if self._fpvs_root is not None
            else None,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selection is None:
            return
        source, key = dialog.selection
        new_id = f"modifier-{uuid4().hex[:10]}"
        if source == "built-in":
            if key.startswith("masking-"):
                variant = cast(Literal["color", "faces", "number"], key.removeprefix("masking-"))
                self._add_definition(create_masking_modifier(modifier_id=new_id, variant=variant))
                self.tabs.setCurrentIndex(1)
                self._set_status(
                    "Masking added to the draft. Review native sources and use source experiment "
                    "timing when reproducing the original study. Apply saves the complete draft."
                )
                return
            factory = (
                create_backward_counting_modifier
                if key == "backward-counting"
                else create_image_memory_modifier
            )
            self._add_definition(factory(modifier_id=new_id))
            return
        assert self._fpvs_root is not None
        root = self._fpvs_root
        staging = Path(self._staging.name)

        def import_preset() -> ModifierDefinition:
            preset = load_modifier_preset(root, key)
            definition = preset.definition.model_copy(deep=True)
            definition.modifier.name = preset.name
            definition.modifier.description = preset.description
            return import_modifier_definition(
                staging,
                definition,
                modifier_preset_root(root, key),
                modifier_id=new_id,
            )

        def imported(value: object) -> None:
            definition = cast(ModifierDefinition, value)
            for task in definition.task_modules:
                for path in task_image_references(task):
                    self._asset_sources[path] = staging / path
            for path in modifier_image_references(definition.modifier):
                self._asset_sources[path] = staging / path
            self._add_definition(definition)

        self._run_job(import_preset, imported, "Copying preset into the dialog draft…")

    def _add_definition(self, definition: ModifierDefinition) -> None:
        key = definition.modifier.modifier_id
        self._definitions[key] = definition
        occupied = any(self._condition_id in ids for ids in self._scopes.values())
        self._scopes[key] = [] if occupied else [self._condition_id]
        self._refresh_list(key)
        self._set_status(
            "Added to the draft. Choose its conditions and Apply when ready."
            if occupied
            else "Added to this condition's draft. Apply when ready."
        )

    def _choose_images(self, targets: bool) -> None:
        if self._selected_id is None:
            return
        paths, _filter = QFileDialog.getOpenFileNames(
            self,
            "Choose four target images" if targets else "Choose four foil images",
            str(self._document.project_root),
            "Images (*.png *.jpg *.jpeg)",
        )
        if not paths:
            return
        if len(paths) != 4 or len(set(paths)) != 4:
            self._show_error(ValueError("Choose exactly four different image files."))
            return
        other_images = self._foil_images if targets else self._target_images
        other_paths = {self._asset_path(image.image_path).resolve() for image in other_images}
        if any(Path(path).resolve() in other_paths for path in paths):
            self._show_error(ValueError("Target and foil images must use different files."))
            return
        images = []
        recognition_targets = []
        revision = uuid4().hex[:8]
        for index, filename in enumerate(paths, start=1):
            source = Path(filename)
            self._thumbnail_icons.pop(str(source), None)
            image_id = f"{'target' if targets else 'foil'}-{index}"
            modifier = self._definitions[self._selected_id].modifier
            task_id = modifier.pre_task_ids[0] if targets else modifier.post_task_ids[0]
            filename = f"{image_id}-{revision}{source.suffix.lower()}"
            path = f"stimuli/task-assets/{task_id}/{filename}"
            images.append(MemoryImage(image_id=image_id, image_path=path))
            self._asset_sources[path] = source
            if targets:
                recognition_path = f"stimuli/task-assets/{modifier.post_task_ids[0]}/{filename}"
                recognition_targets.append(
                    MemoryImage(image_id=image_id, image_path=recognition_path)
                )
                self._asset_sources[recognition_path] = source
        if targets:
            self._target_images = images
            self._recognition_targets = recognition_targets
        else:
            self._foil_images = images
        self._refresh_image_lists()
        self._mark_dirty()
        self._request_thumbnails()

    def _asset_path(self, relative_path: str) -> Path:
        return self._asset_sources.get(relative_path, self._document.project_root / relative_path)

    def _refresh_image_lists(self) -> None:
        for image_list, images in (
            (self.target_list, self._target_images),
            (self.foil_list, self._foil_images),
        ):
            image_list.clear()
            for image in images:
                path = self._asset_path(image.image_path)
                item = QListWidgetItem(self._thumbnail_icons.get(str(path), QIcon()), path.name)
                item.setToolTip(str(path))
                image_list.addItem(item)

    def _request_thumbnails(self) -> None:
        paths = list(
            dict.fromkeys(
                self._asset_path(image.image_path)
                for image in [*self._target_images, *self._foil_images, *self._recognition_targets]
                if str(self._asset_path(image.image_path)) not in self._thumbnail_icons
            )
        )
        if not paths or self._active_task is not None:
            return

        def ready(value: object) -> None:
            for path, data in cast(dict[str, bytes], value).items():
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                self._thumbnail_icons[path] = QIcon(pixmap)
            self._refresh_image_lists()
            self._refresh_preview()
            self._set_status("Image previews ready. Changes remain pending until Apply.")

        self._run_job(lambda: _read_preview_thumbnails(paths), ready, "Preparing image previews…")

    def _edit_instructions(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Participant instructions")
        dialog.setMinimumSize(680, 440)
        layout = QVBoxLayout(dialog)
        counting = self.settings_stack.currentIndex() == 0
        if counting:
            dialog.setMinimumHeight(600)
        layout.addWidget(
            _label(
                "The starting number and subtraction step are supplied automatically. "
                "Leave blank to use the standard instructions."
                if counting
                else "Edit the study and recognition prompts shown to participants.",
                dialog,
            )
        )
        editors = []
        entries = list(
            zip(
                ("Before FPVS", "Endpoint question" if counting else "After FPVS"),
                self._instructions,
                strict=True,
            )
        )
        if counting:
            entries.extend(
                [
                    ("Baseline instructions", self._baseline_instructions),
                    ("Baseline endpoint question", self._baseline_endpoint_prompt),
                ]
            )
        for title, content in entries:
            layout.addWidget(QLabel(title, dialog))
            editor = QTextEdit(dialog)
            editor.setPlainText(content or "")
            editors.append(editor)
            layout.addWidget(editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        apply_condition_modifier_theme(dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._instructions = (
                editors[0].toPlainText().strip() or None,
                editors[1].toPlainText().strip() or None,
            )
            if counting:
                self._baseline_instructions = editors[2].toPlainText().strip() or None
                self._baseline_endpoint_prompt = editors[3].toPlainText().strip() or None
            self._mark_dirty()

    def _refresh_preview(self, *_args: object) -> None:
        if self._selected_id is None:
            return
        definition = self._definitions[self._selected_id]
        counting = definition.modifier.kind == ConditionModifierKind.BACKWARD_COUNTING
        phase = self.preview_phase.currentIndex()
        if definition.modifier.kind == ConditionModifierKind.MASKING:
            self.preview_grid_widget.hide()
            self.preview_endpoint.hide()
            self.preview_submit.hide()
            self.preview_result.setText(
                "Sequence overview. Edit modifier screens previews the authored question layouts."
            )
            settings = definition.modifier.masking
            assert settings is not None
            catch_preview = (
                "\n\nOne extra sequence per variant block omits every target, retains the masks, "
                "and uses a randomly selected SOA. PAS 'No experience' is a correct rejection; "
                "target identity is unscored."
                if self.masking_catch_checkbox.isChecked() else ""
            )
            self.preview_text.setText((
                "Instructions → Space → two-second red fixation.",
                f"Base presentations start {self.masking_timing_spins['soa_ms'].value():g} ms "
                "into each item slot. On target slots, the target starts immediately and the "
                "mask follows at the selected SOA. Native sources preserve color and geometry."
                + catch_preview,
                "How clearly did you see the brief target stimulus during the sequence?\n\n"
                "Identify the target.\n\n"
                "How often did you see the brief target stimulus during the sequence?\n\n"
                "Take a break, then press Space.",
                "This modifier has no separate session baseline.",
            )[phase])
            return
        self.preview_grid_widget.setVisible(not counting and phase in (0, 2))
        self.preview_endpoint.setVisible(counting and phase == 2)
        self.preview_submit.setVisible(phase == 2)
        self.preview_submit.setEnabled(counting)
        self.preview_result.setText("Preview only. No participant data is saved.")
        if counting:
            roles = {
                task.backward_counting.role: task.backward_counting
                for task in definition.task_modules
                if task.backward_counting is not None
            }
            if phase == 1:
                text = "FPVS images play here. Continue counting silently until they disappear."
            else:
                role = (
                    BackwardCountingRole.LOAD_START
                    if phase == 0
                    else BackwardCountingRole.LOAD_REPORT
                    if phase == 2
                    else BackwardCountingRole.BASELINE
                )
                config = roles.get(role)
                if config is None:
                    text = "No baseline is enabled."
                else:
                    number = min(max(1053, config.start_min), config.start_max)
                    screens = backward_counting_steps(
                        BackwardCountingSpec.model_validate(
                            {
                                **config.model_dump(),
                                "start_number": number,
                            }
                        )
                    )
                    text = "\n\n".join(
                        screen.text
                        + ("\n" + screen.questions[0].prompt if screen.questions else "")
                        for screen in screens
                    )
            self.preview_text.setText(text)
            return
        texts = (
            self._instructions[0] or "Remember these four images. Press Space when ready.",
            "FPVS images play here. Keep the four studied images in mind.",
            self._instructions[1] or "Select the four images you studied, then Submit.",
            "This modifier has no session baseline.",
        )
        self.preview_text.setText(texts[phase])
        images = (
            self._target_images if phase == 0 else [*self._recognition_targets, *self._foil_images]
        )
        for index, button in enumerate(self.preview_images):
            self.preview_grid.addWidget(
                button, index // (2 if phase == 0 else 4), index % (2 if phase == 0 else 4)
            )
            button.setChecked(False)
            button.setVisible(index < (4 if phase == 0 else 8))
            button.setEnabled(phase == 2 and len(images) == 8)
            if index < len(images):
                path = self._asset_path(images[index].image_path)
                icon = self._thumbnail_icons.get(str(path), QIcon())
                button.setIcon(icon)
                button.setText("" if not icon.isNull() else "Preparing image…")
                button.setToolTip(path.name)
            else:
                button.setIcon(QIcon())
                button.setText("Image required")
        if len(self._target_images) != 4 or len(self._foil_images) != 4:
            self.preview_result.setText(
                "Incomplete: choose four targets and four foils in Settings."
            )

    def _preview_selection_changed(self) -> None:
        selected = [button for button in self.preview_images if button.isChecked()]
        if len(selected) > 4:
            sender = self.sender()
            if isinstance(sender, QPushButton):
                sender.setChecked(False)
            selected = [button for button in self.preview_images if button.isChecked()]
        self.preview_submit.setEnabled(len(selected) == 4)
        self.preview_result.setText(
            f"{len(selected)} of 4 selected. Click again to revise a choice."
        )

    def _submit_preview(self) -> None:
        if self.settings_stack.currentIndex() == 0:
            try:
                endpoint = int(self.preview_endpoint.text().strip())
            except ValueError:
                self.preview_result.setText(
                    "Enter a whole number, including a minus sign if needed."
                )
                return
            start = min(max(1053, self.minimum_spin.value()), self.maximum_spin.value())
            estimate = (start - endpoint) / self.step_spin.value()
            self.preview_result.setText(
                f"Example estimate: {estimate:g} steps. No response is saved."
            )
        else:
            hits = sum(button.isChecked() for button in self.preview_images[:4])
            self.preview_result.setText(
                f"Researcher preview: {hits}/4 targets selected. "
                "Participants receive no accuracy feedback."
            )

    def _build_project(self) -> ProjectFile:
        return apply_modifier_draft(self._project, self._definitions, self._scopes)

    def _open_advanced(self) -> None:
        if not self._save_fields():
            return
        owned = {
            task_id
            for modifier in self._project.condition_modifiers
            for task_id in [
                *modifier.pre_task_ids,
                *modifier.post_task_ids,
                modifier.baseline_task_id,
            ]
        }
        custom = self._project.model_copy(deep=True)
        custom = custom.model_copy(
            update={
                "condition_modifiers": [],
                "task_modules": [task for task in custom.task_modules if task.task_id not in owned],
                "conditions": [
                    condition.model_copy(
                        update={
                            "pre_task_bindings": [
                                binding
                                for binding in condition.pre_task_bindings
                                if binding.task_id not in owned
                            ],
                            "post_task_bindings": [
                                binding
                                for binding in condition.post_task_bindings
                                if binding.task_id not in owned
                            ],
                        }
                    )
                    for condition in custom.conditions
                ],
            }
        )
        detached = ProjectDocument(project_root=self._document.project_root, project=custom)
        dialog = ConditionTaskDialog(
            detached, condition_id=self._condition_id, parent=self, defer_apply=True
        )
        dialog.setWindowTitle("Advanced custom steps")
        dialog.header.subtitle_label.setText(
            "Edit extra instructions and questions for this condition. Modifier start/report "
            "screens remain managed by the modifier. Changes return to the pending draft."
        )
        dialog.update_shared_checkbox.hide()
        # The advanced editor applies only to the displayed condition. Give shared
        # modules private draft IDs before planning their deferred image intake.
        shared = {
            binding.task_id
            for condition in custom.conditions
            if condition.condition_id != self._condition_id
            for binding in [*condition.pre_task_bindings, *condition.post_task_bindings]
        }
        remap = {
            task.task_id: f"{task.task_id}-{uuid4().hex[:8]}"
            for task in custom.task_modules
            if task.task_id in shared
        }
        for editor in (dialog.pre_editor, dialog.post_editor):
            drafts = editor.modules()
            for module in drafts:
                module.module_id = remap.get(module.module_id, module.module_id)
                for step in module.steps:
                    options = [
                        *step.options,
                        *[option for question in step.questions for option in question.options],
                    ]
                    for option in options:
                        if option.image_path in self._asset_sources:
                            option.source_path = self._asset_sources[option.image_path]
            editor.set_modules(drafts)
        dialog._validate_draft()
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.staged_result is None:
            return
        modules, pre, post, copies = dialog.staged_result
        detached.set_condition_task_flow(
            self._condition_id, modules=modules, pre_bindings=pre, post_bindings=post
        )
        updated = detached.project
        custom_by_id = {task.task_id: task for task in updated.task_modules}
        tasks = [task for task in self._project.task_modules if task.task_id in owned]
        tasks.extend(custom_by_id.values())
        custom_conditions = {condition.condition_id: condition for condition in updated.conditions}
        conditions = []
        for condition in self._project.conditions:
            edited = custom_conditions[condition.condition_id]
            conditions.append(
                condition.model_copy(
                    update={
                        "pre_task_bindings": [
                            *edited.pre_task_bindings,
                            *[
                                binding
                                for binding in condition.pre_task_bindings
                                if binding.task_id in owned
                            ],
                        ],
                        "post_task_bindings": [
                            *[
                                binding
                                for binding in condition.post_task_bindings
                                if binding.task_id in owned
                            ],
                            *edited.post_task_bindings,
                        ],
                    }
                )
            )
        self._project = self._project.model_copy(
            update={"task_modules": tasks, "conditions": conditions}
        )
        self._asset_sources.update({target: source for source, target in copies})
        self._custom_edited = True
        self._set_status(
            "Custom steps updated in the draft. Apply to keep them in the experiment."
        )

    def _edit_modifier_screens(self) -> None:
        if self._selected_id is None or not self._save_fields():
            return
        definition = self._definitions[self._selected_id]
        masking = definition.modifier.kind == ConditionModifierKind.MASKING
        condition = next(
            item for item in self._project.conditions if item.condition_id == self._condition_id
        )
        if masking:
            condition = next(
                item for item in self._build_project().conditions
                if item.condition_id == self._condition_id
            )
        condition = condition.model_copy(
            update={
                "pre_task_bindings": [binding for binding in condition.pre_task_bindings
                                      if binding.task_id in definition.modifier.pre_task_ids]
                if masking else [
                    TaskBinding(task_id=task_id, replaces_condition_start_gate=True)
                    for task_id in definition.modifier.pre_task_ids
                ],
                "post_task_bindings": [binding for binding in condition.post_task_bindings
                                       if binding.task_id in definition.modifier.post_task_ids]
                if masking else [
                    TaskBinding(task_id=task_id) for task_id in definition.modifier.post_task_ids
                ],
            }
        )
        detached = ProjectDocument(
            project_root=self._document.project_root,
            project=self._project.model_copy(
                update={
                    "task_modules": definition.task_modules,
                    "condition_modifiers": [definition.modifier],
                    "conditions": [condition],
                },
                deep=True,
            ),
        )

        def validate_screens(
            modules: list[TaskModule],
            pre: list[TaskBinding],
            post: list[TaskBinding],
        ) -> None:
            if (
                [binding.task_id for binding in pre] != definition.modifier.pre_task_ids
                or [binding.task_id for binding in post] != definition.modifier.post_task_ids
                or pre != condition.pre_task_bindings
                or post != condition.post_task_bindings
            ):
                raise ValueError(
                    "Keep the linked modifier modules in their original phases and occurrences. "
                    "Add other content in Advanced custom steps."
                )
            candidate = ModifierDefinition(modifier=definition.modifier, task_modules=modules)
            if not masking:
                validate_image_memory_definition(candidate, allow_incomplete=True)

        dialog = ConditionTaskDialog(
            detached,
            condition_id=self._condition_id,
            parent=self,
            defer_apply=True,
            staged_validator=validate_screens,
        )
        dialog.setWindowTitle("Edit masking screens" if masking else "Edit image-memory screens")
        dialog.header.subtitle_label.setText(
            "Edit the instructions, visibility, target identity and frequency screens. "
            "Keep target response values consistent with Native sources → Target answer."
            if masking else
            "Edit instructions, fonts and layouts. Keep one study screen and one recognition "
            "screen with four targets, four foils and an explicit four-choice Submit response."
        )
        dialog.update_shared_checkbox.hide()
        for editor in (dialog.pre_editor, dialog.post_editor):
            drafts = editor.modules()
            for module in drafts:
                for step in module.steps:
                    for option in step.options:
                        if option.image_path in self._asset_sources:
                            option.source_path = self._asset_sources[option.image_path]
            editor.set_modules(drafts)
        dialog._validate_draft()
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.staged_result is None:
            return
        modules, _pre, _post, copies = dialog.staged_result
        self._definitions[self._selected_id] = ModifierDefinition(
            modifier=definition.modifier,
            task_modules=modules,
        )
        self._asset_sources.update({target: source for source, target in copies})
        self._refresh_list(self._selected_id)
        self._set_status(
            "Modifier screens updated in the draft. Apply keeps these experiment edits."
        )

    def _save_preset(self) -> None:
        if self._selected_id is None or self._fpvs_root is None or not self._save_fields():
            return
        definition = self._definitions[self._selected_id].model_copy(deep=True)
        image_count = sum(len(task_image_references(task)) for task in definition.task_modules)
        image_count += len(modifier_image_references(definition.modifier))
        dialog = SaveModifierPresetDialog(
            name=definition.modifier.name,
            description=definition.modifier.description,
            image_count=image_count,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        root = self._fpvs_root
        source_root = self._document.project_root
        sources = dict(self._asset_sources)
        name = dialog.name_edit.text().strip()
        description = dialog.description_edit.toPlainText().strip()
        self._run_job(
            lambda: save_modifier_preset(
                root,
                definition,
                source_root,
                name=name,
                description=description,
                asset_sources=sources,
            ),
            lambda _value: self._set_status("Saved locally; project changes are still pending."),
            "Saving the local preset and its images…",
        )

    def accept(self) -> None:
        if self._active_task is not None or not self._save_fields():
            return
        try:
            draft = self._build_project()
        except ValueError as error:
            self._show_error(error)
            return
        project_root = self._document.project_root
        sources = dict(self._asset_sources)

        def applied(value: object) -> None:
            self._document.apply_condition_modifier_project(cast(ProjectFile, value))
            super(ConditionModifierDialog, self).accept()

        self._run_job(
            lambda: apply_modifier_project(project_root, draft, asset_sources=sources),
            applied,
            "Validating modifiers and copying project images…",
        )

    def _run_job(
        self,
        callback: Callable[[], object],
        completed: Callable[[object], None],
        message: str,
    ) -> None:
        if self._active_task is not None:
            return
        self._job_result = None
        self._job_error = None
        task = BackgroundTask(parent_widget=self, callback=callback)
        self._active_task = task
        self._set_busy(True)
        self._set_status(message)
        task.succeeded.connect(lambda value: setattr(self, "_job_result", value))
        task.failed.connect(lambda error: setattr(self, "_job_error", error))

        def finished() -> None:
            self._active_task = None
            self._set_busy(False)
            if self._job_error is not None:
                self._show_error(self._job_error)
            else:
                completed(self._job_result)

        task.finished.connect(finished)
        task.start()

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.modifier_list,
            self.detail,
            self.add_button,
            self.remove_button,
            self.custom_button,
            self.convert_button,
            self.save_button,
            self.cancel_button,
            self.apply_button,
        ):
            widget.setEnabled(not busy)
        if not busy:
            self.detail.setEnabled(self._selected_id is not None)
            self.remove_button.setEnabled(self._selected_id is not None)
            self.save_button.setEnabled(
                self._selected_id is not None and self._fpvs_root is not None
            )

    def _set_status(self, text: str) -> None:
        self.status.setProperty("errorText", "false")
        refresh_widget_style(self.status)
        self.status.setText(text if len(text) <= 300 else text[:297] + "…")
        self.status.setToolTip(text)

    def _show_error(self, error: object) -> None:
        self._set_status(str(error))
        mark_error_text(self.status)

    def reject(self) -> None:
        if self._active_task is None:
            super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._active_task is not None:
            event.ignore()
        else:
            super().closeEvent(event)
