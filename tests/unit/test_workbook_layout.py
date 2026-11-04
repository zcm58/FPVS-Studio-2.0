"""Content-based dimensions keep regenerated research tables readable."""

from __future__ import annotations

import hashlib
from copy import copy

import pytest
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font

from fpvs_studio.runtime.workbook_layout import (
    MAX_COLUMN_WIDTH,
    MAX_ROW_HEIGHT,
    PREFERRED_MAX_COLUMN_WIDTH,
    autofit_workbook,
    autofit_worksheet,
)


def _sheet(rows):
    sheet = Workbook().active
    for row in rows:
        sheet.append(row)
    for row in sheet:
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for cell in sheet[1]:
        cell.font = Font(size=11, bold=True)
    return sheet


def test_new_result_grows_columns_and_multiline_rows_without_changing_data(tmp_path):
    sheet = _sheet([["Participant", "Answer"], ["0007", "Yes"]])
    assert autofit_worksheet(sheet) == []
    previous_width = sheet.column_dimensions["B"].width
    previous_height = sheet.row_dimensions[2].height
    sheet.append(["0008", "First line\nA considerably longer second answer line\nThird line"])
    for cell in sheet[3]:
        cell.alignment = copy(sheet[2][cell.column - 1].alignment)
    before = [[(cell.value, cell.data_type, copy(cell.alignment)) for cell in row] for row in sheet]
    assert autofit_worksheet(sheet) == []
    assert sheet.column_dimensions["B"].width > previous_width
    assert sheet.row_dimensions[3].height > previous_height
    assert before == [
        [(cell.value, cell.data_type, copy(cell.alignment)) for cell in row] for row in sheet
    ]
    path = tmp_path / "fitted.xlsx"
    sheet.parent.save(path)
    saved = load_workbook(path)
    try:
        assert saved.active["A2"].value == "0007"
        assert saved.active.column_dimensions["B"].bestFit
        assert saved.active.row_dimensions[3].height == sheet.row_dimensions[3].height
    finally:
        saved.close()


def test_headers_wide_unicode_and_unbroken_identifiers_all_contribute_to_fit():
    sheet = _sheet([
        ["Mean Reaction Time Across All Conditions (ms)", "Text", "Identifier"],
        [12.3456, "漢字漢字漢字漢字漢字漢字漢字漢字漢字漢字", "W" * 130],
    ])
    assert autofit_worksheet(sheet) == []
    assert sheet.column_dimensions["A"].width > 45
    assert sheet.column_dimensions["B"].width > 40
    assert sheet.row_dimensions[2].height > 25
    assert sheet.column_dimensions["C"].width <= PREFERRED_MAX_COLUMN_WIDTH
    assert sheet["C2"].value == "W" * 130


def test_number_formats_measure_displayed_precision_without_changing_numeric_values():
    sheet = _sheet([["RT", "Percent", "Identifier"], [123456789.0, 0.123456, "0000007"]])
    sheet["A2"].number_format = "#,##0.000"
    sheet["B2"].number_format = "0.00%"
    before = [(cell.value, cell.number_format, cell.data_type) for cell in sheet[2]]
    assert autofit_worksheet(sheet) == []
    assert sheet.column_dimensions["A"].width > 16
    assert sheet.column_dimensions["B"].width < 12
    assert before == [(cell.value, cell.number_format, cell.data_type) for cell in sheet[2]]


def test_long_seed_list_expands_past_preferred_width_to_avoid_height_clipping():
    seeds = "; ".join(f"run-{index:03d}-condition-name-{'a' * 24}=123456789" for index in range(36))
    sheet = _sheet([["Image Display Order Seeds"], [seeds]])
    assert len(seeds) > 2000
    assert autofit_worksheet(sheet) == []
    assert PREFERRED_MAX_COLUMN_WIDTH < sheet.column_dimensions["A"].width <= MAX_COLUMN_WIDTH
    assert 100 < sheet.row_dimensions[2].height <= MAX_ROW_HEIGHT
    assert sheet["A2"].value == seeds


def test_extreme_text_reports_excel_limit_without_losing_any_characters():
    value = "漢" * 20000
    sheet = _sheet([["Answer"], [value]])
    assert autofit_worksheet(sheet) == ["A2"]
    assert sheet.column_dimensions["A"].width == MAX_COLUMN_WIDTH
    assert sheet.row_dimensions[2].height == MAX_ROW_HEIGHT
    assert sheet["A2"].value == value


