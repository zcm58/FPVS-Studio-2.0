"""Fit research workbook cells without a GUI or changing their recorded values.

Excel does not calculate AutoFit dimensions when an XLSX is written by openpyxl.
Conservative character widths provide portable dimensions, with word wrapping,
explicit line breaks and the cell's font size included in row-height calculation.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from functools import lru_cache
from typing import Any

from openpyxl.styles import Alignment, Font  # type: ignore[import-untyped]
from openpyxl.utils import get_column_letter  # type: ignore[import-untyped]
from openpyxl.worksheet.hyperlink import Hyperlink  # type: ignore[import-untyped]

MIN_COLUMN_WIDTH = 8.0
PREFERRED_MAX_COLUMN_WIDTH = 80.0
MAX_COLUMN_WIDTH = 255.0
MAX_ROW_HEIGHT = 409.0
_COLUMN_PADDING = 3.0
_ROW_PADDING = 6.0
_MIN_ROW_HEIGHT = 18.0
_DEFAULT_FONT_SIZE = 11.0
_WRAP_CACHE_ENTRIES = 1024
_WRAP_CACHE_MAX_TEXT = 512
_TOKENS = re.compile(r"\S+|\s+")
_DECIMALS = re.compile(r"[0#?][.]([0#?]+)")
_FULL_TEXT_SHEET = "Full Text"
_FULL_TEXT_MARKER = "FPVSFullTextV1"
_NOTES_MARKER = "FPVSFitNotesV1"
_FULL_TEXT_HEADER = ["Sheet", "Cell", "Part", "Parts", "Text"]
_FULL_TEXT_NOTE_TOPIC = "Full text (Excel limits)"
_FULL_TEXT_NOTE_PATTERN = re.compile(
    r"^\d+ cells exceed Excel's visible cell limits\. Follow their links to "
    r"Full Text for complete numbered parts; original values are retained\.$",
)
_LINE_ENDINGS = re.compile(r"\r\n|\r|\n|[^\r\n]")


@dataclass(frozen=True, slots=True)
class _MeasuredCell:
    coordinate: str
    row: int
    column: int
    text: str
    size: float
    scale: float
    wrap: bool

    @property
    def natural_width(self) -> float:
        return max((_text_width(line) for line in self.text.split("\n")), default=0) * self.scale

    def height(self, width: float, wrapped_lines: Callable[[str, float], int]) -> float:
        available = max(1.0, (width - _COLUMN_PADDING) / self.scale)
        text_lines = self.text.split("\n")
        if self.wrap:
            lines = sum(
                wrapped_lines(line, available)
                if len(line) <= _WRAP_CACHE_MAX_TEXT else _wrapped_lines(line, available)
                for line in text_lines
            )
        else:
            lines = len(text_lines)
        return max(_MIN_ROW_HEIGHT, lines * self.size * 1.5 + _ROW_PADDING)


@lru_cache(maxsize=512)
def _character_width(character: str) -> float:
    """Estimate glyph width in default-font digit units."""

    if unicodedata.combining(character):
        return 0.0
    if character == "\t":
        return 4.0
    if unicodedata.east_asian_width(character) in {"W", "F"}:
        return 2.2
    if character in "MWmw@%&":
        return 1.6
    if character.isspace():
        return 0.65
    if character.isupper():
        return 1.15
    if character.isdigit():
        return 1.05
    if unicodedata.category(character).startswith("P"):
        return 0.75
    return 1.0


def _text_width(text: str) -> float:
    """Accumulate widths in text order to preserve the rounding of fitted dimensions."""

    width = 0.0
    for character in text:
        width += _character_width(character)
    return width


def _wrapped_lines(text: str, available: float) -> int:
    """Count greedy word wrapping, splitting a token only when it cannot fit."""

    if not text:
        return 1
    lines = 1
    used = 0.0
    spacing = 0.0
    for token in _TOKENS.findall(text):
        width = _text_width(token)
        if token.isspace():
            spacing += width
            continue
        if width <= available:
            if used and used + spacing + width > available:
                lines += 1
                used = width
            else:
                used += spacing + width
        else:
            if used:
                lines += 1
            pieces = math.ceil(width / available)
            lines += pieces - 1
            used = width - (pieces - 1) * available
        spacing = 0.0
    if not used and spacing:
        return max(1, math.ceil(spacing / available))
    return max(lines, math.ceil(_text_width(text) / available))


def _display_text(value: Any, number_format: str) -> str:
    """Use displayed precision for the neutral numeric/date formats in our exports."""

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        section = number_format.split(";")[0]
        if section not in {"General", "@"}:
            decimals = _DECIMALS.search(section)
            precision = len(decimals.group(1)) if decimals is not None else 0
            precision = min(precision, 15)
            scaled = value * 100 if "%" in section else value
            if re.search(r"[eE][+-]0", section):
                rendered = f"{scaled:.{precision}E}"
            elif any(character in section for character in "0#?"):
                grouping = "," if "," in section.split(".")[0] else ""
                rendered = format(scaled, f"{grouping}.{precision}f")
            else:
                rendered = str(value)
            if "%" in section:
                rendered += "%"
            literals = re.findall(r'"([^\"]*)"', section)
            currency = "".join(character for character in section if character in "$€£¥")
            return currency + rendered + "".join(literals)
    return str(value)


def autofit_worksheet(worksheet: Any) -> list[str]:
    """Fit every populated column and row, returning physically oversized cells.

    Long columns normally wrap at a readable width. A column grows beyond that
    preference when needed to keep a row inside Excel's 409-point height limit.
    Values, numeric formats, alignments and all other workbook content are untouched.
    The returned addresses retain their full original values even when text cannot
    fit at Excel's maximum column width and row height.
    """

    wrapped_lines = lru_cache(maxsize=_WRAP_CACHE_ENTRIES)(_wrapped_lines)
    return _fit_worksheet(worksheet, wrapped_lines)


def _fit_worksheet(worksheet: Any, wrapped_lines: Callable[[str, float], int]) -> list[str]:
    columns: dict[int, list[_MeasuredCell]] = defaultdict(list)
    for row in worksheet.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            size = float(cell.font.sz or _DEFAULT_FONT_SIZE)
            scale = (size / _DEFAULT_FONT_SIZE) * (1.12 if cell.font.bold else 1.0)
            text = _display_text(cell.value, cell.number_format)
            measured = _MeasuredCell(
                coordinate=cell.coordinate, row=cell.row, column=cell.column,
                text=text.replace("\r\n", "\n").replace("\r", "\n"),
                size=size, scale=scale, wrap=bool(cell.alignment.wrap_text),
            )
            columns[cell.column].append(measured)

    row_heights: dict[int, float] = {}
    oversized: list[_MeasuredCell] = []
    for column, cells in columns.items():
        natural = max(cell.natural_width for cell in cells) + _COLUMN_PADDING
        unwrapped = max((cell.natural_width + _COLUMN_PADDING for cell in cells if not cell.wrap),
                        default=MIN_COLUMN_WIDTH)
        width = min(MAX_COLUMN_WIDTH, max(
            MIN_COLUMN_WIDTH, min(PREFERRED_MAX_COLUMN_WIDTH, natural), unwrapped,
        ))
        while width < MAX_COLUMN_WIDTH and any(
            cell.height(width, wrapped_lines) > MAX_ROW_HEIGHT for cell in cells
        ):
            width = min(MAX_COLUMN_WIDTH, max(width + 12.0, width * 1.25))
        width = math.ceil(width * 100) / 100
        dimension = worksheet.column_dimensions[get_column_letter(column)]
        dimension.width = width
        dimension.bestFit = True
        for cell in cells:
            height = cell.height(width, wrapped_lines)
            row_heights[cell.row] = max(row_heights.get(cell.row, _MIN_ROW_HEIGHT),
                                        min(MAX_ROW_HEIGHT, math.ceil(height * 100) / 100))
            if (height > MAX_ROW_HEIGHT
                    or not cell.wrap and cell.natural_width > width - _COLUMN_PADDING):
                oversized.append(cell)
    for row, height in row_heights.items():
        worksheet.row_dimensions[row].height = height
    return [cell.coordinate for cell in sorted(oversized, key=lambda cell: (cell.row, cell.column))]


def _full_text_parts(text: str) -> list[str]:
    """Preserve exact text while bounding each display part's length and newlines."""

    parts = []
    current: list[str] = []
    characters = 0
    line_breaks = 0
    for token in _LINE_ENDINGS.findall(text):
        is_line_break = token in {"\r\n", "\r", "\n"}
        if current and (characters + len(token) > 1000 or line_breaks + is_line_break > 10):
            parts.append("".join(current))
            current = []
            characters = 0
            line_breaks = 0
        current.append(token)
        characters += len(token)
        line_breaks += is_line_break
    if current:
        parts.append("".join(current))
    return parts or [""]


