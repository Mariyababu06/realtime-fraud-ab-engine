"""Data layer for the dashboard. Two interchangeable backends with the same methods:
  * ClickHouseBackend: live, connects as analyst_user (read-only, masked view only)
  * DemoBackend: reads data/demo/scored_masked.parquet created by scripts/run_local_demo.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.settings import get_settings  # noqa: E402

QUERIES = ROOT / "database" / "queries"
DEMO_FILE = ROOT / "data" / "demo" / "scored_masked.parquet"
VIEW = "fraud.v_transactions_masked"


def _confusion(g: pd.DataFrame) -> dict:
    tp = int(((g.flagged == 1) & (g.isFraud == 1)).sum())
    fn = int(((g.flagged == 0) & (g.isFraud == 1)).sum())
    fp = int(((g.flagged == 1) & (g.isFraud == 0)).sum())
    tn = int(((g.flagged == 0) & (g.isFraud == 0)).sum())
    return {"tp": tp, "fn": fn, "fp": fp, "tn": tn}


class ClickHouseBackend:
    name = "ClickHouse (live)"

    def __init__(self):
        import clickhouse_connect
        s = get_settings()
        self.sla = s.latency_sla_ms
        self.client = clickhouse_connect.get_client(host=s.ch_host, port=s.ch_port, database=s.ch_db,
                                                    username=s.ch_analyst_user, password=s.ch_analyst_password,
                                                    connect_timeout=3, send_receive_timeout=30)
        self.client.command("SELECT 1")

    def _df(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        return self.client.query_df(sql, parameters=params or {})

    def ab_metrics(self, sla_ms: float) -> pd.DataFrame:
        return self._df((QUERIES / "ab_metrics.sql").read_text(encoding="utf-8"), {"sla_ms": sla_ms})

    def trend(self) -> pd.DataFrame:
        return self._df(f"""SELECT intDiv(step, 24) AS day, variant, count() AS txns,
            countIf(flagged = 1 AND isFraud = 1) AS tp, countIf(flagged = 1 AND isFraud = 0) AS fp,
            countIf(flagged = 0 AND isFraud = 1) AS fn FROM {VIEW} GROUP BY day, variant ORDER BY day, variant""")

    def velocity(self, min_txns: int, top_n: int) -> pd.DataFrame:
        return self._df((QUERIES / "rolling_windows.sql").read_text(encoding="utf-8"),
                        {"min_txns": min_txns, "top_n": top_n})

    def recent_flagged(self, n: int = 50) -> pd.DataFrame:
        return self._df(f"""SELECT txn_id, step, type, amount, orig_id_masked, dest_id_masked, variant, isFraud,
            round(latency_ms, 1) AS latency_ms FROM {VIEW} WHERE flagged = 1 ORDER BY scored_at DESC, txn_id DESC LIMIT {{n:UInt32}}""",
                        {"n": n})


class DemoBackend:
    name = "Demo file"

    def __init__(self, path: Path = DEMO_FILE):
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run: python scripts/run_local_demo.py")
        self.df = pd.read_parquet(path)

    def ab_metrics(self, sla_ms: float) -> pd.DataFrame:
        rows = []
        for v, g in self.df.groupby("variant"):
            c = _confusion(g)
            rows.append({"variant": v, "rule_version": g.rule_version.iloc[0], "txns": len(g),
                         "actual_fraud": int(g.isFraud.sum()), "flagged_txns": int(g.flagged.sum()), **c,
                         "fraud_detection_rate": round(c["tp"] / max(c["tp"] + c["fn"], 1), 4),
                         "false_positive_rate": round(c["fp"] / max(c["fp"] + c["tn"], 1), 6),
                         "precision": round(c["tp"] / max(c["tp"] + c["fp"], 1), 4),
                         "fraud_amount_caught": round(g.loc[(g.flagged == 1) & (g.isFraud == 1), "amount"].sum(), 2),
                         "fraud_amount_missed": round(g.loc[(g.flagged == 0) & (g.isFraud == 1), "amount"].sum(), 2),
                         "latency_p50_ms": round(g.latency_ms.quantile(.50), 3),
                         "latency_p95_ms": round(g.latency_ms.quantile(.95), 3),
                         "latency_p99_ms": round(g.latency_ms.quantile(.99), 3),
                         "pct_within_sla": round(float((g.latency_ms <= sla_ms).mean()), 4)})
        return pd.DataFrame(rows)

    def trend(self) -> pd.DataFrame:
        d = self.df.assign(day=self.df.step // 24)
        out = d.groupby(["day", "variant"]).apply(lambda g: pd.Series({"txns": len(g), **{k: v for k, v in _confusion(g).items() if k != "tn"}}),
                                                  include_groups=False).reset_index()
        return out.astype({"txns": int})

    def velocity(self, min_txns: int, top_n: int) -> pd.DataFrame:
        r = self.df[self.df.type.isin(["TRANSFER", "CASH_OUT"])].sort_values(["dest_id_masked", "step"])
        out = []
        for dest, g in r.groupby("dest_id_masked"):
            if len(g) < min_txns:
                continue
            steps, amt = g.step.to_numpy(), g.amount.to_numpy()
            csum = np.concatenate([[0.0], np.cumsum(amt)])
            for i in range(len(g)):
                lo = int(np.searchsorted(steps, steps[i] - 5, side="left"))
                hi = int(np.searchsorted(steps, steps[i], side="right"))
                n = hi - lo
                if n >= min_txns:
                    w = g.iloc[lo:hi]
                    out.append({"dest_id_masked": dest, "step": int(steps[i]), "txns_in_window": n,
                                "amount_in_window": round(float(csum[hi] - csum[lo]), 2),
                                "distinct_senders": int(w.orig_id_masked.nunique()), "fraud_in_window": int(w.isFraud.sum())})
        res = pd.DataFrame(out, columns=["dest_id_masked", "step", "txns_in_window", "amount_in_window",
                                         "distinct_senders", "fraud_in_window"])
        res = res.drop_duplicates()
        return res.sort_values(["txns_in_window", "amount_in_window"], ascending=False).head(top_n).reset_index(drop=True)

    def recent_flagged(self, n: int = 50) -> pd.DataFrame:
        cols = ["txn_id", "step", "type", "amount", "orig_id_masked", "dest_id_masked", "variant", "isFraud", "latency_ms"]
        return self.df[self.df.flagged == 1].sort_values("txn_id", ascending=False).head(n)[cols].round({"latency_ms": 1})


def get_backend(mode: str = "Auto"):
    """Auto: try live ClickHouse first, fall back to the demo file."""
    if mode in ("Auto", "ClickHouse live"):
        try:
            return ClickHouseBackend(), None
        except Exception as exc:  # noqa: BLE001
            if mode == "ClickHouse live":
                raise
            err = f"ClickHouse not reachable ({type(exc).__name__}); showing demo data."
            return DemoBackend(), err
    return DemoBackend(), None
