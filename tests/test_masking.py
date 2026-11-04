import hashlib
import hmac

from pipeline.hashing import mask_id


def test_mask_is_hmac_sha256_uppercase_hex():
    expected = hmac.new(b"salt", b"C123456789", hashlib.sha256).hexdigest().upper()
    assert mask_id("C123456789", "salt") == expected


def test_same_id_same_key_is_stable_and_key_changes_output():
    assert mask_id("C123456789", "salt") == mask_id("C123456789", "salt")
    assert mask_id("C123456789", "other") != mask_id("C123456789", "salt")


def test_default_dev_key_is_rejected():
    import pytest
    with pytest.raises(ValueError):
        mask_id("C123456789", "dev-only-salt-change-me")
