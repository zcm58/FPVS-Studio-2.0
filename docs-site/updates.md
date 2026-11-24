# Update FPVS Studio

FPVS Studio can check GitHub Releases for newer Windows installers.

## In-App Update Check

Use:

```text
Help > Check for Updates
```

If a newer version is available for your Windows installation, save your work
and choose **Download and Install**. Studio downloads and verifies the patch or
full installer, then closes to apply the update.

## Startup Checks

FPVS Studio also runs one quiet update check shortly after the Welcome window
opens. It stays quiet unless a newer version is available.

## Manual Update

You can also download the latest installer from the
[GitHub Releases page](https://github.com/zcm58/FPVS-Studio-2.0/releases/latest).

Run the new installer over the existing installation. Your projects, templates,
run history, and logs are stored outside the install folder and should remain in
place.

## Projects With Repeat Participant Sessions

Repeat participant sessions are available in FPVS Studio **1.5.3 and later**.
Update any computer that shares a project and still runs a version earlier than
1.5.3. Existing projects keep repeat sessions disabled until you enable
**Setup > Project > Allow repeat participant sessions** and save.

See [Returning Participants](run-session.md#returning-participants) for the launch
confirmation, separate session folders, and numbered CSV/Excel summaries.

## If the Check Fails

If the in-app check cannot reach GitHub, try again later or open the releases
page in a browser. Some lab networks block GitHub downloads.
