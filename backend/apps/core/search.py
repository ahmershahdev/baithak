"""Turning what a person types into a MySQL FULLTEXT boolean query.

Only word characters get through, so a search can't use boolean operators to do anything but
"every word, as a prefix". InnoDB skips words under innodb_ft_min_token_size (3) and its default
stopwords when indexing; a required term it never indexed would make every search with it come
back empty, so those words are dropped here instead.
"""

import re

MIN_LENGTH = 3
# innodb_ft_max_token_size
MAX_LENGTH = 84
MAX_TERMS = 8

# INNODB_FT_DEFAULT_STOPWORD, MySQL 8.4.
STOPWORDS = frozenset(
    {
        "a", "about", "an", "are", "as", "at", "be", "by", "com", "de", "en", "for", "from",
        "how", "i", "in", "is", "it", "la", "of", "on", "or", "that", "the", "this", "to",
        "was", "what", "when", "where", "who", "will", "with", "und", "www",
    }
)  # fmt: skip

_WORD = re.compile(r"\w+")


def terms(text: str) -> list[str]:
    """The words worth searching for, lowercased, in order, each once."""
    found: list[str] = []
    for word in _WORD.findall(text.lower()):
        if MIN_LENGTH <= len(word) <= MAX_LENGTH and word not in STOPWORDS and word not in found:
            found.append(word)
    return found[:MAX_TERMS]


def boolean_query(words: list[str]) -> str:
    """Every word required, each matching as a prefix ("deploy" finds "deployment")."""
    return " ".join(f"+{word}*" for word in words)
