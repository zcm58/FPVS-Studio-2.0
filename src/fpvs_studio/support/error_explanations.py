"""Plain-language error explanations independent of GUI and project contracts."""

from __future__ import annotations

import errno
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorExplanation:
    summary: str
    advice: str

    @property
    def description(self) -> str:
        return f"{self.summary}\n\n{self.advice}" if self.advice else self.summary


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
            "Check that the folder is writable and the drive is connected. "
            "Close apps using it, or choose a folder you can write to, then try again.",
        )
    if any(isinstance(cause, FileNotFoundError) for cause in causes) or re.search(
        r"filenotfounderror|no such file or directory|cannot find the (?:file|path)", text
    ):
        return ErrorExplanation(
            "A file or folder needed for this action couldn't be found.",
            "Check that the drive is connected and the files haven't moved. "
            "Choose the correct folder or download the experiment again, then retry.",
        )
    if re.search(
        r"badzipfile|checksum mismatch|checksum does not match|checksum differs|"
        r"hash mismatch|corrupt(?:ed)? archive|not a zip file|bad crc",
        text,
    ):
        return ErrorExplanation(
            "This experiment file is incomplete, damaged, or doesn't match the expected download.",
            "Download a fresh copy and try again. If the fresh copy also fails, report this error.",
        )
    if re.search(
        r"requires (?:a )?newer|newer (?:fpvs )?studio|unsupported (?:project )?schema", text
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
            "Close Studio and use Update & Repair, or reinstall the latest full installer. "
            "If it still fails, report the error.",
        )
    if any(isinstance(cause, (TimeoutError, ConnectionError)) for cause in causes) or re.search(
        r"timed out|connection (?:refused|reset)|network is unreachable|"
        r"name resolution|unable to reach|could not (?:contact|connect to)|"
        r"urlerror|http error (?:502|503|504)",
        text,
    ):
        return ErrorExplanation(
            "FPVS Studio couldn't reach the online service.",
            "Check your internet connection and try again later. "
            "If the problem continues, report the error.",
        )
    if any(type(cause).__name__ == "ValidationError" for cause in causes) or re.search(
        r"\d+ validation errors? for", text
    ):
        return ErrorExplanation(
            "Some experiment settings or file contents aren't valid.",
            "Open Show Details to see which values need attention. "
            "If an unedited Library download fails, report this error.",
        )
    # Existing short, actionable validation messages remain useful to the author.
    generic = re.match(r"(?:unable|failed|error|unexpected|cannot|could not)\b", message, re.I)
    if not generic and len(message) <= 1200 and message.strip():
        return ErrorExplanation(message, "If you need help with this error, use the report button.")
    operation = "finish this action"
    for keyword, action in (
        ("import", "import these files"),
        ("export", "export these files"),
        ("save", "save these changes"),
        ("launch", "start the experiment"),
        ("open", "open this experiment"),
        ("download", "download this experiment"),
    ):
        if keyword in title.lower():
            operation = action
            break
    return ErrorExplanation(
        f"FPVS Studio couldn't {operation}.",
        "Try again. If it still fails, use Report this bug. Please! "
        "The report will include the error details; a note about what you did is optional.",
    )
