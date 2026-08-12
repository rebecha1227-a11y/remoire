import base64
import binascii
import hashlib
import hmac
import secrets


_ITERATIONS = 200_000
_PREFIX = "pbkdf2_sha256"


def hash_pin(pin: str | None) -> str | None:
    if not pin:
        return None
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _ITERATIONS)
    return "$".join((
        _PREFIX,
        str(_ITERATIONS),
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    ))


def verify_pin(pin: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        prefix, iterations, salt, expected = encoded.split("$", 3)
        if prefix != _PREFIX:
            return False
        iteration_count = int(iterations)
        if iteration_count != _ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), base64.urlsafe_b64decode(salt), iteration_count
        )
        return hmac.compare_digest(actual, base64.urlsafe_b64decode(expected))
    except (binascii.Error, ValueError, TypeError):
        return False
