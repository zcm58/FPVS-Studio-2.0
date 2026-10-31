# Optional Task Recipes

Search headings or symbols here only when the scope table does not locate the
affected behavior. This is an entry-point map, not another contract or mandatory
reading list. Module paths below are relative to `src/fpvs_studio/`; test paths are
repository-relative. Select affected focused scopes, then repo precommit for shared
behavior. Qt and real hardware/service checks retain their existing approval and
evidence boundaries.

## GUI, Setup and Project Paths

| Task | First source/test | Current contract |
| --- | --- | --- |
| Shared layout, themes, no clipping | `gui/components.py`; relevant registered GUI test | [Frontend](../FRONTEND.md#no-clipping-baseline), [design guidance](../design-docs/agent-ui-design.md) |
| Eight-step Setup and Timing/Session split | `gui/setup_wizard_page.py`, `gui/runtime_settings_page.py`, `gui/session_structure_page.py` | [Setup acceptance](../GUI_WORKFLOW.md#setup-design-and-manual-acceptance) |
| Next blockers and optional description | `gui/setup_wizard_page.py`; `tests/gui/test_setup_project_details.py` | [Home/Setup flow](../GUI_WORKFLOW.md#existing-home-and-setup-flow) |
| Condition modality, sources and instructions | `gui/condition_setup_step.py`, `gui/document_conditions.py`; `tests/unit/test_condition_modality.py` | [Home/Setup flow](../GUI_WORKFLOW.md#existing-home-and-setup-flow) |
| Find Action and condition search | `gui/action_palette.py`, `gui/main_window.py`; `tests/gui/test_condition_search.py` | [Action discovery](../GUI_WORKFLOW.md#action-discovery-and-condition-search) |
| Manage Projects rename/discovery | `gui/manage_projects_dialog.py`, `gui/controller.py`, `core/project_service.py`; `tests/unit/test_project_service.py` | [Project opening/saving](../GUI_WORKFLOW.md#project-opening-and-saving) |
| Opening, hidden-page refresh and stale jobs | `gui/controller.py`, `gui/document.py`; `tests/gui/test_frontend_responsiveness.py`, `tests/gui/test_hidden_page_refresh.py` | [Responsiveness](../GUI_WORKFLOW.md#authoring-and-project-discovery-responsiveness) |
| Windows long paths and scaled display | `core/paths.py`, affected I/O caller; `tests/unit/test_bundle_open_setup.py` | [Security](../SECURITY.md), relevant [GUI workflow](../GUI_WORKFLOW.md) section |
| Retained image/AB editors and category repair | `core/experiment_design.py`, `gui/attentional_blink_stream_designer.py`, `gui/attentional_blink_character_size.py` | [Categories](../EXPERIMENT_CATEGORIES.md), [designer](../VISUAL_EXPERIMENT_DESIGNER.md) |

Use the GUI scope for interactions, project-io for persistence and core/compiler for
validation or scheduling. Preserve timing/navigation aliases and drafts. Retained
editor source is not permission to reintroduce a guided Design step. Thumbnail
caches are scoped to an update; do not cache mutable project validation across edits.

## Timing, Seeds, Tasks and Accuracy

| Task | First source/test | Current contract |
| --- | --- | --- |
| Shared/condition frequency and exact stream seconds | `core/condition_timing.py`, `gui/condition_timing_table.py` | [Run timing](../RUNSPEC.md#timing-model) |
| Presentation counts and occurrence identity | `core/session_ordering.py`, `gui/session_structure_page.py` | [Count/recovery compatibility](../SESSION_PLAN.md#presentation-count-compatibility-and-recovery) |
| Independent seeds and pending launch snapshot | `core/randomization.py`, `gui/randomization_editor.py`, document/main-window launch coordination | [Independent randomization](../SESSION_PLAN.md#independent-randomization) |
| Exact saved condition arrangements | `core/session_ordering.py`, `gui/condition_order_dialog.py` | [Saved arrangements](../SESSION_PLAN.md#saved-condition-arrangements) |
| Task numeric precision and tolerance | `core/task_models.py`, `runtime/task_runner.py`, `engines/psychopy_tasks.py`; `tests/unit/test_runtime_tasks.py` | [Task rendering](../ENGINE_INTERFACE.md#modular-task-rendering) |
| Mouse choices and handlers | `engines/psychopy_tasks.py`; `tests/unit/test_psychopy_task_mouse.py` | [Task rendering](../ENGINE_INTERFACE.md#modular-task-rendering) |
| Basic before/after questions and readable CSV | `core/post_questions.py`, `runtime/post_condition_responses.py` | [Questions](../POST_CONDITION_QUESTIONS.md) |
| Advanced modifiers and Masking | `core/condition_modifiers.py`, `core/modifier_presets.py`, `core/compiler_masking.py` | [Modifiers](../CONDITION_MODIFIERS.md), [Masking](../MASKING.md) |
| Cognitive Load baseline/counting | `core/cognitive_load_presets.py`, `core/backward_counting.py` | [Cognitive Load FPVS](../COGNITIVE_LOAD_FPVS.md) |
| Native AB rate, repeated targets and recall | `core/attentional_blink_stream.py`, `core/attentional_blink_presets.py`, `runtime/attentional_blink_report.py` | [Categories](../EXPERIMENT_CATEGORIES.md), [recall results](../RUNTIME_EXECUTION.md#attentional-blink-recall-results) |
| AB all-character markers | `core/compiler_schedules.py`, `engines/psychopy_triggers.py`, `runtime/preflight.py`; `tests/unit/test_attentional_blink_distractor_triggers.py` | [TriggerEvent](../RUNSPEC.md#triggerevent) |
| Fixation visibility and accuracy export | `gui/fixation_settings_page.py`, runtime fixation-report owner; `tests/gui/test_fixation_settings_page.py` | [Fixation accuracy](../RUNTIME_EXECUTION.md#fixation-task-accuracy-query-and-export) |
| Repeat participants and pilot/test identity | `gui/document_runtime.py`, runtime participant/session owners | [Repeat visits](../RUNTIME_EXECUTION.md#repeat-participant-sessions), [AB pilot](../RUNTIME_EXECUTION.md#ab-pilot-execution-identity) |

Use core/compiler for realization, runtime for sequencing/scoring and engine for
rendering. Keep task clocks outside FPVS frames and preserve compiled provenance.
AB's opted-in frame -1 marker is an explicit neutral flip; it is not a scheduling
fallback. Software mouse/input checks do not replace visible presentation acceptance.

## Recording, Recovery and Native Lifetime

| Task | First source/test | Current contract |
| --- | --- | --- |
| Computer default/project EEG selection | `gui/recording_dialog.py`, `gui/document.py`, `gui/controller.py`, `runtime/recording.py` | Relevant [GUI workflow](../GUI_WORKFLOW.md) recording section |
| BioSemi selected-port checks | `gui/biosemi_port_selector.py`, `triggers/serial_port_access.py` | [Trigger behavior](../RUNTIME_EXECUTION.md#trigger-behavior) |
| ActiveThree/TriggerBox discovery and pulse limits | `core/brainproducts.py`, `triggers/brainproducts_discovery.py`, `triggers/brainproducts_backend.py`; `tests/unit/test_brainproducts_discovery.py` | [ActiveThree/TriggerBox](../RUNTIME_EXECUTION.md#biosemi-activethree-and-brain-products-triggerbox) |
| actiCHamp parallel output | `triggers/parallel_backend.py`, `triggers/parallel_discovery.py`, `gui/parallel_port_selector.py` | [Parallel output](../RUNTIME_EXECUTION.md#actichamp-parallel-port-output) |
| Unicorn Recorder readiness/UDP | `runtime/unicorn_recorder.py`, `runtime/unicorn_recorder_windows.py`, `triggers/unicorn_udp_backend.py` | [Unicorn contract](../RUNTIME_EXECUTION.md#unicorn-recorder-udp-receiver-validation-pending), active Unicorn plan |
| Completed Toolbox handoff | `core/recording_hardware.py`, `core/project_config.py`, `runtime/acquisition_evidence.py` | [Completed handoff](../RUNTIME_EXECUTION.md#completed-toolbox-handoff), active integration plan |
| Native worker cleanup/shutdown | `gui/workers.py`, `gui/update_lifecycle.py`, `gui/thread_completion.py`, `gui/qt_diagnostics.py` | [Bug reporting](../BUG_REPORTING.md) |
| Graphics crashes between conditions | `engines/psychopy_graphics_lifetime.py`, `engines/psychopy_text_screens.py` | [Engine boundary](../ENGINE_INTERFACE.md#boundary-rules) |
| Interrupted-run notice, acknowledgement and rerun | `runtime/condition_recovery.py`, `gui/condition_recovery_dialog.py` | [Interrupted conditions](../GUI_WORKFLOW.md#interrupted-conditions) |

Use triggers/runtime/GUI scopes as affected. Port detection reads metadata; explicit
access checks never write marker bytes. Recorder readiness observes process/file
activity, not marker integrity or physical timing. Do not probe the OS on the GUI
thread. Fake serial/socket tests never qualify real receiving hardware. Preserve
historical acquisition evidence and review acknowledgements independently of reruns.

Approved Qt runs isolate both INI UserScope/SystemScope QSettings paths; APPDATA alone
does not override Windows native known folders. Standalone Qt subprocesses need the
same explicit profile isolation. Refer to the Qt smoke skill before execution.

## Library, Publishing and Results

| Task | First source/test | Current contract |
| --- | --- | --- |
| Catalog/enrollment/startup lab code | `library/client.py`, `gui/library_access_dialog.py`, `gui/application.py` | [Service/access](../EXPERIMENT_LIBRARY.md#service-and-access-boundary) |
| Current-project update, backups and rollback | `core/project_bundle_update.py`, `gui/project_update_controller.py`, `gui/project_version_dialog.py` | [Version checks](../EXPERIMENT_LIBRARY.md#project-version-checks) |
| Update readiness | `data_sharing/project_updates.py`, `runtime/condition_recovery.py` | [Results update guard](../DATA_SHARING.md#library-project-updates) |
| Origin receipts and installed duplicates | `core/library_origin.py`, `core/library_installations.py`, `library/installations.py` | [Version checks](../EXPERIMENT_LIBRARY.md#project-version-checks) |
| Bundle admission, decode limits and provenance | `core/project_bundle.py`, `core/compiler_limits.py`, `preprocessing/inspection.py`, `library/provenance.py` | [Payload validation](../EXPERIMENT_LIBRARY.md#local-payload-validation), [signed evidence](../LIBRARY_ARTIFACT_PROVENANCE.md) |
| Review uploads and retained cancellation | `core/library_publish.py`, `library/submissions.py`, `gui/library_submission_controller.py` | [Project review](../EXPERIMENT_LIBRARY.md#upload-a-project-for-review), active submission plan |
| Maintainer publishing/signing | `developer/library_publisher.py`, `developer/catalog_publisher.py` | [Developer publishing](../EXPERIMENT_LIBRARY.md#developer-publishing-in-studio), [local signing](../EXPERIMENT_LIBRARY.md#local-maintainer-signing) |
| Named study enrollment and pending-scope replacement | `data_sharing/client.py`, `library/client.py`, `gui/data_sharing_controller.py` | [Operator workflow](../DATA_SHARING.md#operator-workflow) |
| Completed capture, upload retirement and offline retry | `runtime/data_sharing.py`, `data_sharing/service.py`, `data_sharing/storage.py` | [Completion/recovery](../DATA_SHARING.md#completion-and-crash-recovery), [budgets](../REPORTING_STORAGE.md) |
| Startup saved-report notice | `gui/data_sharing_controller.py`, `gui/data_sharing_dialog.py`, `gui/controller.py`; `tests/unit/test_data_sharing_gui_jobs.py` | [Private sharing](../GUI_WORKFLOW.md#private-experiment-sharing) |

Current version review supports guarded replacement of the current project and a
separate-project download. Ordinary bundle import still never replaces projects.
Preserve local identity/settings/participant data, pending-report guards and recovery
evidence. Automatic offers never install without the user's explicit action.

Use library/project-io/GUI/data-sharing/runtime scopes as affected. Credentials remain
bound to canonical origins; alias receipt comparison does not transfer tokens. Results
authorization and credentials are separate from Library access. Private sibling
`../OpenFPVS` owns website accounts/admin, grants, signing-key migration and backend
reporting; its guidance and `PROJECT_REPORTING.md` are authoritative there. Desktop
`services/results/` is only an undeployed reference. Never publish content, send reports
or email as an incidental test.

## Updater, Reports and Transfer Security

| Task | First source/test | Current contract |
| --- | --- | --- |
| Updater check/download/install handoff | `updates/helper_client.py`, `updates/helper_protocol.py`, `updates/helper_service.py`, `updates/helper_runtime.py` | [Update flow](../PACKAGING.md#in-app-update-flow) |
| Combined Download and Install UI | `gui/update_dialog.py`, `gui/updater_window.py`; `tests/unit/test_update_dialog_jobs.py` | [Update flow](../PACKAGING.md#in-app-update-flow) |
| Patch selection, verifier and sparse payload | `updates/patches.py`, `updates/cache_io.py`, `packaging/inno/patch_upgrade.iss`, `scripts/build_patch.py` | [Direct patches](../PACKAGING.md#direct-patch-releases) |
| Independent updater build/progress window | `updater_main.py`, `scripts/build_updater.ps1`, `gui/updater_window.py` | [Independent updater](../PACKAGING.md#independent-updater-build-and-installation) |
| Reviewed bug/feature reports and popup explanations | `gui/report_bug_dialog.py`, `gui/bug_report_controller.py`, `gui/error_dialogs.py`, `support/error_explanations.py` | [Bug reporting](../BUG_REPORTING.md) |
| Automatic crash consent, recovery and delivery | `support/crash_reporting.py`, `gui/crash_report_controller.py`; `tests/unit/test_automatic_crash_reporting.py`, `tests/unit/test_crash_reporting_gui_jobs.py` | [Bug reporting](../BUG_REPORTING.md), active automatic-crash plan |
| Upload/download trust and decoding | Affected transfer owner; `tests/unit/test_transfer_security.py`, `tests/unit/test_image_decode_security.py` | [Security](../SECURITY.md) |
| Atomic saves and compilation/intake efficiency | `core/serialization.py`, `core/compiler_inputs.py`, `core/compiler_tasks.py`, `preprocessing/importer.py`, `runtime/session_export.py` | Relevant run/session/runtime contract |

Use updates/packaging/GUI for updater seams. Inno owns full installed baseline/target
verification and mutation; discovery authenticates a candidate, not every installed
file. Download and Install supplies one explicit action, followed by the existing
Save gate and verified helper handoff after worker cleanup. Native installed-upgrade
acceptance uses isolated identities; passing source tests do not establish that result.

Support owns bounded/redacted local diagnostics and reviewed payloads; automatic crash
delivery has separate consent/grants. Private `../FPVS-Studio-Feedback` owns service
registration, intake and email. Its activation gates are independent of desktop code.
Keep service checks synthetic unless a specific live action is authorized.
