-- Base table: raw identifiers live here, so only the pipeline role can touch it.
-- ReplacingMergeTree(scored_at) keeps one row per (variant, txn_id): safe if Kafka redelivers a batch.
-- ORDER BY starts with the low-cardinality variant (every A/B query filters or groups on it).
CREATE TABLE IF NOT EXISTS fraud.transactions
(
    txn_id          UInt64,
    step            UInt16,
    type            LowCardinality(String),
    amount          Float64,
    nameOrig        String,
    oldbalanceOrg   Float64,
    newbalanceOrig  Float64,
    nameDest        String,
    oldbalanceDest  Float64,
    newbalanceDest  Float64,
    isFraud         UInt8,
    variant         LowCardinality(String),
    flagged         UInt8,
    rule_version    LowCardinality(String),
    dest_velocity   UInt16,
    produced_at     DateTime64(3, 'UTC'),
    scored_at       DateTime64(3, 'UTC'),
    latency_ms      Float32
)
ENGINE = ReplacingMergeTree(scored_at)
ORDER BY (variant, txn_id);
