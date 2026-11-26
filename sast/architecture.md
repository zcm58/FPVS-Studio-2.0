# FPVS Studio security architecture

## Technology stack

| Component | Implementation |
| --- | --- |
| Desktop | Python 3.10, PySide6, Pydantic, Pillow, NumPy and openpyxl. Hatchling builds the Python package. Dependencies are specified in `pyproject.toml`. |
| Acquisition | PsychoPy renders compiled schedules. Device adapters use serial, parallel or UDP output. |
| Persistence | The active project holds JSON, stimulus assets, CSV, Excel workbooks and a SQLite study history. Project-local reporting sidecars retain enrollment settings and queued results. The user profile holds machine preferences and update caches. |
| Release | GitHub Actions runs source and installer checks. PyInstaller and Inno Setup build the Windows application and updater. PowerShell and shell scripts support source installs. |
| Services | The desktop talks to OpenFPVS Library and Results, Feedback, and GitHub Releases. The JavaScript worker and SQL migrations under `services/results/` are a reference implementation. Production services have separate owners. |

## Architecture overview

The GUI delegates project I/O and compilation to core. Runtime executes the resulting
run and session plans, calls the presentation engine and records responses. The
desktop process normally acts with the operator's OS permissions. The independent
updater has a separate entry point and install handoff. The repository's
[architecture guide](../ARCHITECTURE.md) identifies the owners of each boundary.

## Data flow and entry points

| Entry | Authority | Data flow |
| --- | --- | --- |
| `fpvs-studio` | Local operator | Opens or imports a project, validates its models and media, compiles schedules and starts a visit. |
| Presentation and export | Local recording setup | Responses and device observations enter runtime. Runtime writes study records and exports for the operator and Toolbox. |
| Library and Results clients | Public catalog or an enrolled device | Library metadata selects verified downloads. Results consent and enrollment govern report capture, outbox delivery and receipt handling. |
| Support reports | Per-workflow reporting settings or operator review | Diagnostics are filtered for the intended report and delivered through Feedback. |
| Independent updater | Installed Windows application and explicit install action | Release metadata identifies a candidate. The helper verifies and hands the installer to Inno. |

## Trust boundaries

Project and archive contents cross into the operator's filesystem during import and
replacement. Participant input crosses into durable study records during recording
and export. Optional uploads cross from local storage to a remote service under a
service-specific identity. Updater downloads cross from remote content into
executable files. The installer, hardware drivers, OS credential store and deployed
web services have their own execution and permission boundaries.

## Sensitive data inventory

| Data | Location and access | Protection |
| --- | --- | --- |
| Participant identifiers, demographics, answers and acquisition records | Study folders, workbooks and explicit handoffs | Operator-controlled local filesystem and workflow-specific export boundaries |
| Reporting payloads and receipts | Project reporting state and local outboxes | Enrollment scope, reporting settings and receipt verification |
| Device and service credentials | User-specific credential store | OS-backed protection and separate service namespaces |
| Diagnostic information | Local logs and selected report payloads | Bounded collection, redaction and reporting controls |
