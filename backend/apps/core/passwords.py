MIN_LENGTH = 12
MAX_LENGTH = 128

RULES = (
    (f"at least {MIN_LENGTH} characters", lambda p: len(p) >= MIN_LENGTH),
    (f"at most {MAX_LENGTH} characters", lambda p: len(p) <= MAX_LENGTH),
    ("2 lowercase letters", lambda p: sum(c.islower() for c in p) >= 2),
    ("2 uppercase letters", lambda p: sum(c.isupper() for c in p) >= 2),
    ("2 digits", lambda p: sum(c.isdigit() for c in p) >= 2),
    ("1 symbol", lambda p: any(not c.isalnum() and not c.isspace() for c in p)),
)


def missing(password: str) -> list[str]:
    """The rules this password doesn't meet yet, in the order the web app lists them."""
    return [rule for rule, met in RULES if not met(password)]
