import pytest

from apps.core.files import MAX_NAME, MAX_SIZE, problem, safe_name, shown_inline, sniff


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png"),
        (b"\xff\xd8\xff\xe0\x00\x10JFIF", "image/jpeg"),
        (b"GIF89a\x01\x00", "image/gif"),
        (b"GIF87a\x01\x00", "image/gif"),
        (b"RIFF\x24\x00\x00\x00WEBPVP8 ", "image/webp"),
        (b"%PDF-1.7\n", "application/pdf"),
        (b"PK\x03\x04\x14\x00", "application/zip"),
        (b"PK\x05\x06" + b"\x00" * 18, "application/zip"),
        (b"Meeting notes\n- chai at four\r\n", "text/plain"),
        ("Salaam, kaise ho? \u0633\u0644\u0627\u0645".encode(), "text/plain"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>', "text/plain"),
        (b"RIFF\x24\x00\x00\x00WAVEfmt ", None),
        (b"MZ\x90\x00\x03\x00", None),
        (b"\x7fELF\x02\x01", None),
        (b"text with a \x00 null", None),
        (b"bell \x07 ring", None),
        (b"\xff\xfe\xfd not utf-8", None),
        (b"", None),
    ],
)
def test_sniff(head: bytes, expected: str | None) -> None:
    assert sniff(head) == expected


def test_text_cut_inside_a_character_is_still_text() -> None:
    head = ("a" * 10 + "\u0633").encode()[:-1]

    assert sniff(head) == "text/plain"


@pytest.mark.parametrize(
    ("size", "content_type", "refused"),
    [
        (10, "image/png", False),
        (MAX_SIZE, "application/pdf", False),
        (0, "image/png", True),
        (MAX_SIZE + 1, "image/png", True),
        (10, None, True),
        (10, "image/svg+xml", True),
    ],
)
def test_problem(size: int, content_type: str | None, refused: bool) -> None:
    assert (problem(size, content_type) is not None) is refused


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\amna\\photo.jpg", "photo.jpg"),
        ("bad\x00na\u202eme.txt", "badname.txt"),
        ("   ", "file"),
        ("...", "file"),
        ("folder/", "file"),
    ],
)
def test_safe_name(name: str, expected: str) -> None:
    assert safe_name(name) == expected


def test_a_long_name_keeps_its_extension() -> None:
    name = safe_name("x" * 300 + ".docx")

    assert len(name) == MAX_NAME
    assert name.endswith(".docx")


def test_a_long_name_with_no_short_extension_is_cut() -> None:
    assert safe_name("y" * 300) == "y" * MAX_NAME
    assert safe_name("y" * 150 + "." + "z" * 150) == ("y" * 150 + "." + "z" * 150)[:MAX_NAME]


def test_only_images_are_shown_inline() -> None:
    assert shown_inline("image/webp")
    assert not shown_inline("application/pdf")
    assert not shown_inline("text/plain")
