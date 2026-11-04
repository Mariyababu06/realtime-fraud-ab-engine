-- A/B performance matrix per variant. Run as analyst_user (reads only the masked view).
-- Detection rate (FDR) = recall = TP / actual fraud.  FPR = FP / actual legit.  Precision = TP / flagged.
-- Latency is end-to-end (producer timestamp -> scored); SLA target is a parameter, default 100 ms.
SELECT
    variant,
    any(rule_version)                                              AS rule_version,
    count()                                                        AS txns,
    sum(isFraud)                                                   AS actual_fraud,
    sum(flagged)                                                   AS flagged_txns,
    countIf(flagged = 1 AND isFraud = 1)                           AS tp,
    countIf(flagged = 0 AND isFraud = 1)                           AS fn,
    countIf(flagged = 1 AND isFraud = 0)                           AS fp,
    countIf(flagged = 0 AND isFraud = 0)                           AS tn,
    round(tp / nullIf(tp + fn, 0), 4)                              AS fraud_detection_rate,
    round(fp / nullIf(fp + tn, 0), 6)                              AS false_positive_rate,
    round(tp / nullIf(tp + fp, 0), 4)                              AS precision,
    round(sumIf(amount, flagged = 1 AND isFraud = 1), 2)           AS fraud_amount_caught,
    round(sumIf(amount, flagged = 0 AND isFraud = 1), 2)           AS fraud_amount_missed,
    round(quantile(0.50)(latency_ms), 2)                           AS latency_p50_ms,
    round(quantile(0.95)(latency_ms), 2)                           AS latency_p95_ms,
    round(quantile(0.99)(latency_ms), 2)                           AS latency_p99_ms,
    round(countIf(latency_ms <= {sla_ms:Float64}) / count(), 4)    AS pct_within_sla
FROM fraud.v_transactions_masked
GROUP BY variant
ORDER BY variant;
