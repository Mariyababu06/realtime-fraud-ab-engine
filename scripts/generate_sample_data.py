"""Generates a PaySim-format sample CSV so the whole project runs without downloading the 24M-row Kaggle file.

Fraud patterns mimic PaySim: TRANSFER / CASH_OUT that drain the origin account, plus bursts of transfers into mule
accounts. Some legitimate large transfers and full withdrawals are included so both rules produce false positives.
NOTE: results on this synthetic file are for demonstration; run the pipeline on real PaySim for portfolio numbers.

    python scripts/generate_sample_data.py --rows 200000
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def generate(rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    types = rng.choice(["PAYMENT", "CASH_IN", "CASH_OUT", "TRANSFER", "DEBIT"], rows, p=[0.34, 0.22, 0.35, 0.08, 0.01])
    step = np.sort(rng.integers(1, 744, rows))
    orig_ids = rng.integers(10**8, 10**9, int(rows * 0.9))
    name_orig = np.array([f"C{i}" for i in rng.choice(orig_ids, rows)])
    merchants = np.array([f"M{i}" for i in rng.integers(10**8, 10**9, 5000)])
    customers = np.array([f"C{i}" for i in rng.integers(10**8, 10**9, 60000)])
    name_dest = np.where(types == "PAYMENT", rng.choice(merchants, rows), rng.choice(customers, rows))
    old_bal = np.round(rng.lognormal(9.5, 1.6, rows), 2)
    amount = np.round(np.minimum(rng.lognormal(8.2, 1.4, rows), old_bal * rng.uniform(0.02, 0.9, rows)), 2)
    is_fraud = np.zeros(rows, dtype=int)

    risky = np.where(np.isin(types, ["TRANSFER", "CASH_OUT"]))[0]
    # 1) account-drain fraud (~0.9% of risky txns)
    drain = rng.choice(risky, int(len(risky) * 0.009), replace=False)
    old_bal[drain] = np.round(rng.lognormal(12.0, 1.3, len(drain)), 2)  # fraud victims hold larger balances (as in PaySim)
    amount[drain] = np.round(old_bal[drain] * rng.uniform(0.97, 1.0, len(drain)), 2)
    is_fraud[drain] = 1
    # 2) mule bursts: groups of 4-6 fraudulent transfers into one destination within a few hours, not always full drains
    free = np.setdiff1d(risky, drain)
    for _ in range(max(5, rows // 6000)):
        start = rng.choice(free)
        grp = free[(free > start) & (step[free] - step[start] <= 5)][: rng.integers(4, 7)]
        name_dest[grp] = f"C{rng.integers(10**8, 10**9)}"
        old_bal[grp] = np.round(rng.lognormal(11.0, 1.2, len(grp)), 2)
        amount[grp] = np.round(old_bal[grp] * rng.uniform(0.4, 0.9, len(grp)), 2)
        is_fraud[grp] = 1
    # 3) legitimate noise: big business transfers (hit rule A) and honest full withdrawals (hit rule B)
    legit = np.setdiff1d(free, np.where(is_fraud == 1)[0])
    big = rng.choice(legit, int(len(legit) * 0.012), replace=False)
    old_bal[big] = np.round(rng.uniform(400_000, 3_000_000, len(big)), 2)
    amount[big] = np.round(old_bal[big] * rng.uniform(0.3, 0.8, len(big)), 2)
    wd = rng.choice(np.setdiff1d(legit, big), int(len(legit) * 0.004), replace=False)
    amount[wd] = np.round(old_bal[wd] * rng.uniform(0.96, 1.0, len(wd)), 2)

    new_orig = np.round(np.where(np.isin(types, ["CASH_IN"]), old_bal + amount, np.maximum(old_bal - amount, 0)), 2)
    old_dest = np.round(rng.lognormal(9, 1.7, rows), 2)
    new_dest = np.round(np.where(types == "PAYMENT", 0.0, old_dest + amount), 2)
    return pd.DataFrame({"step": step, "type": types, "amount": amount, "nameOrig": name_orig, "oldbalanceOrg": old_bal,
                         "newbalanceOrig": new_orig, "nameDest": name_dest, "oldbalanceDest": old_dest,
                         "newbalanceDest": new_dest, "isFraud": is_fraud, "isFlaggedFraud": 0})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=200_000)
    ap.add_argument("--out", type=Path, default=Path("data/sample_paysim.csv"))
    a = ap.parse_args()
    df = generate(a.rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df):,} rows to {a.out} | fraud rate {df.isFraud.mean():.3%}")
