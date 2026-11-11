# Trigger Tester serial discovery

Status: Active

The Trigger Tester opens a uniquely named BrainVision or BioSemi interface and
reports the connection check before enabling the digits. For a generic BioSemi
USB serial interface, the operator can use the configured port or identify a
reassigned port by reconnecting only that device.

- Use metadata to identify candidates. Open and close only the identified or
  configured port during the check. Require a digit action to send a trigger.
- Keep detection and manual selections in the dialog. Use the saved recording
  port and baud rate during acquisition.
- Check metadata filtering, ambiguous reconnects, connection errors, digit sends,
  and configured BioSemi, BrainVision, and parallel paths in the relevant test scopes.
- Run the [visible smoke path](../../GUI_WORKFLOW.md#trigger-tester) on Windows
  and verify receipt in ActiView and BrainVision Recorder with physical hardware.
