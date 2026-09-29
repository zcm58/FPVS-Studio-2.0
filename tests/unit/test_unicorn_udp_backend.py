"""Unicorn submission tests use injected sockets and never send network traffic."""

from __future__ import annotations

import socket

import pytest

from fpvs_studio.runtime.triggers import (
    LoggedTriggerBackend,
    TriggerEmissionError,
    build_trigger_backend,
)
from fpvs_studio.triggers.null_backend import NullBackend
from fpvs_studio.triggers.unicorn_udp_backend import (
    UnicornUDPBackend,
    UnicornUDPBackendError,
)


class _FakeSocket:
    def __init__(
        self,
        *,
        setup_error: Exception | None = None,
        send_error: Exception | None = None,
        close_error: Exception | None = None,
        bytes_sent: int | None = None,
    ) -> None:
        self.setup_error = setup_error
        self.send_error = send_error
        self.close_error = close_error
        self.bytes_sent = bytes_sent
        self.blocking: list[bool] = []
        self.attempts: list[tuple[bytes, tuple[str, int]]] = []
        self.close_calls = 0

    def setblocking(self, flag: bool) -> None:
        self.blocking.append(flag)
        if self.setup_error:
            raise self.setup_error

    def sendto(self, data: bytes, address: tuple[str, int]) -> int:
        self.attempts.append((data, address))
        if self.send_error:
            raise self.send_error
        return len(data) if self.bytes_sent is None else self.bytes_sent

    def close(self) -> None:
        self.close_calls += 1
        if self.close_error:
            raise self.close_error


def test_unicorn_prepares_nonblocking_socket_once_and_exact_ascii_payloads() -> None:
    fake_socket = _FakeSocket()
    calls: list[tuple[int, int]] = []

    def make_socket(family: int, kind: int) -> _FakeSocket:
        calls.append((family, kind))
        return fake_socket

    backend = UnicornUDPBackend(1200, socket_factory=make_socket)
    backend.connect()
    backend.connect()
    for code in [1, 55, 55, 127, 128, 255]:
        backend.send_trigger(code)
    backend.reset()

    assert calls == [(socket.AF_INET, socket.SOCK_DGRAM)]
    assert fake_socket.blocking == [False]
    assert fake_socket.attempts == [
        (payload, ("127.0.0.1", 1200))
        for payload in [b"1", b"55", b"55", b"127", b"128", b"255"]
    ]
    assert backend.backend_name == "unicorn_udp"
    assert backend.emits_external_markers is True
    assert backend.emits_hardware_triggers is False


@pytest.mark.parametrize("port", [0, -1, 65536, True, "1000", None, 1000.0])
def test_unicorn_rejects_invalid_ports(port: object) -> None:
    with pytest.raises(ValueError, match="1 to 65535"):
        UnicornUDPBackend(port)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", [-1, 0, 256, True, None, "55"])
def test_unicorn_rejects_invalid_event_codes_without_sending(code: object) -> None:
    fake_socket = _FakeSocket()
    backend = UnicornUDPBackend(socket_factory=lambda *_args: fake_socket)
    backend.connect()
    with pytest.raises((TypeError, ValueError), match="1 to 255"):
        backend.send_trigger(code)  # type: ignore[arg-type]
    assert fake_socket.attempts == []


def test_unicorn_prevalidated_path_uses_prepared_bytes(monkeypatch) -> None:
    fake_socket = _FakeSocket()
    backend = UnicornUDPBackend(socket_factory=lambda *_args: fake_socket)
    backend.connect()
    monkeypatch.setattr(
        "fpvs_studio.triggers.unicorn_udp_backend.validate_event_trigger_code",
        lambda _code: (_ for _ in ()).throw(AssertionError("unexpected validation")),
    )
    backend.send_prevalidated_trigger(255)
    assert fake_socket.attempts == [(b"255", ("127.0.0.1", 1000))]


@pytest.mark.parametrize("send_error", [BlockingIOError("busy"), OSError("send failed")])
def test_unicorn_logs_failed_submission_without_retry(send_error: Exception) -> None:
    fake_socket = _FakeSocket(send_error=send_error)
    backend = LoggedTriggerBackend(
        UnicornUDPBackend(socket_factory=lambda *_args: fake_socket),
        backend_name="unicorn_udp",
    )
    backend.connect()
    with pytest.raises(TriggerEmissionError, match=str(send_error)):
        backend.send_trigger(55, frame_index=5, time_s=0.25, label="oddball_onset")
    backend.close()

    assert fake_socket.attempts == [(b"55", ("127.0.0.1", 1000))]
    assert fake_socket.close_calls == 1
    record, = backend.records
    assert (record.code, record.frame_index, record.time_s) == (55, 5, 0.25)
    assert record.backend_name == "unicorn_udp"
    assert record.status == "error"
    assert record.message is not None and str(send_error) in record.message


@pytest.mark.parametrize("bytes_sent", [0, 1, 3])
def test_unicorn_reports_incomplete_or_invalid_submission(bytes_sent: int) -> None:
    fake_socket = _FakeSocket(bytes_sent=bytes_sent)
    backend = UnicornUDPBackend(socket_factory=lambda *_args: fake_socket)
    backend.connect()
    with pytest.raises(UnicornUDPBackendError, match="expected 2"):
        backend.send_trigger(55)
    assert len(fake_socket.attempts) == 1


