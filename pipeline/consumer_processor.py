"""Kafka consumer: validates, scores (A/B rules), measures latency and batch-inserts into ClickHouse.

Reliability:
  * manual offset commit only AFTER a successful insert (at-least-once; the ReplacingMergeTree table dedups replays)
  * invalid events go to a dead-letter topic instead of crashing the loop
  * insert retries with exponential backoff; graceful shutdown on SIGINT/SIGTERM

    python -m pipeline.consumer_processor
"""
import json
import signal
import time
from datetime import datetime, timezone

import clickhouse_connect
from confluent_kafka import Consumer, KafkaError, Producer

from pipeline.logging_config import get_logger
from pipeline.scoring import Scorer, ValidationError
from pipeline.settings import get_settings

log = get_logger("consumer")
COLUMNS = ["txn_id", "step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig", "nameDest",
           "oldbalanceDest", "newbalanceDest", "isFraud", "variant", "flagged", "rule_version", "dest_velocity",
           "produced_at", "scored_at", "latency_ms"]


def to_row(scored: dict, now_ms: float) -> list:
    """Adds end-to-end latency (producer timestamp to scoring time) and orders values to match COLUMNS."""
    scored = {**scored, "latency_ms": max(0.0, now_ms - scored["produced_ms"]),
              "produced_at": datetime.fromtimestamp(scored["produced_ms"] / 1000, tz=timezone.utc),
              "scored_at": datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)}
    return [scored[c] for c in COLUMNS]


def insert_with_retry(client, rows: list, attempts: int = 4) -> None:
    for i in range(attempts):
        try:
            client.insert("transactions", rows, column_names=COLUMNS)
            return
        except Exception:  # noqa: BLE001 - any driver/network error is retried, then re-raised
            if i == attempts - 1:
                raise
            wait = 2 ** i
            log.warning("insert failed (attempt %d/%d), retrying in %ds", i + 1, attempts, wait, exc_info=True)
            time.sleep(wait)


def main() -> None:
    s = get_settings()
    scorer = Scorer(s.ab_split_a, s.experiment_salt)
    client = clickhouse_connect.get_client(host=s.ch_host, port=s.ch_port, database=s.ch_db,
                                           username=s.ch_pipeline_user, password=s.ch_pipeline_password)
    consumer = Consumer({"bootstrap.servers": s.kafka_bootstrap, "group.id": s.kafka_group,
                         "enable.auto.commit": False, "auto.offset.reset": "earliest"})
    dlq = Producer({"bootstrap.servers": s.kafka_bootstrap})
    consumer.subscribe([s.kafka_topic_raw])

    running = {"on": True}
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: running.update(on=False))

    stored = bad = 0
    t0 = time.time()
    log.info("consuming %s as group %s", s.kafka_topic_raw, s.kafka_group)
    try:
        while running["on"]:
            msgs = consumer.consume(num_messages=s.batch_size, timeout=1.0)
            rows = []
            for m in msgs:
                if m.error():
                    if m.error().code() != KafkaError._PARTITION_EOF:
                        log.error("kafka error: %s", m.error())
                    continue
                try:
                    scored = scorer.score(json.loads(m.value()))
                    rows.append(to_row(scored, time.time() * 1000))
                except (ValidationError, ValueError, KeyError, TypeError) as exc:
                    bad += 1
                    log.warning("bad event sent to DLQ: %s", exc)
                    dlq.produce(s.kafka_topic_dlq, value=m.value(), headers={"error": str(exc)[:200]})
            if rows:
                insert_with_retry(client, rows)
                consumer.commit(asynchronous=False)   # commit only after the insert succeeded
                stored += len(rows)
                if stored % (s.batch_size * 20) < len(rows):
                    log.info("stored=%d bad=%d rate=%.0f/s", stored, bad, stored / (time.time() - t0))
            dlq.poll(0)
    finally:
        dlq.flush(5)
        consumer.close()
        log.info("shutdown: stored=%d bad=%d", stored, bad)


if __name__ == "__main__":
    main()
