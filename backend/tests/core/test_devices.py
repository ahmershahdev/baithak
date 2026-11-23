import pytest

from apps.core.devices import label

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        (CHROME_WINDOWS, "Chrome on Windows"),
        (CHROME_WINDOWS + " Edg/131.0.0.0", "Edge on Windows"),
        (CHROME_WINDOWS + " OPR/114.0.0.0", "Opera on Windows"),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Firefox on macOS",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
            "Safari on iPhone",
        ),
        (
            "Mozilla/5.0 (iPad; CPU OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like "
            "Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1",
            "Chrome on iPad",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
            "SamsungBrowser/26.0 Chrome/122.0.0.0 Mobile Safari/537.36",
            "Samsung Internet on Android",
        ),
        (
            "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36",
            "Chrome on ChromeOS",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Firefox on Linux",
        ),
        ("curl/8.5.0", "Unknown browser"),
        ("", "Unknown browser"),
        ("SomeApp/1.0 (Windows NT 10.0)", "Windows"),
        ("Firefox/132.0", "Firefox"),
    ],
)
def test_label(agent: str, expected: str) -> None:
    assert label(agent) == expected
