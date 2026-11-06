"""Plain-language error explanations independent of GUI and project contracts."""

from __future__ import annotations

import errno
import re
from dataclasses import dataclass
from zipfile import BadZipFile


@dataclass(frozen=True)
class ErrorExplanation:
    summary: str
    advice: str

    @property
    def description(self) -> str:
        return f"{self.summary}\n\n{self.advice}" if self.advice else self.summary


def describe_error(title: str, error: object) -> str:
    """Describe a failure for a label; callers retain the original diagnostics."""

    return explain_error(
        title, str(error), error=error if isinstance(error, BaseException) else None,
    ).description


def explain_error(
    title: str, message: str, *, error: BaseException | None = None, details: str = ""
) -> ErrorExplanation:
    """Use a known cause when available; never claim an unverified root cause."""
    causes: list[BaseException] = []
    current = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        causes.append(current)
        current = current.__cause__ or (
            None if current.__suppress_context__ else current.__context__
        )
    text = "\n".join([message, details, *(str(cause) for cause in causes)]).lower()
    cause_names = {type(cause).__name__ for cause in causes}
    if any(type(cause).__name__ == "ParallelPortDriverUnavailableError" for cause in causes) or (
        "an already installed, running inpout driver is required for native lpt output" in text
    ):
        return ErrorExplanation(
            "FPVS Studio couldn't access the parallel-port driver.",
            "Ensure the drivers for your parallel-port interface and a compatible InpOut "
            "driver are installed and running. Close any other app using the parallel port, "
            "then retry. Studio does not install drivers.",
        )
    triggerbox_cause = next(
        (cause for cause in causes if type(cause).__name__ == "BrainProductsTriggerBoxError"), None,
    )
    source = (
        str(triggerbox_cause) if triggerbox_cause is not None else "\n".join((message, details))
    )
    actionable = re.search(
        r"The (?i:COM)[1-9]\d* port is occupied or access was denied\.|"
        r"TriggerBox (?:"
        r"port [^\r\n]*? (?:is busy or access was denied|was not found|"
        r"did not respond in time|could not be closed)|"
        r"serial settings on [^\r\n]*? were rejected|communication on [^\r\n]*? failed|"
        r"could not (?:connect on \S+|open (?i:COM)[1-9]\d*|load its connection component|"
        r"send a marker|clear the trigger signal|"
        r"start its automatic trigger reset|finish shutting down)|"
        r"did not (?:clear the last trigger in time|accept the full marker byte|"
        r"accept the zero reset byte|finish sending the marker|finish clearing the trigger signal)|"
        r"timed out while (?:sending a marker|clearing the trigger signal)|"
        r"cannot connect because its serial support is missing|"
        r"can no longer clear trigger signals automatically|is still closing|"
        r"is not connected|cleanup did not finish)[.,]|"
        r"Two triggers are too close together\.",
        source,
    )
    if triggerbox_cause is not None or actionable is not None or (
        "brainproductstriggerboxerror" in text
        or "unable to open brain products triggerbox" in text
        or "triggerbox" in text and any(phrase in text for phrase in (
            "trigger preflight failed", "trigger output failed",
        ))
    ):
        if actionable is not None:
            triggerbox_plain = (
                source[actionable.start():].partition("Details:")[0].splitlines()[0].strip()
            )
            if _plain_message(triggerbox_plain):
                summary, separator, advice = triggerbox_plain.partition(". ")
                return ErrorExplanation(
                    summary + "." if separator else summary,
                    advice or "Check the TriggerBox connection, then try again.",
                )
        if "unable to open brain products triggerbox" in text:
            return ErrorExplanation(
                "FPVS Studio couldn't connect to the USB TriggerBox.",
                "Check the USB cable, installed TriggerBox driver and COM port in Settings > "
                "Recording. Close TriggerBox Configuration/Test IO and other apps using the "
                "port, then retry.",
            )
        return ErrorExplanation(
            "TriggerBox could not finish sending or clearing its trigger signals.",
            "Restart FPVS Studio and reconnect TriggerBox before retrying. Check any saved "
            "EEG markers because the last marker or its reset may be incomplete. "
            "Open Show Details for the failed operation.",
        )
    if "reporting lock wait timed out" in text:
        return ErrorExplanation(
            "Studio couldn't update this project's reports because another process is using them.",
            "Wait for the other save or export to finish, then try again. "
            "If it has stopped responding, close that Studio window before retrying.",
        )
    if "display refresh check timed out" in text:
        settings = (
            "macOS System Settings > Displays" if "macos system settings > displays" in text
            else "system Displays settings"
        )
        return ErrorExplanation(
            "The display refresh check took too long and was stopped.",
            "The display may not be ready or the check may have stalled. Check the selected "
            f"screen and its fixed refresh rate in {settings}, then try again.",
        )
    recorder_cause = next(
        (cause for cause in causes if type(cause).__name__ == "RecorderReadinessError"), None,
    )
    if recorder_cause is not None or "recorderreadinesserror" in text:
        readable = _plain_message(str(recorder_cause)) if recorder_cause is not None else None
        if readable:
            return ErrorExplanation(readable, "Check Recorder's recording status, then try again.")
        return ErrorExplanation(
            "Studio couldn't confirm that Unicorn Recorder is saving EEG.",
            "Recorder may be closed, idle or unable to save. Open Recorder, connect the headset "
            "and start recording before launching again.",
        )
    if "SerialBackendError" in cause_names or "serialbackenderror" in text or re.search(
        r"fpvs studio cannot detect the .+ serial port", text,
    ):
        if any(isinstance(cause, ImportError) for cause in causes) or "pyserial" in text:
            return ErrorExplanation(
                "Studio couldn't load its EEG connection component.",
                "The Studio installation may be incomplete. "
                "Repair or reinstall Studio, then retry.",
            )
        return ErrorExplanation(
            "Studio couldn't use the BioSemi trigger connection.",
            "The interface may be disconnected or its port may be unavailable. Check the USB "
            "connection and port in Recording Setup, close other apps using that port, then retry. "
            "Check saved markers if recording had already started.",
        )
    if "UnicornUDPBackendError" in cause_names or "unicornudpbackenderror" in text:
        return ErrorExplanation(
            "Studio couldn't prepare or send markers for Unicorn Recorder.",
            "The local marker connection may be unavailable. Check that Recorder is running "
            "and its marker port matches Recording Setup, then retry. "
            "Check saved markers if recording had already started.",
        )
    if "ParallelPortError" in cause_names or "parallelporterror" in text:
        if "requires windows" in text:
            return ErrorExplanation(
                "Parallel-port EEG output requires Windows.",
                "Use a Windows computer with the parallel-port interface, or select a supported "
                "recording connection in Settings > Recording.",
            )
        if "pulse overlaps" in text or "low interval is shorter" in text:
            return ErrorExplanation(
                "Two EEG markers are too close together.",
                "The previous marker has not finished clearing. Increase their spacing, or "
                "shorten the pulse only if the amplifier supports it "
                "at the selected sampling rate.",
            )
        return ErrorExplanation(
            "Studio couldn't use the parallel-port trigger connection.",
            "The interface or its driver may be unavailable. Check the connection and "
            "Recording Setup, then restart Studio and retry. Check saved markers if recording "
            "had already started.",
        )
    if "RecordingConfigurationError" in cause_names or "recordingconfigurationerror" in text:
        readable = _plain_message(message)
        return ErrorExplanation(
            readable or "The recording settings are incomplete or invalid.",
            "Open Settings > Recording, check the selected device and required values, "
            "then apply the settings and try again.",
        )
    operating_errors = [cause for cause in causes if isinstance(cause, OSError)]
    if any(
        cause.errno == errno.ENOSPC or getattr(cause, "winerror", None) == 112
        for cause in operating_errors
    ) or re.search(r"no space left on device|\[winerror 112\]|disk (?:is )?full", text):
        return ErrorExplanation(
            "There isn't enough free space to finish this action.",
            "Free some space on the destination drive, or choose another folder, then try again.",
        )
    if any(getattr(cause, "winerror", None) in (32, 33) for cause in operating_errors) or (
        re.search(r"\[winerror (?:32|33)\]|being used by another process|sharing violation", text)
    ):
        return ErrorExplanation(
            "A file or folder needed for this action is in use.",
            "Close other apps using it and try again. If this keeps happening, report the error.",
        )
    if any(cause.errno in (errno.EACCES, errno.EPERM) for cause in operating_errors) or (
        re.search(r"\[winerror 5\]|permission denied|access is denied", text)
    ):
        return ErrorExplanation(
            "FPVS Studio couldn't access a file or folder needed for this action.",
            "Access may be restricted or another app may be using it. "
            "Check folder permissions, close apps using it, "
            "or choose a writable folder, then retry.",
        )
    if any(isinstance(cause, FileNotFoundError) for cause in causes) or re.search(
        r"filenotfounderror|no such file or directory|cannot find the (?:file|path)", text
    ):
        return ErrorExplanation(
            "A file or folder needed for this action couldn't be found.",
            "It may have moved or its drive may be disconnected. Check the drive and location. "
            "Choose the correct folder or restore the missing file, then retry.",
        )
    update_integrity = "UpdateIntegrityError" in cause_names or "updateintegrityerror" in text
    corrupt_archive = any(
        isinstance(cause, BadZipFile) for cause in causes
    ) or bool(re.search(r"badzipfile|corrupt(?:ed)? archive|not a zip file|bad crc", text))
    damaged_file = corrupt_archive or bool(re.search(
        r"checksum mismatch|checksum does not match|checksum differs|"
        r"hash mismatch|sha-?256 .*did not match|"
        r"installer (?:content length|size) did not match|"
        r"installer exceeded the release asset size",
        text,
    ))
    if update_integrity and not (corrupt_archive or damaged_file and "installer" in text):
        return ErrorExplanation(
            "Studio couldn't verify this update.",
            "The release information or installed application may not match the update. "
            "Check for updates again in Update & Repair. If it still fails, "
            "use a fresh copy of the latest full installer.",
        )
    if damaged_file:
        if update_integrity or (
            "update" in title.lower() and "project update" not in title.lower()
        ):
            return ErrorExplanation(
                "The Studio update file is incomplete or doesn't match the expected download.",
                "Download the update again in Update & Repair. If it still fails, "
                "use a fresh copy of the latest full installer.",
            )
        return ErrorExplanation(
            "This experiment file is incomplete, damaged, or doesn't match the expected download.",
            "Download a fresh copy and try again. If the fresh copy also fails, report this error.",
        )
    if "UnidentifiedImageError" in cause_names or re.search(
        r"unidentifiedimageerror|cannot identify image file|image assets could not be decoded",
        text,
    ):
        return ErrorExplanation(
            "Studio couldn't read a stimulus image.",
            "The image may be damaged or use an unsupported format. Open it in an image viewer, "
            "replace or re-export it, then import it again.",
        )
    if (
        "JSONDecodeError" in cause_names
        or any(isinstance(cause, UnicodeError) for cause in causes)
        or re.search(r"jsondecodeerror|unicodedecodeerror|unicodeencodeerror|invalid json", text)
    ):
        return ErrorExplanation(
            "Studio couldn't read the data needed for this action.",
            "The file or response may be incomplete or in an unexpected format. "
            "Try a fresh copy of the file or repeat the request. "
            "If it still fails, report the error.",
        )
    if re.search(
        r"requires (?:a )?newer|newer (?:fpvs )?studio|"
        r"unsupported (?:project (?:config )?)?schema",
        text,
    ):
        return ErrorExplanation(
            "This experiment uses a format this version of FPVS Studio can't read.",
            "Check your Studio version in About, then install the latest Studio update and retry.",
        )
    if any(isinstance(cause, ImportError) for cause in causes) or re.search(
        r"modulenotfounderror|importerror|dll load failed|no module named", text
    ):
        return ErrorExplanation(
            "A component FPVS Studio needs couldn't be loaded.",
            "The installation may be incomplete or damaged. Close Studio and use Update & Repair, "
            "or reinstall the latest full installer. "
            "If it still fails, report the error.",
        )
    if any(type(cause).__name__ == "ValidationError" for cause in causes) or re.search(
        r"\d+ validation errors? for", text,
    ):
        for cause in causes:
            get_errors = getattr(cause, "errors", None)
            if type(cause).__name__ == "ValidationError" and callable(get_errors):
                for item in get_errors():
                    value = item.get("msg", "") if isinstance(item, dict) else ""
                    if isinstance(value, str) and value.startswith("Value error, "):
                        readable = _plain_message(value.removeprefix("Value error, "))
                        if readable:
                            return ErrorExplanation(readable, "Correct this value, then try again.")
        return ErrorExplanation(
            "Some experiment settings or file contents aren't valid.",
            "A required value may be missing or outside its allowed range. "
            "Review Setup or the file you selected, correct the values, then retry.",
        )
    if re.search(r"http(?: error)? (?:401|403)\b", text):
        return ErrorExplanation(
            "The online service did not allow this action.",
            "Your access may have expired or this action may need permission. "
            "Check your Library or service access, then try again. If access should be available, "
            "report the error.",
        )
    if re.search(r"service could not complete the request \([45]\d\d\)", text):
        return ErrorExplanation(
            "The online service couldn't finish this request.",
            "The service may be temporarily unavailable. Wait a moment, then try again.",
        )
    domain_cause = next((cause for cause in causes if type(cause).__name__ in {
        "LibraryError", "LibraryAuthorizationError", "ReportServiceError", "PublisherError",
    }), None)
    domain_message = _plain_message(str(domain_cause)) if domain_cause is not None else (
        _plain_message(message) if any(
            name in title.lower() for name in ("library", "publish", "report", "submit")
        ) else None
    )
    if domain_message:
        if _has_recovery(domain_message):
            return ErrorExplanation(domain_message, "")
        if "your draft is preserved" in domain_message.lower():
            return ErrorExplanation(
                domain_message, "Check the report's status before trying to send it again.",
            )
    if any(
        type(cause).__module__.startswith(("urllib.", "requests.", "httpx.")) for cause in causes
    ) or re.search(
        r"network is unreachable|name resolution|urlerror|https?connectionpool|"
        r"max retries exceeded|http(?: error)? [45]\d\d|"
        r"(?:server|online service|internet|network) .*(?:unavailable|failed|timed out)|"
        r"(?:request|download) timed out|github update check timed out",
        text,
    ):
        return ErrorExplanation(
            "FPVS Studio couldn't reach the online service.",
            "The connection may be blocked or the service may be unavailable. "
            "Check your internet connection and try again later. "
            "If the problem continues, report the error.",
        )
    if any(isinstance(cause, TimeoutError) for cause in causes) or "timed out" in text:
        return ErrorExplanation(
            "This action took too long to finish.",
            "The app or device may be busy or unresponsive. Try again once it is ready; "
            "if this keeps happening, restart Studio and report the error.",
        )
    if any(isinstance(cause, ConnectionError) for cause in causes) or re.search(
        r"connection (?:refused|reset)|could not (?:contact|connect to)", text,
    ):
        return ErrorExplanation(
            "Studio couldn't complete the connection.",
            "The device or service may be unavailable. Check that it is running and connected, "
            "then try again.",
        )
    # Existing short, actionable validation messages remain useful to the author.
    plain = _plain_message(message)
    generic = re.match(r"(?:unable|failed|error|unexpected|cannot|could not)\b", message, re.I)
    programming_error = any(
        type(cause).__name__ in {
            "AttributeError", "TypeError", "NameError", "IndexError", "KeyError", "AssertionError",
            "SyntaxError", "UnboundLocalError",
        } and str(cause) == message
        for cause in causes
    )
    if plain and not generic and not programming_error:
        return ErrorExplanation(
            plain, "" if _has_recovery(plain) else
            "Check the item or setting described above, then try again.",
        )
    operation = "finish this action"
    lowered_title = title.lower()
    if "project update" in lowered_title:
        operation = "update this experiment"
    elif "update" in lowered_title:
        operation = "complete this update"
        for keyword, action in (
            ("repair", "start Update & Repair"), ("download", "download the update"),
            ("install", "install the update"), ("check", "check for updates"),
        ):
            if keyword in lowered_title:
                operation = action
                break
    elif "participant results" in lowered_title:
        operation = "open participant results" if "open" in lowered_title else (
            "complete this participant-results action"
        )
    else:
        for keyword, action in (
            ("import", "import these files"),
            ("export", "export these files"),
            ("save", "save these changes"),
            ("launch", "start the experiment"),
            ("open", "open the selected item"),
            ("download", "download this experiment"),
            ("publish", "publish this experiment"),
            ("submit", "submit this information"),
            ("sharing", "share these results"),
            ("library", "complete this Library action"),
            ("report", "complete this report action"),
        ):
            if keyword in lowered_title:
                operation = action
                break
    return ErrorExplanation(
        f"FPVS Studio couldn't {operation}.",
        "The cause isn't clear from this error. Try again; if it still fails, report the error "
        "with its details. A note about what you did is optional.",
    )


