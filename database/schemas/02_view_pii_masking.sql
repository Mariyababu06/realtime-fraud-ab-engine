-- Analyst-facing view: account ids are replaced by HMAC-SHA256 pseudonyms (same value -> same hash, so analysts can still
-- count distinct accounts and spot repeat destinations, but cannot read the id). FINAL collapses Kafka replays.
-- __PII_SALT__ is injected by scripts/init_db.py from the PII_SALT environment variable.
-- SQL SECURITY DEFINER: analysts need no grant on the base table, only on this view.
CREATE OR REPLACE VIEW fraud.v_transactions_masked
DEFINER = CURRENT_USER SQL SECURITY DEFINER
AS
SELECT
    txn_id,
    step,
    type,
    amount,
    hex(hmac_sha256('__PII_SALT__', nameOrig)) AS orig_id_masked,
    hex(hmac_sha256('__PII_SALT__', nameDest)) AS dest_id_masked,
    oldbalanceOrg,
    newbalanceOrig,
    isFraud,
    variant,
    flagged,
    rule_version,
    dest_velocity,
    produced_at,
    scored_at,
    latency_ms
FROM fraud.transactions FINAL;
