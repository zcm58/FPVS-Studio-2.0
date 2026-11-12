"""Verify classic BDF layout and Recorder-specific sample semantics."""

from pathlib import Path

import pytest

from fpvs_studio.tools.unicorn_bdf import UnicornBdf, read_unicorn_bdf

_DIGITAL_MAX = 8388607
_CHANNEL_LIMITS = {
    "EEG 1": (-1000, 1000, -8388608, _DIGITAL_MAX),
    "Status": (-8388608, _DIGITAL_MAX, -8388608, _DIGITAL_MAX),
    "CNT": (0, 8000000, 0, _DIGITAL_MAX),
    "VALID": (0, 1, 0, _DIGITAL_MAX),
}


def _field(value: str | int, width: int) -> bytes:
    encoded = str(value).encode("ascii")
    assert len(encoded) <= width
    return encoded.ljust(width)


def _bdf_bytes(
    labels: tuple[str, ...],
    records: tuple[tuple[tuple[int, ...], ...], ...],
    *,
    reserved: str = "24BIT",
    declared_records: int | None = None,
) -> bytes:
    first_record = records[0]
    assert len(first_record) == len(labels)
    assert all(tuple(map(len, record)) == tuple(map(len, first_record)) for record in records)
    header = b"\xffBIOSEMI" + b"".join(
        _field(value, width)
        for value, width in (
            ("X", 80), ("X", 80), ("12.11.26", 8), ("13.25.25", 8),
            (256 * (1 + len(labels)), 8), (reserved, 44),
            (len(records) if declared_records is None else declared_records, 8),
            ("0.012", 8), (len(labels), 4),
        )
    )
    limits = [_CHANNEL_LIMITS[label] for label in labels]
    fields: tuple[tuple[int, tuple[str | int, ...]], ...] = (
        (16, labels),
        (80, ("",) * len(labels)),
        (8, ("",) * len(labels)),
        (8, tuple(limit[0] for limit in limits)),
        (8, tuple(limit[1] for limit in limits)),
        (8, tuple(limit[2] for limit in limits)),
        (8, tuple(limit[3] for limit in limits)),
        (80, ("",) * len(labels)),
        (8, tuple(map(len, first_record))),
        (32, ("",) * len(labels)),
    )
    signal_header = b"".join(_field(value, width) for width, values in fields for value in values)
    data = b"".join(
        sample.to_bytes(3, "little", signed=True)
        for record in records
        for channel in record
        for sample in channel
    )
    return header + signal_header + data


def test_reads_every_marker_and_checks_integrity_across_records(tmp_path: Path) -> None:
    path = tmp_path / "run.bdf"
    raw = _bdf_bytes(
        ("EEG 1", "Status", "VALID", "CNT"),
        (
            ((-110, 20), (0, 1, 55), (_DIGITAL_MAX, _DIGITAL_MAX, 0), (10, 12, 13)),
            ((-20, 110), (55, 255, 0), (_DIGITAL_MAX, _DIGITAL_MAX, 1), (16, 0, 1)),
        ),
    )
    path.write_bytes(raw)

    assert read_unicorn_bdf(path) == UnicornBdf(
        sample_rate_hz=250,
        sample_count=6,
        markers=((1, 1), (2, 55), (3, 55), (4, 255)),
        counter_discontinuities=(3, 4),
        invalid_samples=(2, 5),
    )
    assert path.read_bytes() == raw


def test_optional_checks_are_unknown_without_the_signals(tmp_path: Path) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("Status",), (((55, 0, 55),),), declared_records=-1))

    assert read_unicorn_bdf(path) == UnicornBdf(250, 3, ((0, 55), (2, 55)), None, None)


@pytest.mark.parametrize("code", [-1, 256])
def test_rejects_out_of_range_marker(tmp_path: Path, code: int) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("Status",), (((0, code, 0),),)))

    with pytest.raises(ValueError, match=rf"Invalid Unicorn Status code {code} at sample 1"):
        read_unicorn_bdf(path)


def test_requires_status(tmp_path: Path) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("EEG 1",), (((0, 0, 0),),)))

    with pytest.raises(ValueError, match="missing its Status signal"):
        read_unicorn_bdf(path)


def test_rejects_unsynchronized_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("Status", "CNT"), (((0, 0, 0), (1, 2)),)))

    with pytest.raises(ValueError, match="CNT and Status sample counts differ"):
        read_unicorn_bdf(path)


@pytest.mark.parametrize(
    ("declared_records", "drop_bytes", "message"),
    [
        (1, 300, "Truncated BDF file header"),
        (1, 10, "Truncated BDF signal header"),
        (1, 1, "Truncated BDF data records"),
        (2, 0, "Truncated BDF data records"),
        (0, 0, "BDF data exceeds the declared record count"),
    ],
)
def test_rejects_incomplete_or_inconsistent_payload(
    tmp_path: Path, declared_records: int, drop_bytes: int, message: str
) -> None:
    path = tmp_path / "run.bdf"
    data = _bdf_bytes(("Status",), (((0, 55, 0),),), declared_records=declared_records)
    path.write_bytes(data[: len(data) - drop_bytes])

    with pytest.raises(ValueError, match=message):
        read_unicorn_bdf(path)


def test_rejects_bdf_plus_header(tmp_path: Path) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("Status",), (((0, 55, 0),),), reserved="BDF+C"))

    with pytest.raises(ValueError, match="classic 24-bit Unicorn Recorder BDF"):
        read_unicorn_bdf(path)


@pytest.mark.parametrize(
    ("offset", "field", "message"),
    [
        (236, "two", "Invalid numeric field in the BDF file header"),
        (244, "nan", "Invalid BDF data record count or duration"),
        (256 + 104, "min", "Invalid Unicorn BDF STATUS calibration"),
        (256 + 112, "100", "Expected identity calibration"),
        (256 + 216, "-1", "Invalid BDF sample count for channel 1"),
    ],
)
def test_rejects_invalid_header_fields(
    tmp_path: Path, offset: int, field: str, message: str
) -> None:
    path = tmp_path / "run.bdf"
    data = bytearray(_bdf_bytes(("Status",), (((0, 55, 0),),)))
    data[offset : offset + 8] = _field(field, 8)
    path.write_bytes(data)

    with pytest.raises(ValueError, match=message):
        read_unicorn_bdf(path)


@pytest.mark.parametrize("channel", ["CNT", "VALID"])
def test_rejects_diagnostic_sample_outside_declared_range(tmp_path: Path, channel: str) -> None:
    path = tmp_path / "run.bdf"
    path.write_bytes(_bdf_bytes(("Status", channel), (((0, 55, 0), (1, -1, 0)),)))

    with pytest.raises(ValueError, match=rf"Unicorn {channel} value outside its range at sample 1"):
        read_unicorn_bdf(path)