@pytest.mark.parametrize("point_size", [11, 20])
def test_explicit_lines_and_font_size_determine_height(point_size):
    sheet = _sheet([["Question"], ["One\n\nThree\nFour"]])
    sheet["A2"].font = Font(size=point_size)
    assert autofit_worksheet(sheet) == []
    assert sheet.row_dimensions[2].height >= point_size * 1.5 * 4 + 6


@pytest.mark.parametrize("text", [
    "=literal formula text " + "漢" * (16384 - len("=literal formula text ")),
    "first\n" + "\n\n" * 7000 + "last",
], ids=["wide_text", "line_breaks"])
def test_valid_long_answers_have_complete_linked_display_parts(tmp_path, text):
    sheet = _sheet([["Answer"], [text]])
    sheet["A2"].data_type = "s"
    book = sheet.parent
    assert autofit_workbook(book) == ["Sheet!A2"]
    assert sheet["A2"].value == text
    assert sheet["A2"].hyperlink.location == "'Full Text'!E2"
    full = book["Full Text"]
    rows = list(full.iter_rows(min_row=2, values_only=True))
    assert "".join(row[4] for row in rows) == text
    assert [row[2] for row in rows] == list(range(1, len(rows) + 1))
    assert all(row[3] == len(rows) for row in rows)
    assert all(len(row[4]) <= 1000 for row in rows)
    assert autofit_worksheet(full) == []
    assert all(row.height <= MAX_ROW_HEIGHT for row in full.row_dimensions.values())
    assert all(cell.data_type == "s" for row in full.iter_rows(min_row=2)
               for cell in row if isinstance(cell.value, str))
    assert any("complete numbered parts" in str(cell.value)
               for row in book["Results Notes"] for cell in row)
    path = tmp_path / "linked.xlsx"
    book.save(path)
    saved = load_workbook(path)
    try:
        assert len(saved["Sheet"]["A2"].value) == len(text)
        assert hashlib.sha256(saved["Sheet"]["A2"].value.encode()).hexdigest() == hashlib.sha256(
            text.encode(),
        ).hexdigest()
        assert saved["Sheet"]["A2"].hyperlink.location == "'Full Text'!E2"
        assert "".join(row[4] for row in saved["Full Text"].iter_rows(
            min_row=2, values_only=True,
        )) == text
        assert autofit_workbook(saved) == ["Sheet!A2"]
        assert saved.sheetnames.count("Full Text") == 1
    finally:
        saved.close()


def test_workbook_without_overflow_does_not_add_disclosure_tabs():
    sheet = _sheet([["Question", "Answer"], ["Choose one", "Yes"]])
    assert autofit_workbook(sheet.parent) == []
    assert sheet.parent.sheetnames == ["Sheet"]


def test_custom_full_text_sheet_is_never_overwritten():
    sheet = _sheet([["Answer"], ["漢" * 20000]])
    custom = sheet.parent.create_sheet("Full Text")
    custom["A1"] = "Researcher notes"
    with pytest.raises(ValueError, match="not a generated"):
        autofit_workbook(sheet.parent)
    assert custom["A1"].value == "Researcher notes"


def test_crlf_display_parts_reconstruct_exact_raw_text_in_memory():
    text = "first\r\n" + "\n\r\n" * 5000 + "last"
    sheet = _sheet([["Answer"], [text]])
    assert autofit_workbook(sheet.parent) == ["Sheet!A2"]
    parts = [row[4] for row in sheet.parent["Full Text"].iter_rows(min_row=2, values_only=True)]
    assert sheet["A2"].value == text
    assert "".join(parts) == text
    assert not any(left.endswith("\r") and right.startswith("\n")
                   for left, right in zip(parts[:-1], parts[1:], strict=True))


def test_repeated_fit_removes_obsolete_generated_disclosure_preserving_notes():
    sheet = _sheet([["Answer"], ["A short value"]])
    sheet["A2"].font = Font(size=400)
    notes = sheet.parent.create_sheet("Results Notes")
    notes.append(["Topic", "Meaning"])
    notes.append(["Original note", "Keep this interpretation unchanged"])
    notes.freeze_panes = "C3"
    notes["B2"].alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    original_alignment = copy(notes["B2"].alignment)
    assert autofit_workbook(sheet.parent) == ["Sheet!A2"]
    assert notes.freeze_panes == "C3"
    assert copy(notes["B2"].alignment) == original_alignment
    sheet["A2"].font = Font(size=11)
    assert autofit_workbook(sheet.parent) == []
    assert "Full Text" not in sheet.parent.sheetnames
    assert sheet["A2"].hyperlink is None
    assert list(notes.values) == [
        ("Topic", "Meaning"), ("Original note", "Keep this interpretation unchanged"),
    ]
    assert notes.freeze_panes == "C3"
