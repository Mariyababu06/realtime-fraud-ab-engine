"""Deterministic experiment assignment and keyed PII pseudonymisation."""
import hashlib
import hmac


def _bucket(user_id: str, experiment_salt: str) -> int:
    digest = hashlib.sha256(f"{experiment_salt}:{user_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % 100


def assign_variant(user_id: str, split_a: int = 50, experiment_salt: str = "exp-fraud-rules-v1") -> str:
    if not 0 <= split_a <= 100:
        raise ValueError("split_a must be between 0 and 100")
    return "A" if _bucket(str(user_id), experiment_salt) < split_a else "B"


def mask_id(value: str, salt: str) -> str:
    """HMAC-SHA256 prevents offline guessing without the secret key."""
    if not salt or salt == "dev-only-salt-change-me":
        raise ValueError("A non-default PII_SALT is required for pseudonymisation")
    return hmac.new(salt.encode(), str(value).encode(), hashlib.sha256).hexdigest().upper()
