import base64
import re

import pytest

from apps.core import totp

# RFC 6238 appendix B: the SHA-1 test key is the ASCII "12345678901234567890".
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()


@pytest.mark.parametrize(
    ("unix", "code"),
    [
        (59, "287082"),
        (1111111109, "081804"),
        (1111111111, "050471"),
        (1234567890, "005924"),
        (2000000000, "279037"),
        (20000000000, "353130"),
    ],
)
def test_rfc_6238_vectors(unix: int, code: str) -> None:
    # The RFC lists 8-digit codes; the last 6 digits are the 6-digit code.
    assert totp.hotp(RFC_SECRET, totp.step_at(unix)) == code


def test_a_current_code_matches_its_step() -> None:
    step = totp.step_at(1111111109)

    assert totp.match(RFC_SECRET, "081804", 1111111109, None) == step
    assert totp.match(RFC_SECRET, "081 804", 1111111109, None) == step


def test_codes_one_step_either_side_still_match() -> None:
    now = 1111111109
    before = totp.hotp(RFC_SECRET, totp.step_at(now) - 1)
    after = totp.hotp(RFC_SECRET, totp.step_at(now) + 1)
    two_back = totp.hotp(RFC_SECRET, totp.step_at(now) - 2)

    assert totp.match(RFC_SECRET, before, now, None) == totp.step_at(now) - 1
    assert totp.match(RFC_SECRET, after, now, None) == totp.step_at(now) + 1
    assert totp.match(RFC_SECRET, two_back, now, None) is None


def test_a_used_step_is_never_accepted_again() -> None:
    step = totp.step_at(1111111109)

    assert totp.match(RFC_SECRET, "081804", 1111111109, last_step=step) is None
    assert totp.match(RFC_SECRET, "081804", 1111111109, last_step=step - 1) == step


@pytest.mark.parametrize("code", ["", "12345", "1234567", "12a456", "------"])
def test_malformed_codes_are_refused(code: str) -> None:
    assert totp.match(RFC_SECRET, code, 1111111109, None) is None


def test_new_secrets_are_160_bit_base32() -> None:
    secret = totp.new_secret()

    assert re.fullmatch(r"[A-Z2-7]{32}", secret)
    assert secret != totp.new_secret()
    assert len(totp.hotp(secret, 1)) == totp.DIGITS
    assert totp.hotp(secret.lower(), 1) == totp.hotp(secret, 1)


def test_setup_uri() -> None:
    uri = totp.setup_uri("JBSWY3DPEHPK3PXP", "amna@example.com")

    assert uri == (
        "otpauth://totp/Baithak%3Aamna%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=Baithak"
    )


def test_recovery_codes() -> None:
    codes = totp.new_recovery_codes()

    assert len(codes) == totp.RECOVERY_CODES == len(set(codes))
    assert all(re.fullmatch(r"[a-z2-9]{5}-[a-z2-9]{5}", code) for code in codes)
    assert not any(c in "".join(codes) for c in "01ilo")


def test_recovery_codes_are_read_loosely() -> None:
    assert totp.normal_recovery_code(" K7M2Q 9XFR4 ") == "k7m2q-9xfr4"
    assert totp.normal_recovery_code("k7m2q-9xfr4") == "k7m2q-9xfr4"