def _plain_message(message: str) -> str | None:
    """Keep human instructions, excluding diagnostic suffixes and programming syntax."""

    plain = message.partition("Details:")[0].strip()
    if not plain or len(plain) > 1200 or re.search(
        r"\b\w*(?:Error|Exception)\b|Traceback|\[WinError |\[Errno |[{}]|"
        r"\bHTTP(?: Error)? [45]\d\d\b|"
        r"\b(?:NoneType|None|True|False)\b|object has no attribute|object at 0x|"
        r"(?:list|tuple) index out of range|name ['\"][^'\"]+['\"] is not defined|"
        r"object is not (?:iterable|callable|subscriptable)|values to unpack|"
        r"<class ['\"]|\[\s*['\"]|\[\s*\d+\s*,|"
        r"\b\w+\s*=(?!=)\s*\S+|"
        r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+(?![\w.])|\bb[\"']|"
        r"\b\w+\([^)]*\)|^['\"].*['\"]$",
        plain,
    ):
        return None
    return plain


def _has_recovery(message: str) -> bool:
    return re.search(
        r"(?:^|[.!?]\s+)(?:please )?(?:enter|choose|select|check|open|close|"
        r"connect|restart|repair|install|wait|correct|increase|reduce|try|retry|keep)\b|"
        r"\b(?:then retry|try again|before retrying)\b", message, re.I,
    ) is not None
