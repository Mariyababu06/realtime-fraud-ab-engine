# Production-readiness plan

This repository is a portfolio/reference implementation, not a certified payment-fraud control. Passing unit tests does not prove production readiness.

## Required before any real deployment
- [ ] Use managed secrets/KMS; reject default salts/passwords at startup; rotate secrets.
- [ ] Confirm analyst masking implementation is equivalent in Python and ClickHouse. Deployments must test HMAC function support and key handling before switching the view; never silently fall back to plain SHA-256.
- [ ] Use a durable state store for destination velocity (e.g. Kafka Streams/Flink keyed by destination with checkpointing), not process-local memory. Define event-time semantics, late events, TTL, replay and recovery.
- [ ] Do not horizontally scale the in-memory velocity tracker. It is not partition-safe because source messages are keyed by sender, not destination.
- [ ] Make ingestion idempotent with stable source event IDs and explicit replay semantics; committing the consumer's highest offsets per partition only after durable writes is necessary but batch-wide commits require careful handling of invalid records and partial failures.
- [ ] DLQ must be access-controlled, encrypted, retention-limited, monitored, and PII-safe. Current raw-message DLQ is sensitive and must not be exposed to analysts.
- [ ] Replace transaction-level p-values with pre-registered user/account-cluster inference; account for multiple metrics, sequential peeking, temporal drift and delayed labels.
- [ ] Add schema registry/versioning, bounded retries, backpressure, circuit breakers, health/readiness endpoints, metrics, tracing and alerting.
- [ ] Add load, chaos, restart/rebalance, duplicate-delivery, partition expansion, security, SQL integration and disaster-recovery tests.
- [ ] Run dependency/container vulnerability scans, SBOM generation, image signing, pinned dependency locks, non-root containers, network policy and least-privilege credentials.
- [ ] Validate PII redaction in every sink, including Kafka headers, exception traces, crash dumps and external telemetry.
- [ ] Define model/rule approval, rollback, audit trail, change management, false-positive review and human escalation.
- [ ] Benchmark with representative throughput and latency SLOs; document hardware, concurrency, p95/p99 and failure behaviour.

## Known limitations
1. `VelocityTracker` is in-memory and not safe for multiple consumers or restarts.
2. `consumer_processor.py` currently places original Kafka payloads in the DLQ; those payloads contain account IDs.
3. Existing `verdict()` uses transaction-level proportions; correlated transactions can overstate confidence. Use `cluster_bootstrap_rate_difference` for exploratory user-cluster recall inference.
4. Demo metrics are not empirical evidence. Use real PaySim and report limitations.
5. `txn_id` is generated from the current producer run; stable deduplication across restarts needs a source-derived event ID.
