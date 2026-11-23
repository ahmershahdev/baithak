"""Virus scanning through clamd's INSTREAM command over TCP (clamd.conf(5)): the file goes as
chunks, each after its length as 4 big-endian bytes, then a zero length; clamd answers one line
ending in a null byte."""

import socket
from dataclasses import dataclass

from django.conf import settings

from apps.core import files as file_rules

SEND = 64 * 1024
# The standard antivirus test file (eicar.org); harmless, and every scanner flags it. Kept in
# two parts so antivirus on a developer's machine doesn't quarantine this source file.
EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$" + b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class ScanUnavailable(Exception):
    """clamd could not be reached or could not answer; the scan is tried again later."""


@dataclass(frozen=True)
class Verdict:
    clean: bool
    detail: str = ""


def _clamd(data: bytes) -> Verdict:
    try:
        with socket.create_connection(
            (settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=settings.CLAMAV_TIMEOUT
        ) as connection:
            connection.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), SEND):
                piece = data[start : start + SEND]
                connection.sendall(len(piece).to_bytes(4, "big") + piece)
            connection.sendall(b"\0\0\0\0")
            reply = b""
            while not reply.endswith(b"\0"):
                received = connection.recv(4096)
                if not received:
                    break
                reply += received
    except OSError as error:
        raise ScanUnavailable(str(error)) from error
    outcome, detail = file_rules.clamd_verdict(reply)
    if outcome == "error":
        raise ScanUnavailable(detail)
    return Verdict(clean=outcome == "clean", detail=detail)


def _fake(data: bytes) -> Verdict:
    if EICAR in data:
        return Verdict(clean=False, detail="Eicar-Test-Signature")
    return Verdict(clean=True)


def scan(data: bytes) -> Verdict:
    return _fake(data) if settings.FILE_SCANNER == "fake" else _clamd(data)
