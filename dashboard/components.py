"""Reusable dashboard widgets: KPI cards, A/B table, significance panel, latency SLA, trend, alerts."""
import plotly.express as px
import streamlit as st

from pipeline import ab_stats

COLORS = {"A": "#7f8c8d", "B": "#1f77b4"}


def _row(m, v):
    r = m[m.variant == v]
    return r.iloc[0] if len(r) else None


def kpi_cards(m):
    a, b = _row(m, "A"), _row(m, "B")
    c = st.columns(5)
    c[0].metric("Transactions", f"{int(m.txns.sum()):,}")
    c[1].metric("Actual fraud", f"{int(m.actual_fraud.sum()):,}", f"{m.actual_fraud.sum() / m.txns.sum():.2%} of txns", delta_color="off")
    if a is not None and b is not None:
        c[2].metric("Detection rate B", f"{b.fraud_detection_rate:.1%}", f"{(b.fraud_detection_rate - a.fraud_detection_rate) * 100:+.1f} pp vs A")
        c[3].metric("False-positive rate B", f"{b.false_positive_rate:.3%}",
                    f"{(b.false_positive_rate - a.false_positive_rate) * 100:+.3f} pp vs A", delta_color="inverse")
        c[4].metric("Fraud amount caught B", f"{b.fraud_amount_caught:,.0f}", f"A: {a.fraud_amount_caught:,.0f}", delta_color="off")


def ab_table(m):
    cols = ["variant", "rule_version", "txns", "actual_fraud", "tp", "fn", "fp", "fraud_detection_rate",
            "false_positive_rate", "precision", "fraud_amount_missed"]
    st.dataframe(m[cols], use_container_width=True, hide_index=True)


def significance_panel(m, split_a: int):
    a, b = _row(m, "A"), _row(m, "B")
    if a is None or b is None:
        st.info("Both variants are needed for a significance test.")
        return
    srm = ab_stats.srm_check(int(a.txns), int(b.txns), split_a / 100)
    (st.success if srm["ok"] else st.error)(
        f"Sample-ratio check: A={int(a.txns):,}, B={int(b.txns):,}, p={srm['p_value']:.3f}. "
        + ("Split matches the design." if srm["ok"] else "Split is off: check routing before trusting results."))
    res = ab_stats.verdict({"A": a.to_dict(), "B": b.to_dict()})
    d, f = res["detection"], res["false_positive"]
    c1, c2 = st.columns(2)
    ci_d = f"95% CI {d['ci_low'] * 100:+.1f} to {d['ci_high'] * 100:+.1f}, p={d['p_value']:.4f}"
    ci_f = f"95% CI {f['ci_low'] * 100:+.3f} to {f['ci_high'] * 100:+.3f}, p={f['p_value']:.4f}"
    c1.metric("Detection-rate difference (B - A)", f"{d['diff'] * 100:+.1f} pp", ci_d, delta_color="off")
    c2.metric("False-positive-rate difference (B - A)", f"{f['diff'] * 100:+.3f} pp", ci_f, delta_color="off")
    st.info(res["text"])


def latency_panel(m, sla_ms: float):
    long = m.melt(id_vars="variant", value_vars=["latency_p50_ms", "latency_p95_ms", "latency_p99_ms"], var_name="percentile", value_name="ms")
    long["percentile"] = long.percentile.str.replace("latency_", "").str.replace("_ms", "")
    fig = px.bar(long, x="percentile", y="ms", color="variant", barmode="group", color_discrete_map=COLORS, title=f"Latency percentiles (SLA {sla_ms:.0f} ms)")
    fig.add_hline(y=sla_ms, line_dash="dash", annotation_text="SLA")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Within SLA: " + " | ".join(f"{r.variant}: {r.pct_within_sla:.2%}" for r in m.itertuples()))


def trend_chart(t):
    t = t.assign(detection=t.tp / (t.tp + t.fn).clip(lower=1), false_positives=t.fp)
    c1, c2 = st.columns(2)
    c1.plotly_chart(px.line(t, x="day", y="detection", color="variant", color_discrete_map=COLORS, title="Detection rate by day"), use_container_width=True)
    c2.plotly_chart(px.line(t, x="day", y="false_positives", color="variant", color_discrete_map=COLORS, title="False positives by day"), use_container_width=True)


def alerts_panel(velocity, recent):
    st.subheader("Velocity attacks: destination accounts with bursts of transfers")
    if velocity.empty:
        st.success("No velocity bursts above the threshold.")
    else:
        v = velocity.assign(dest_id_masked=velocity.dest_id_masked.str[:12] + "…")
        st.dataframe(v, use_container_width=True, hide_index=True)
    st.subheader("Latest flagged transactions (account ids masked)")
    r = recent.assign(orig_id_masked=recent.orig_id_masked.str[:12] + "…", dest_id_masked=recent.dest_id_masked.str[:12] + "…")
    st.dataframe(r, use_container_width=True, hide_index=True)
