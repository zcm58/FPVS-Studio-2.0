# Update FPVS Studio

FPVS Studio can check GitHub Releases for newer Windows installers.

## In-App Update Check

Use:

```text
File > Check for Updates
```

If a newer version is available, FPVS Studio shows the current version, the
latest version, and a short release summary. Choose **Download Update** to
download the installer.

After the download, FPVS Studio asks before closing the app and starting the
installer.

## Startup Checks

FPVS Studio also runs one quiet update check shortly after the Welcome window
opens. It stays quiet unless a newer version is available.

## Manual Update

You can also download the latest installer from the
[GitHub Releases page](https://github.com/zcm58/FPVS-Studio-2.0/releases/latest).

Run the new installer over the existing installation. Your projects, templates,
run history, and logs are stored outside the install folder and should remain in
place.

## If the Check Fails

If the in-app check cannot reach GitHub, try again later or open the releases
page in a browser. Some lab networks block GitHub downloads.