def test_unicorn_close_is_idempotent_and_reconnect_uses_new_socket() -> None:
    sockets = [_FakeSocket(), _FakeSocket()]
    unused = iter(sockets)
    backend = UnicornUDPBackend(socket_factory=lambda *_args: next(unused))
    with pytest.raises(UnicornUDPBackendError, match="not connected"):
        backend.send_trigger(1)
    backend.connect()
    backend.send_trigger(1)
    backend.close()
    backend.close()
    with pytest.raises(UnicornUDPBackendError, match="not connected"):
        backend.send_trigger(2)
    backend.connect()
    backend.send_trigger(255)
    backend.close()

    assert [item.close_calls for item in sockets] == [1, 1]
    assert [item.attempts for item in sockets] == [
        [(b"1", ("127.0.0.1", 1000))],
        [(b"255", ("127.0.0.1", 1000))],
    ]


def test_unicorn_setup_failure_closes_socket_and_preserves_cleanup_failure() -> None:
    failed = _FakeSocket(
        setup_error=OSError("nonblocking failed"), close_error=OSError("cleanup failed")
    )
    recovered = _FakeSocket()
    unused = iter([failed, recovered])
    backend = UnicornUDPBackend(socket_factory=lambda *_args: next(unused))

    with pytest.raises(UnicornUDPBackendError, match="nonblocking failed.*cleanup failed"):
        backend.connect()
    backend.close()
    backend.connect()
    backend.send_trigger(1)
    backend.close()

    assert failed.close_calls == 1
    assert recovered.attempts == [(b"1", ("127.0.0.1", 1000))]
    assert recovered.close_calls == 1


def test_unicorn_socket_creation_failure_is_explicit() -> None:
    def fail_open(*_args: int) -> _FakeSocket:
        raise OSError("socket unavailable")

    backend = UnicornUDPBackend(socket_factory=fail_open)
    with pytest.raises(UnicornUDPBackendError, match="socket unavailable"):
        backend.connect()
    backend.close()


def test_unicorn_close_failure_is_explicit_and_detaches_resource() -> None:
    fake_socket = _FakeSocket(close_error=OSError("close failed"))
    backend = UnicornUDPBackend(socket_factory=lambda *_args: fake_socket)
    backend.connect()
    with pytest.raises(UnicornUDPBackendError, match="close failed"):
        backend.close()
    backend.close()
    assert fake_socket.close_calls == 1


def test_logged_unicorn_preserves_transport_capability_and_submission_meaning() -> None:
    fake_socket = _FakeSocket()
    adapter = UnicornUDPBackend(socket_factory=lambda *_args: fake_socket)
    with pytest.raises(ValueError, match="transport identity"):
        LoggedTriggerBackend(adapter, backend_name="serial")
    backend = LoggedTriggerBackend(adapter, backend_name="unicorn_udp")
    backend.connect()
    backend.send_trigger(1, frame_index=0, label="condition_start", time_s=0.0)

    assert backend.emits_external_markers is True
    assert backend.emits_hardware_triggers is False
    assert backend.records[0].status == "sent"
    assert "unverified" in (backend.records[0].message or "")


@pytest.mark.parametrize("external", [True, False])
def test_logged_backend_rejects_inconsistent_identity_and_output_capability(external) -> None:
    class InconsistentBackend(NullBackend):
        emits_external_markers = external
        backend_name = "null" if external else "unicorn_udp"

    adapter = InconsistentBackend()
    with pytest.raises(ValueError, match="external-marker capability"):
        LoggedTriggerBackend(adapter, backend_name=adapter.backend_name)


@pytest.mark.parametrize("mode", ["experiment_test_mode", "pilot_mode"])
@pytest.mark.parametrize("selected", [None, "serial", "unicorn_udp"])
def test_runtime_test_and_pilot_never_construct_external_adapters(
    monkeypatch, mode: str, selected: str | None,
) -> None:
    def unexpected_adapter(*_args, **_kwargs):
        raise AssertionError("test/pilot must not construct an external adapter")

    monkeypatch.setattr("fpvs_studio.runtime.triggers.SerialBackend", unexpected_adapter)
    monkeypatch.setattr("fpvs_studio.runtime.triggers.UnicornUDPBackend", unexpected_adapter)
    backend, _ = build_trigger_backend(
        {mode: True, "serial_enabled": True, "recording_backend": selected}
    )
    backend.connect()
    backend.send_trigger(55)
    assert backend.backend_name == "null"
    assert backend.records[0].status == "skipped_disabled"


def test_runtime_invalid_unicorn_port_is_blocked_before_socket_construction(monkeypatch) -> None:
    def unexpected_adapter(*_args, **_kwargs):
        raise AssertionError("invalid configuration must not construct a socket")

    monkeypatch.setattr("fpvs_studio.runtime.triggers.UnicornUDPBackend", unexpected_adapter)
    with pytest.raises(ValueError, match="UDP port"):
        build_trigger_backend({"recording_backend": "unicorn_udp", "unicorn_udp_port": 0})


@pytest.mark.parametrize("port", [1000, 1200])
def test_runtime_unicorn_factory_uses_real_adapter_with_fake_socket(monkeypatch, port) -> None:
    fake_socket = _FakeSocket()
    calls: list[tuple[int, int]] = []

    def make_socket(family: int, kind: int):
        calls.append((family, kind))
        return fake_socket

    monkeypatch.setattr(
        "fpvs_studio.triggers.unicorn_udp_backend.socket.socket", make_socket
    )
    options = {
        "recording_backend": "unicorn_udp", "unicorn_udp_port": port, "serial_enabled": False,
    }
    backend, warnings = build_trigger_backend(options)
    assert calls == []
    backend.connect()
    backend.send_trigger(255)
    backend.close()

    assert calls == [(socket.AF_INET, socket.SOCK_DGRAM)]
    assert warnings == []
    assert backend.backend_name == "unicorn_udp"
    assert fake_socket.attempts == [(b"255", ("127.0.0.1", port))]
    assert fake_socket.close_calls == 1
