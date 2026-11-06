# Trigger Tester

Status: Completed

Lab operators need to check the trigger path to BrainVision Recorder 2 or BioSemi
ActiView without launching a participant session. Add **Tools > Trigger Tester** to
the project window and reuse the installed trigger adapters. The primary action is
pressing a digit on the top row or numeric keypad. Show the matching buttons for
mouse and keyboard navigation.

- Start with the project's effective recording device and configured port, baud
  rate, pulse width or parallel address. Allow another supported output and
  temporary serial port edits in the tester.
- Run one send at a time in an app-owned worker. Reuse adapter pulse and cleanup
  behavior. Explicitly write idle for digit 0. Report Studio's send result and
  leave receiver verification to the operator.
- Use the shared native dialog theme at a 560 × 340 minimum and default size.
  Keep output settings, digit buttons, status and Close visible in ready, busy,
  missing-configuration and failure states. Disable further sends during cleanup.
- Fake transport tests cover exact payloads and cleanup. Registered GUI tests
  cover digit input, failure recovery, menu discovery and layout.
- The user manually confirmed Trigger Tester on BioSemi hardware on 2026-11-06.
  BrainVision receipt and registered Qt smoke execution remain pending.
  [Visible smoke path](../../GUI_WORKFLOW.md#trigger-tester).
