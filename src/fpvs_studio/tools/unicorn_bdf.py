"""Read the sample-aligned diagnostics in Unicorn Recorder's classic BDF files."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from os import SEEK_END
from pathlib import Path

_HEADER_SIZE = 256
_SIGNAL_HEADER_SIZE = 256
_SAMPLE_SIZE = 3
_SIGNAL_NAMES = {"status", "cnt", "valid"}


@dataclass(frozen=True, slots=True)
class UnicornBdf:
    """Integrity positions are zero-based; a missing diagnostic channel is unknown."""

    sample_rate_hz: float
    sample_count: int
    markers: tuple[tuple[int, int], ...]
    counter_discontinuities: tuple[int, ...] | None
    invalid_samples: tuple[int, ...] | None


@dataclass(frozen=True, slots=True)
class _Signal:
    offset: int
    samples: int
    physical_min: float
    physical_max: float
    digital_min: int
    digital_max: int

    @property
    def scale(self) -> float:
        return (self.physical_max - self.physical_min) / (self.digital_max - self.digital_min)

    def read(self, record: bytes, sample: int) -> int:
        start = self.offset + _SAMPLE_SIZE * sample
        return int.from_bytes(record[start : start + _SAMPLE_SIZE], "little", signed=True)


def read_unicorn_bdf(path: Path) -> UnicornBdf:
    """Return zero-based Recorder marker and integrity positions, leaving the file intact."""
    with path.open("rb") as bdf:
        header = bdf.read(_HEADER_SIZE)
        if len(header) != _HEADER_SIZE:
            raise ValueError("Truncated BDF file header.")
        if header[:8] != b"\xffBIOSEMI" or header[192:236].strip() != b"24BIT":
            raise ValueError("Expected a classic 24-bit Unicorn Recorder BDF file.")

        try:
            header_size = int(header[184:192])
            record_count = int(header[236:244])
            record_seconds = float(header[244:252])
            signal_count = int(header[252:256])
        except ValueError as exc:
            raise ValueError("Invalid numeric field in the BDF file header.") from exc
        if signal_count < 1 or header_size != _HEADER_SIZE + _SIGNAL_HEADER_SIZE * signal_count:
            raise ValueError("Invalid BDF signal header size or count.")
        if record_count < -1 or not isfinite(record_seconds) or record_seconds <= 0:
            raise ValueError("Invalid BDF data record count or duration.")

        signal_header = bdf.read(header_size - _HEADER_SIZE)
        if len(signal_header) != header_size - _HEADER_SIZE:
            raise ValueError("Truncated BDF signal header.")
        signals, record_size = _read_signals(signal_header, signal_count)
        status, counter, valid = _diagnostic_signals(signals)
        sample_rate_hz = status.samples / record_seconds
        if not isfinite(sample_rate_hz):
            raise ValueError("Invalid BDF sample rate.")

        payload_size = bdf.seek(0, SEEK_END) - header_size
        complete_records, remainder = divmod(payload_size, record_size)
        if remainder or (record_count >= 0 and complete_records < record_count):
            raise ValueError("Truncated BDF data records.")
        if record_count >= 0 and complete_records > record_count:
            raise ValueError("BDF data exceeds the declared record count.")
        if complete_records == 0:
            raise ValueError("BDF contains no data records.")
        bdf.seek(header_size)

        markers: list[tuple[int, int]] = []
        discontinuities: list[int] = []
        invalid: list[int] = []
        previous_count: int | None = None
        counter_scale = counter.scale if counter is not None else 0.0
        for record_index in range(complete_records):
            record = bdf.read(record_size)
            if len(record) != record_size:
                raise ValueError("Truncated BDF data record while reading.")
            for sample in range(status.samples):
                index = record_index * status.samples + sample
                code = status.read(record, sample)
                if not (0 <= code <= 255 and status.digital_min <= code <= status.digital_max):
                    raise ValueError(f"Invalid Unicorn Status code {code} at sample {index}.")
                # Recorder stores one event per nonzero sample, including adjacent repeats.
                if code:
                    markers.append((index, code))
                if counter is not None:
                    raw = counter.read(record, sample)
                    if not counter.digital_min <= raw <= counter.digital_max:
                        raise ValueError(f"Unicorn CNT value outside its range at sample {index}.")
                    # The header maps integers to slightly finer digital steps.
                    count = round(
                        counter.physical_min + (raw - counter.digital_min) * counter_scale
                    )
                    if previous_count is not None and count != previous_count + 1:
                        discontinuities.append(index)
                    previous_count = count
                if valid is not None:
                    flag = valid.read(record, sample)
                    if not valid.digital_min <= flag <= valid.digital_max:
                        raise ValueError(
                            f"Unicorn VALID value outside its range at sample {index}."
                        )
                    if flag != valid.digital_max:
                        invalid.append(index)

    return UnicornBdf(
        sample_rate_hz=sample_rate_hz,
        sample_count=complete_records * status.samples,
        markers=tuple(markers),
        counter_discontinuities=tuple(discontinuities) if counter is not None else None,
        invalid_samples=tuple(invalid) if valid is not None else None,
    )


def _read_signals(header: bytes, count: int) -> tuple[dict[str, _Signal], int]:
    signals: dict[str, _Signal] = {}
    offset = 0
    for index in range(count):
        try:
            label = header[16 * index : 16 * (index + 1)].decode("ascii").strip().lower()
        except UnicodeDecodeError as exc:
            raise ValueError(f"Invalid BDF label for channel {index + 1}.") from exc
        try:
            samples = int(_signal_field(header, count, index, 216))
        except ValueError as exc:
            raise ValueError(f"Invalid BDF sample count for channel {index + 1}.") from exc
        if samples <= 0:
            raise ValueError(f"Invalid BDF sample count for channel {index + 1}.")
        if label in _SIGNAL_NAMES:
            if label in signals:
                raise ValueError(f"Duplicate Unicorn BDF {label.upper()} signal.")
            try:
                signals[label] = _Signal(
                    offset,
                    samples,
                    float(_signal_field(header, count, index, 104)),
                    float(_signal_field(header, count, index, 112)),
                    int(_signal_field(header, count, index, 120)),
                    int(_signal_field(header, count, index, 128)),
                )
            except ValueError as exc:
                raise ValueError(f"Invalid Unicorn BDF {label.upper()} calibration.") from exc
        offset += _SAMPLE_SIZE * samples
    return signals, offset


def _signal_field(header: bytes, count: int, index: int, offset: int) -> bytes:
    start = offset * count + 8 * index
    return header[start : start + 8]


def _diagnostic_signals(
    signals: dict[str, _Signal],
) -> tuple[_Signal, _Signal | None, _Signal | None]:
    status = signals.get("status")
    if status is None:
        raise ValueError("Unicorn BDF is missing its Status signal.")
    for name, signal in signals.items():
        if signal.samples != status.samples:
            raise ValueError(f"Unicorn BDF {name.upper()} and Status sample counts differ.")
        if not -8388608 <= signal.digital_min < signal.digital_max <= 8388607:
            raise ValueError(f"Invalid Unicorn BDF {name.upper()} digital range.")

    if (status.physical_min, status.physical_max) != (status.digital_min, status.digital_max):
        raise ValueError("Expected identity calibration for the Unicorn Status signal.")
    counter = signals.get("cnt")
    if counter is not None and not 0 < counter.scale <= 1:
        raise ValueError("Unicorn BDF CNT calibration cannot recover integer counter values.")
    valid = signals.get("valid")
    if valid is not None and (valid.physical_min, valid.physical_max) != (0, 1):
        raise ValueError("Expected a physical range of 0 to 1 for the Unicorn VALID signal.")
    return status, counter, valid
