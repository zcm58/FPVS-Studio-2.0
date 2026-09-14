# Release 1.6.1

Status: Active

The user authorized packaging and GitHub publication of 1.6.1, including the native
Windows patch eligibility change and diagnostic logging. Preserve the published
1.5.3 and 1.6.0 releases. Build a full installer and direct patches from both versions
using authenticated published inventories, isolated release-1.6.1 output directories,
and the retained sanitized dependency PATH. The default branch is master.

Run packaging focused checks and repo precommit, the previously approved bounded
visible packaged smoke, isolated synthetic installer lifecycle checks, and exact
archive/delta verification. Do not replace the user's installed application. Verify
all draft GitHub asset sizes/digests before publication, then check public updater
metadata. Existing installed 1.5.3 may still offer the full installer; its original
eligibility failure remains unconfirmed. Report that limitation in release notes.
