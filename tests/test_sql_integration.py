"""Runs the real SQL files against an embedded ClickHouse engine (chdb) and checks them against the Python logic.
Skipped automatically if chdb is not installed. Verifies: schema + masking view, masked hash == Python mask_id,
ab_metrics.sql == pandas metrics, rolling_windows.sql runs and finds the mule bursts."""
import re
import tempfile
from pathlib import Path

import pandas as pd
import pytest

chdb = pytest.importorskip("chdb")
from chdb import session as chdb_session  # noqa: E402

from pipeline.consumer_processor import COLUMNS, to_row  # noqa: E402
from pipeline.hashing import mask_id  # noqa: E402
from pipeline.producer import iter_events  # noqa: E402
from pipeline.scoring import Scorer  # noqa: E402
from scripts.generate_sample_data import generate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SALT = "test-salt"


def _sql(rel: str) -> str:
    text = (ROOT / rel).read_text(encoding="utf-8").replace("__PII_SALT__", SALT)
    return "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("--"))


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    csv = tmp_path_factory.mktemp("d") / "s.csv"
    generate(40_000, seed=7).to_csv(csv, index=False)
    scorer, rows = Scorer(), []
    for ev in iter_events(csv, None):
        rows.append(to_row(scorer.score(ev), ev["produced_at"] + 5.0))
    df = pd.DataFrame(rows, columns=COLUMNS)
    sess = chdb_session.Session(tempfile.mkdtemp())
    sess.query("CREATE DATABASE fraud")
    sess.query(_sql("database/schemas/01_table_transactions.sql").replace(";", ""))
    sess.query("INSERT INTO fraud.transactions SELECT * FROM Python(df)")
    view = _sql("database/schemas/02_view_pii_masking.sql").replace(";", "")
    try:
        sess.query(view)
    except Exception:  # embedded engine without access control: drop the DEFINER clause, keep the SELECT identical
        sess.query(re.sub(r"DEFINER = CURRENT_USER SQL SECURITY DEFINER\n", "", view))
    return sess, df


def _q(sess, sql, **params):
    for k, v in params.items():
        sql = re.sub(r"\{" + k + r":[A-Za-z0-9]+\}", str(v), sql)
    return sess.query(sql, "DataFrame")


def test_masked_view_hides_raw_ids_and_matches_python_hash(db):
    sess, df = db
    out = _q(sess, "SELECT * FROM fraud.v_transactions_masked LIMIT 5")
    assert "nameOrig" not in out.columns and "nameDest" not in out.columns
    one = _q(sess, "SELECT txn_id, orig_id_masked FROM fraud.v_transactions_masked ORDER BY txn_id LIMIT 1").iloc[0]
    raw = _q(sess, f"SELECT nameOrig FROM fraud.transactions WHERE txn_id = {int(one.txn_id)}").iloc[0, 0]
    assert one.orig_id_masked == mask_id(raw, SALT)


def test_ab_metrics_sql_matches_pandas(db):
    sess, df = db
    sql = _q(sess, (ROOT / "database/queries/ab_metrics.sql").read_text(encoding="utf-8"), sla_ms=100)
    for _, r in sql.iterrows():
        g = df[df.variant == r.variant]
        tp = int(((g.flagged == 1) & (g.isFraud == 1)).sum())
        fn = int(((g.flagged == 0) & (g.isFraud == 1)).sum())
        fp = int(((g.flagged == 1) & (g.isFraud == 0)).sum())
        assert (r.tp, r.fn, r.fp) == (tp, fn, fp)
        assert r.txns == len(g)
        assert abs(r.fraud_detection_rate - tp / (tp + fn)) < 1e-3


def test_rolling_window_query_finds_velocity_bursts(db):
    sess, _ = db
    out = _q(sess, (ROOT / "database/queries/rolling_windows.sql").read_text(encoding="utf-8"), min_txns=3, top_n=20)
    assert len(out) > 0 and out.txns_in_window.min() >= 3
    assert out.fraud_in_window.max() >= 3  # mule bursts planted by the generator are detected
