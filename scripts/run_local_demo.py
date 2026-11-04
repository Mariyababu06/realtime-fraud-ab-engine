"""Runs the full scoring logic in-process (no Kafka / ClickHouse) and writes data/demo/scored_masked.parquet.
The dashboard's Demo mode reads this file, so you can see everything working with one command.

    python scripts/run_local_demo.py --source data/sample_paysim.csv
"""
import argparse
import time
from pathlib import Path

import pandas as pd

from pipeline.hashing import mask_id
from pipeline.logging_config import get_logger
from pipeline.producer import iter_events
from pipeline.scoring import Scorer
from pipeline.settings import get_settings

log = get_logger("demo")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=Path("data/sample_paysim.csv"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", type=Path, default=Path("data/demo/scored_masked.parquet"))
    a = ap.parse_args()
    s = get_settings()
    scorer, rows = Scorer(s.ab_split_a, s.experiment_salt), []
    t0 = time.time()
    for ev in iter_events(a.source, a.limit):
        r = scorer.score(ev)
        rows.append({
            "txn_id": r["txn_id"], "step": r["step"], "type": r["type"], "amount": r["amount"],
            "orig_id_masked": mask_id(r["nameOrig"], s.pii_salt), "dest_id_masked": mask_id(r["nameDest"], s.pii_salt),
            "oldbalanceOrg": r["oldbalanceOrg"], "newbalanceOrig": r["newbalanceOrig"], "isFraud": r["isFraud"],
            "variant": r["variant"], "flagged": r["flagged"], "rule_version": r["rule_version"],
            "dest_velocity": r["dest_velocity"], "latency_ms": r["compute_ms"],  # demo: scoring time only
        })
    df = pd.DataFrame(rows)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    log.info("scored %d events in %.1fs -> %s", len(df), time.time() - t0, a.out)
    print(df.groupby("variant").agg(txns=("txn_id", "count"), fraud=("isFraud", "sum"), flagged=("flagged", "sum")))


if __name__ == "__main__":
    main()
