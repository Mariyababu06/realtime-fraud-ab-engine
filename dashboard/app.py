"""Real-time fraud A/B dashboard.   streamlit run dashboard/app.py
Auto mode connects to ClickHouse as the read-only analyst user and falls back to the demo parquet file."""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import components as ui  # noqa: E402
from data_access import get_backend  # noqa: E402

from pipeline.settings import get_settings  # noqa: E402

st.set_page_config(page_title="Fraud A/B Engine", layout="wide")
s = get_settings()

st.sidebar.header("Settings")
mode = st.sidebar.radio("Data source", ["Auto", "ClickHouse live", "Demo file"])
refresh = st.sidebar.selectbox("Auto-refresh", ["Off", "5s", "15s", "60s"])
sla = st.sidebar.number_input("Latency SLA (ms)", 1.0, 5000.0, float(s.latency_sla_ms))
min_txns = st.sidebar.slider("Velocity alert: min transfers in 6h window", 2, 10, 3)

st.title("Real-time Fraud Detection: Rule A vs Rule B")
st.caption("A = static amount threshold (control). B = account-drain + destination-velocity behaviour (treatment). "
           "Users are split by a deterministic hash; analysts see masked account ids only.")

try:
    backend, notice = get_backend(mode)
except Exception as exc:  # noqa: BLE001
    st.error(f"Data source unavailable: {exc}")
    st.stop()
if notice:
    st.warning(notice)
st.sidebar.success(f"Source: {backend.name}")


def render():
    m = backend.ab_metrics(sla)
    if m.empty:
        st.info("No transactions yet. Start the producer.")
        return
    ui.kpi_cards(m)
    tabs = st.tabs(["A/B results", "Latency SLA", "Trend", "Alerts"])
    with tabs[0]:
        ui.ab_table(m)
        ui.significance_panel(m, s.ab_split_a)
    with tabs[1]:
        ui.latency_panel(m, sla)
    with tabs[2]:
        ui.trend_chart(backend.trend())
    with tabs[3]:
        ui.alerts_panel(backend.velocity(min_txns, 25), backend.recent_flagged(50))


seconds = {"Off": None, "5s": 5, "15s": 15, "60s": 60}[refresh]
if seconds and hasattr(st, "fragment"):
    st.fragment(run_every=seconds)(render)()
else:
    render()
