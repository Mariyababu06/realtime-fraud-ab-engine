-- Velocity attacks: destination (mule) accounts receiving a burst of risky transfers.
-- Rolling window = the current hour plus the previous 5 hours (PaySim step = 1 hour), per destination account.
SELECT DISTINCT
    dest_id_masked,
    step,
    txns_in_window,
    round(amount_in_window, 2) AS amount_in_window,
    distinct_senders,
    fraud_in_window
FROM
(
    SELECT
        dest_id_masked,
        step,
        count()                 OVER w AS txns_in_window,
        sum(amount)             OVER w AS amount_in_window,
        uniqExact(orig_id_masked) OVER w AS distinct_senders,
        sum(isFraud)            OVER w AS fraud_in_window
    FROM fraud.v_transactions_masked
    WHERE type IN ('TRANSFER', 'CASH_OUT')
    WINDOW w AS (PARTITION BY dest_id_masked ORDER BY step ASC RANGE BETWEEN 5 PRECEDING AND CURRENT ROW)
)
WHERE txns_in_window >= {min_txns:UInt32}
ORDER BY txns_in_window DESC, amount_in_window DESC
LIMIT {top_n:UInt32};
