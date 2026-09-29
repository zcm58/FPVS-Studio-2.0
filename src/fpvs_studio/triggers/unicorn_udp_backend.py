"""Local Unicorn Recorder datagram submission; receiver validation remains separate."""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Protocol

from fpvs_studio.core.trigger_codes import validate_event_trigger_code
from fpvs_studio.triggers.base import TriggerBackend


class UnicornUDPBackendError(RuntimeError):
    """Raised when local Unicorn marker submission or cleanup fails."""


class _DatagramSocket(Protocol):
    def setblocking(self, flag: bool) -> None: ...

    def sendto(self, data: bytes, address: tuple[str, int]) -> int: ...

    def close(self) -> None: ...


class UnicornUDPBackend(TriggerBackend):
    """Submit prepared decimal ASCII markers once to a nonblocking loopback socket.

    A successful send only reports OS submission, never Recorder availability,
    receipt, or EEG sample assignment. Runtime owns the prelaunch Recorder readiness
    check; adapter tests inject a fake socket and never contact a running Recorder.
    """

    def __init__(
        self,
        port: int = 1000,
        *,
        socket_factory: Callable[[int, int], _DatagramSocket] | None = None,
    ) -> None:
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("Unicorn UDP port must be an integer from 1 to 65535.")
        self._endpoint = ("127.0.0.1", port)
        self._socket_factory = socket_factory or socket.socket
        self._socket: _DatagramSocket | None = None
        self._payloads = {code: str(code).encode("ascii") for code in range(1, 256)}

    @property
    def emits_external_markers(self) -> bool:
        return True

    @property
    def backend_name(self) -> str:
        return "unicorn_udp"

    def connect(self) -> None:
        if self._socket is not None:
            return
        opened_socket: _DatagramSocket | None = None
        try:
            opened_socket = self._socket_factory(socket.AF_INET, socket.SOCK_DGRAM)
            opened_socket.setblocking(False)
        except Exception as exc:
            cleanup_detail = ""
            if opened_socket is not None:
                try:
                    opened_socket.close()
                except Exception as cleanup_exc:
                    cleanup_detail = f" Socket cleanup also failed: {cleanup_exc}"
            raise UnicornUDPBackendError(
                f"Unable to prepare Unicorn UDP output on {self._endpoint!r}: "
                f"{exc}.{cleanup_detail}"
            ) from exc
        self._socket = opened_socket

    def send_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        self.send_prevalidated_trigger(
            validate_event_trigger_code(code),
            frame_index=frame_index,
            label=label,
            time_s=time_s,
        )

    def send_prevalidated_trigger(
        self,
        code: int,
        *,
        frame_index: int | None = None,
        label: str | None = None,
        time_s: float | None = None,
    ) -> None:
        del frame_index, label, time_s
        if self._socket is None:
            raise UnicornUDPBackendError("Unicorn UDP trigger backend is not connected.")
        payload = self._payloads[code]
        try:
            bytes_sent = self._socket.sendto(payload, self._endpoint)
        except Exception as exc:
            raise UnicornUDPBackendError(
                f"Unable to submit Unicorn UDP trigger code {code} to "
                f"{self._endpoint!r}: {exc}"
            ) from exc
        if bytes_sent != len(payload):
            raise UnicornUDPBackendError(
                f"Unable to submit Unicorn UDP trigger code {code} to "
                f"{self._endpoint!r}: socket returned {bytes_sent!r}, "
                f"expected {len(payload)}."
            )

    def reset(self) -> None:
        """Do not send zero: receiver reset semantics have not been qualified."""

    def close(self) -> None:
        opened_socket = self._socket
        self._socket = None
        if opened_socket is not None:
            try:
                opened_socket.close()
            except Exception as exc:
                raise UnicornUDPBackendError(
                    f"Unable to close Unicorn UDP output on {self._endpoint!r}: {exc}"
                ) from exc