def _format_display_sheet(
    worksheet: Any, *, first_row: int = 1, last_row: int | None = None,
    preserve_freeze: bool = False,
) -> None:
    """Style only the generated overflow disclosure, never its original cells."""

    for row in worksheet.iter_rows(min_row=first_row, max_row=last_row):
        for cell in row:
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.font = Font(size=11, bold=cell.row == 1)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for column in range(1, worksheet.max_column + 1):
        worksheet.column_dimensions[get_column_letter(column)].alignment = Alignment(
            horizontal="center", vertical="center", wrap_text=True,
        )
    if not preserve_freeze:
        worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions


def _remove_previous_full_text(workbook: Any) -> bool:
    if _FULL_TEXT_SHEET not in workbook.sheetnames:
        return False
    sheet = workbook[_FULL_TEXT_SHEET]
    header = list(next(sheet.iter_rows(values_only=True), ()))
    if sheet.sheet_properties.codeName != _FULL_TEXT_MARKER or header != _FULL_TEXT_HEADER:
        raise ValueError("An existing Full Text worksheet is not a generated results disclosure.")
    sources: dict[tuple[str, str], list[tuple[int, int, str]]] = defaultdict(list)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        name, coordinate, part, total, text = row
        if (not isinstance(name, str) or not isinstance(coordinate, str)
                or re.fullmatch(r"[A-Z]{1,3}[1-9]\d*", coordinate) is None
                or not isinstance(part, int) or not isinstance(total, int)
                or text is not None and not isinstance(text, str)):
            raise ValueError("The generated Full Text worksheet was edited; it was preserved.")
        sources[(name, coordinate)].append((part, total, text or ""))
    for (name, coordinate), parts in sources.items():
        if (name not in workbook.sheetnames or name == _FULL_TEXT_SHEET
                or [part for part, _total, _text in parts] != list(range(1, len(parts) + 1))
                or any(total != len(parts) for _part, total, _text in parts)):
            raise ValueError("The generated Full Text worksheet has incompatible source identity.")
        cell = workbook[name][coordinate]
        original = _display_text(cell.value, cell.number_format)
        if "".join(text for _part, _total, text in parts) != original:
            raise ValueError("The generated Full Text worksheet differs from its original value.")
        if cell.hyperlink is not None and cell.hyperlink.location:
            if cell.hyperlink.location.startswith(f"'{_FULL_TEXT_SHEET}'!"):
                cell.hyperlink = None
    workbook.remove(sheet)
    return True


