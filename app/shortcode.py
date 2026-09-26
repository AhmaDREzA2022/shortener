import secrets

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ23456789"
#  Removed: 0/O, 1/l/I — ambiguous chars confuse users reading a code off a screen.


def generate_code(length: int = 7) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
