import pytest

from apps.core.handles import from_email


@pytest.mark.parametrize(
    ("email", "handle"),
    [
        ("Amna.Khan+work@example.com", "amna.khan"),
        ("bilal_99@example.com", "bilal_99"),
        ("..dots@example.com", "dots"),
        ("ö@example.com", "member"),
        ("a@example.com", "member"),
        ("averyveryverylongname1234567890@example.com", "averyveryverylongname123"),
    ],
)
def test_from_email(email: str, handle: str) -> None:
    assert from_email(email) == handle