def _remove_previous_full_text_note(workbook: Any) -> None:
    if "Results Notes" not in workbook.sheetnames:
        return
    notes = workbook["Results Notes"]
    rows = [row[0].row for row in notes.iter_rows(min_row=2)
            if row[0].value == _FULL_TEXT_NOTE_TOPIC
            and len(row) > 1 and isinstance(row[1].value, str)
            and _FULL_TEXT_NOTE_PATTERN.fullmatch(row[1].value)]
    for row in reversed(rows):
        notes.delete_rows(row)
    if notes.sheet_properties.codeName == _NOTES_MARKER and notes.max_row == 1:
        workbook.remove(notes)
    else:
        notes.auto_filter.ref = notes.dimensions


def autofit_workbook(workbook: Any) -> list[str]:
    """Fit all result tabs and disclose text beyond Excel's physical cell limits.

    Original values remain exact. Exceptionally long values also appear as linked,
    numbered plain-text parts on a conditional Full Text tab, where every part fits.
    Unknown or edited Full Text sheets raise rather than replacing user content.
    Returns qualified addresses of the original oversized cells, never their values.
    """

    # Reuse exact measurements only within this fit and its generated disclosures.
    wrapped_lines = lru_cache(maxsize=_WRAP_CACHE_ENTRIES)(_wrapped_lines)
    if _remove_previous_full_text(workbook):
        _remove_previous_full_text_note(workbook)
    oversized: list[tuple[Any, str]] = []
    for sheet in workbook:
        oversized.extend((sheet, coordinate) for coordinate in _fit_worksheet(sheet, wrapped_lines))
    if not oversized:
        return []

    new_notes = "Results Notes" not in workbook.sheetnames
    if new_notes:
        notes = workbook.create_sheet("Results Notes")
        notes.sheet_properties.codeName = _NOTES_MARKER
        notes.append(["Topic", "Meaning"])
    else:
        notes = workbook["Results Notes"]
    full = workbook.create_sheet(_FULL_TEXT_SHEET, workbook.sheetnames.index("Results Notes"))
    full.sheet_properties.codeName = _FULL_TEXT_MARKER
    full.append(_FULL_TEXT_HEADER)
    for source, coordinate in oversized:
        cell = source[coordinate]
        text = _display_text(cell.value, cell.number_format)
        parts = _full_text_parts(text)
        first_row = full.max_row + 1
        for part, value in enumerate(parts, 1):
            full.append([source.title, coordinate, part, len(parts), value])
        cell.hyperlink = Hyperlink(
            ref=coordinate, location=f"'{_FULL_TEXT_SHEET}'!E{first_row}",
            tooltip="Read the complete value on Full Text",
        )
    message = (
        f"{len(oversized)} cells exceed Excel's visible cell limits. Follow their links to "
        "Full Text for complete numbered parts; original values are retained."
    )
    note_row = next((row for row in notes.iter_rows(min_row=2)
                     if row[0].value == _FULL_TEXT_NOTE_TOPIC and len(row) > 1
                     and isinstance(row[1].value, str)
                     and _FULL_TEXT_NOTE_PATTERN.fullmatch(row[1].value)), None)
    if note_row is None:
        notes.append([_FULL_TEXT_NOTE_TOPIC, message])
        note_number = notes.max_row
    else:
        note_row[1].value = message
        note_number = note_row[0].row
    _format_display_sheet(full)
    _format_display_sheet(
        notes, first_row=1 if new_notes else note_number,
        last_row=None if new_notes else note_number, preserve_freeze=not new_notes,
    )
    if _fit_worksheet(full, wrapped_lines) or _fit_worksheet(notes, wrapped_lines):
        raise ValueError("A generated full-text display part exceeds Excel's visible cell limits.")
    return [f"{sheet.title}!{coordinate}" for sheet, coordinate in oversized]
