import pytest

from pipeline.rules import VelocityTracker, rule_a, rule_b
from pipeline.scoring import Scorer, ValidationError

BASE = {"txn_id": 1, "step": 5, "type": "TRANSFER", "amount": 300_000, "nameOrig": "C1", "oldbalanceOrg": 900_000,
        "newbalanceOrig": 600_000, "nameDest": "C2", "oldbalanceDest": 0, "newbalanceDest": 300_000, "isFraud": 0}


def test_rule_a_flags_large_risky_only():
    assert rule_a(BASE)
    assert not rule_a({**BASE, "amount": 199_999})
    assert not rule_a({**BASE, "type": "PAYMENT"})


def test_rule_b_flags_account_drain_not_big_normal_transfer():
    assert not rule_b(BASE, 0)  # 33% of balance: not a drain
    assert rule_b({**BASE, "amount": 50_000, "oldbalanceOrg": 50_000}, 0)
    assert not rule_b({**BASE, "amount": 500, "oldbalanceOrg": 500}, 0)  # tiny drains ignored


def test_rule_b_velocity_trigger():
    assert rule_b({**BASE, "amount": 1_000}, dest_velocity=3)


def test_velocity_tracker_window():
    t = VelocityTracker(window=6)
    assert [t.observe("D", s) for s in (1, 2, 3)] == [1, 2, 3]
    assert t.observe("D", 20) == 1  # old events fall out of the window


def test_scorer_ignores_client_supplied_variant_and_validates():
    row = Scorer().score({**BASE, "variant": "B"})
    assert row["variant"] in ("A", "B") and row["flagged"] in (0, 1)
    with pytest.raises(ValidationError):
        Scorer().score({**BASE, "type": "BOGUS"})
    with pytest.raises(ValidationError):
        Scorer().score({k: v for k, v in BASE.items() if k != "amount"})
