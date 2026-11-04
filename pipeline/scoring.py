"""Scores one transaction event with the rule set of its A/B variant."""
import time

from pipeline.hashing import assign_variant
from pipeline.rules import RISKY_TYPES, RULE_VERSION, VelocityTracker, rule_a, rule_b

REQUIRED = ("txn_id", "step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
            "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud")
TYPES = {"PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"}


class ValidationError(ValueError):
    pass


def validate(event: dict) -> None:
    missing = [k for k in REQUIRED if k not in event or event[k] is None]
    if missing:
        raise ValidationError(f"missing fields: {missing}")
    if event["type"] not in TYPES:
        raise ValidationError(f"unknown type: {event['type']}")
    if float(event["amount"]) < 0:
        raise ValidationError("negative amount")


class Scorer:
    def __init__(self, split_a: int = 50, experiment_salt: str = "exp-fraud-rules-v1"):
        self.split_a, self.experiment_salt = split_a, experiment_salt
        self.velocity = VelocityTracker()

    def score(self, event: dict) -> dict:
        """Returns the row to store. Variant is recomputed here so a tampered 'variant' field is never trusted."""
        validate(event)
        t0 = time.perf_counter()
        variant = assign_variant(event["nameOrig"], self.split_a, self.experiment_salt)
        velocity = self.velocity.observe(event["nameDest"], int(event["step"])) if event["type"] in RISKY_TYPES else 0
        flagged = rule_a(event) if variant == "A" else rule_b(event, velocity)
        compute_ms = (time.perf_counter() - t0) * 1000
        return {
            "txn_id": int(event["txn_id"]), "step": int(event["step"]), "type": event["type"],
            "amount": float(event["amount"]), "nameOrig": event["nameOrig"],
            "oldbalanceOrg": float(event["oldbalanceOrg"]), "newbalanceOrig": float(event["newbalanceOrig"]),
            "nameDest": event["nameDest"], "oldbalanceDest": float(event["oldbalanceDest"]),
            "newbalanceDest": float(event["newbalanceDest"]), "isFraud": int(event["isFraud"]),
            "variant": variant, "flagged": int(flagged), "rule_version": RULE_VERSION[variant],
            "dest_velocity": velocity, "compute_ms": compute_ms,
            "produced_ms": float(event.get("produced_at", time.time() * 1000)),
        }
