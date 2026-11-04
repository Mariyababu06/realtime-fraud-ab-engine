"""The two fraud rule sets being A/B tested.

Variant A (control)   : static threshold. Flags TRANSFER / CASH_OUT of 200,000 or more.
Variant B (treatment) : behavioural. Flags risky types when the origin account is drained (>= 95% of balance) or when the
                        destination account receives a burst of risky transfers (mule / velocity pattern).
"""
from collections import defaultdict, deque

RISKY_TYPES = {"TRANSFER", "CASH_OUT"}
RULE_VERSION = {"A": "static_threshold_v1", "B": "drain_velocity_v1"}

A_AMOUNT_THRESHOLD = 200_000.0
B_DRAIN_RATIO = 0.95
B_MIN_AMOUNT = 10_000.0
B_VELOCITY_WINDOW_STEPS = 6   # PaySim step = 1 hour
B_VELOCITY_LIMIT = 3


class VelocityTracker:
    """Counts risky inbound transfers per destination account in a sliding window of steps (bounded memory)."""

    def __init__(self, window: int = B_VELOCITY_WINDOW_STEPS):
        self.window = window
        self._events: dict[str, deque] = defaultdict(deque)
        self._seen = 0

    def observe(self, dest: str, step: int) -> int:
        q = self._events[dest]
        q.append(step)
        while q and q[0] <= step - self.window:
            q.popleft()
        self._seen += 1
        if self._seen % 50_000 == 0:  # prune idle accounts
            for k in [k for k, v in self._events.items() if not v or v[-1] <= step - self.window]:
                del self._events[k]
        return len(q)


def rule_a(tx: dict) -> bool:
    return tx["type"] in RISKY_TYPES and float(tx["amount"]) >= A_AMOUNT_THRESHOLD


def rule_b(tx: dict, dest_velocity: int) -> bool:
    if tx["type"] not in RISKY_TYPES:
        return False
    amount, old_bal = float(tx["amount"]), float(tx["oldbalanceOrg"])
    drained = old_bal > 0 and amount >= B_DRAIN_RATIO * old_bal and amount >= B_MIN_AMOUNT
    return drained or dest_velocity >= B_VELOCITY_LIMIT
