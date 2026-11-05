-- Analyst-facing view: account ids are replaced by HMAC-SHA256 pseudonyms (same value -> same hash, so analysts can still
-- count distinct accounts and spot repeat destinations, but cannot read the id). FINAL collapses Kafka replays.
-- ClickHouse has no HMAC function, so HMAC-SHA256 is rebuilt as SHA256(opad || SHA256(ipad || value)).
-- The two key-pad constants below are derived from PII_SALT by scripts/init_db.py (pipeline.hashing.hmac_pads_hex).
-- SQL SECURITY DEFINER: analysts need no grant on the base table, only on this view.
CREATE OR REPLACE VIEW fraud.v_transactions_masked
DEFINER = CURRENT_USER SQL SECURITY DEFINER
AS
SELECT
    txn_id,
    step,
    type,
    amount,
    hex(SHA256(concat(unhex('__HMAC_OPAD_HEX__'), SHA256(concat(unhex('__HMAC_IPAD_HEX__'), nameOrig))))) AS orig_id_masked,
    hex(SHA256(concat(unhex('__HMAC_OPAD_HEX__'), SHA256(concat(unhex('__HMAC_IPAD_HEX__'), nameDest))))) AS dest_id_masked,
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
