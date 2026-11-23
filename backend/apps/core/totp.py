"""Time-based one-time codes for two-step sign-in: TOTP (RFC 6238) over HOTP (RFC 4226), with
SHA-1, 6 digits and 30-second steps, which every authenticator app uses by default.

A code is accepted for the step before and after the current one, so a clock a little off still
works, and never for a step at or before the last one used, so a code can't be replayed.
"""

import base64
import hashlib
import hmac
import secrets
from urllib.parse import quote, urlencode

STEP_SECONDS = 30
DIGITS = 6
DRIFT_STEPS = 1
SECRET_BYTES = 20


def new_secret() -> str:
    """160 random bits as base32 without padding, the form authenticator apps take."""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    padded = secret.upper() + "=" * (-len(secret) % 8)
    return base64.b32decode(padded)


def hotp(secret: str, counter: int) -> str:
    digest = hmac.new(_key(secret), counter.to_bytes(8, "big"), hashlib.sha1).digest()
    # RFC 4226 section 5.3: the low 4 bits of the last byte pick where to read 31 bits from.
    offset = digest[-1] & 0x0F
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def step_at(unix_seconds: float) -> int:
    return int(unix_seconds // STEP_SECONDS)


def match(secret: str, code: str, unix_seconds: float, last_step: int | None) -> int | None:
    """The step the code belongs to, or None if it is wrong, too old or already used."""
    code = code.replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = step_at(unix_seconds)
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(hotp(secret, step), code):
            return step
    return None


def setup_uri(secret: str, account: str, issuer: str = "Baithak") -> str:
    """The otpauth:// address an authenticator app reads from the QR code."""
    label = quote(f"{issuer}:{account}")
    return f"otpauth://totp/{label}?{urlencode({'secret': secret, 'issuer': issuer})}"


RECOVERY_CODES = 10
_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def new_recovery_codes() -> list[str]:
    """Ten codes like "k7m2q-9xfr4": 50 bits each, no look-alike characters."""
    return [
        "-".join("".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5)) for _ in range(2))
        for _ in range(RECOVERY_CODES)
    ]


def normal_recovery_code(code: str) -> str:
    """As typed or pasted: case, spaces and the dash don't matter."""
    plain = "".join(c for c in code.lower() if c.isalnum())
    return f"{plain[:5]}-{plain[5:]}"
