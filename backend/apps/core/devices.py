"""A short name for a signed-in device, such as "Firefox on Windows", from its User-Agent.

Only the browser and the system are read, to help a person recognise their own devices; the
order matters because browsers name each other (Edge says "Chrome", Chrome says "Safari").
"""

BROWSERS = (
    ("Edg/", "Edge"),
    ("EdgiOS", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS", "Firefox"),
    ("SamsungBrowser", "Samsung Internet"),
    ("CriOS", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)

SYSTEMS = (
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
)

MAX_AGENT = 300


def label(user_agent: str) -> str:
    browser = next((name for mark, name in BROWSERS if mark in user_agent), None)
    system = next((name for mark, name in SYSTEMS if mark in user_agent), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "Unknown browser"
