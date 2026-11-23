"""Handles nobody may take: reserved names, and words of hate or abuse even when disguised.

A handle is folded before matching: lowercased, accents dropped, look-alike digits and symbols
read as letters (killj4ws reads as killjews), separators removed and doubled letters squeezed,
so k.i.l.l, k_i_l_l and kiiill all read the same. Blocked words are folded the same way and
matched anywhere inside the handle.
"""

import unicodedata

RESERVED = frozenset(
    {
        "abuse", "admin", "administrator", "api", "baithak", "channel", "everyone", "help",
        "here", "moderator", "mod", "null", "owner", "postmaster", "root", "security", "staff",
        "support", "system", "undefined", "webmaster", "www",
    }
)  # fmt: skip

# Hate, violence, slurs and sexual terms, and religious or ethnic groups (a handle naming a
# group is how abuse like "killjews" starts). Words that sit inside ordinary words or names are
# left out on purpose: "rape" (grape), "isis" (crisis), "heil" (sheila), "spic" (spicy),
# "islam" (islamabad), "allah" (allahditta), "kill" (skill), "ass" (classic), "paki" (pakistan).
BLOCKED = (
    "hitler", "nazi", "kkk", "holocaust", "genocide", "massacre", "slaughter", "behead",
    "murder", "terrorist", "jihad", "alqaeda", "taliban", "rapist", "pedophile", "paedophile",
    "molest", "nigger", "nigga", "faggot", "retard", "tranny", "kike", "chink", "gook",
    "wetback", "whore", "slut", "cunt", "fuck", "shit", "bitch", "porn", "pussy", "jews",
    "jewish", "muslim", "christian", "hindu", "sikh", "buddhist", "kafir", "infidel", "zionist",
)  # fmt: skip

_LOOK_ALIKES = str.maketrans(
    {"@": "a", "3": "e", "!": "i", "|": "i", "0": "o", "5": "s", "$": "s", "7": "t", "+": "t",
     "8": "b", "9": "g"}
)  # fmt: skip
# Look-alikes that stand for more than one letter: j4ws is "jews", h4te is "hate".
_EITHER = {"4": "ae", "1": "il"}


def _squeeze(text: str) -> str:
    out: list[str] = []
    for char in text:
        if not out or out[-1] != char:
            out.append(char)
    return "".join(out)


def _letters(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return "".join(c for c in plain.translate(_LOOK_ALIKES) if c.isalpha())


def fold(text: str) -> str:
    return _squeeze(_letters(text))


# Each word matches as written and, when that still leaves a real word, squeezed: "kkk" must
# not shrink to "k" and block every handle with a k in it.
_FORMS = tuple(
    form for word in BLOCKED for form in {word, _squeeze(word)} if form == word or len(form) >= 4
)


def _spellings(handle: str) -> set[str]:
    """Every reading of the ambiguous look-alikes, each one read the same way throughout."""
    spellings = {handle.lower()}
    for char, letters in _EITHER.items():
        spellings = {s.replace(char, letter) for s in spellings for letter in letters}
    return spellings


def is_offensive(value: str) -> bool:
    """Hate or abuse anywhere in the text, however it is spelled. Used for display names too."""
    readings = {
        reading
        for spelling in _spellings(value)
        for reading in (_letters(spelling), fold(spelling))
    }
    return any(form in reading for reading in readings for form in _FORMS)


def problem(handle: str) -> str | None:
    """Why the handle can't be used, or None when it can."""
    if handle.lower() in RESERVED or fold(handle) in {fold(r) for r in RESERVED}:
        return "This handle is reserved."
    if is_offensive(handle):
        return "This handle is not allowed."
    return None


_HANDLE_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_.-"


def from_email(email: str) -> str:
    """A starting handle for someone who signs up through a provider, from their address:
    "Amna.Khan+work@example.com" gives "amna.khan". The caller adds digits if it is taken."""
    local = email.split("@", 1)[0].split("+", 1)[0].lower()
    kept = "".join(c for c in local if c in _HANDLE_CHARS).lstrip("_.-")[:24]
    return kept if len(kept) >= 2 else "member"
