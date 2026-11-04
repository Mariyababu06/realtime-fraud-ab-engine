"""Streams a PaySim-format CSV into Kafka.

Each event gets a txn_id, a produced_at timestamp (for end-to-end latency) and the A/B variant (dynamic hash of the origin
account). Messages are keyed by origin account so one user's events stay in one partition, in order.

    python -m pipeline.producer --source data/sample_paysim.csv --rate 2000 --limit 100000
    python -m pipeline.producer --source data/sample_paysim.csv --dry-run --limit 5
"""
import argparse
import json
import time
from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from pipeline.hashing import assign_variant
from pipeline.logging_config import get_logger
from pipeline.settings import get_settings

log = get_logger("producer")
COLUMNS = ["step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",
           "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud"]


def iter_events(path: Path, limit: int | None, chunksize: int = 50_000) -> Iterator[dict]:
    """Reads the CSV in chunks so a 24M-row file never has to fit in memory."""
    s, n = get_settings(), 0
    for chunk in pd.read_csv(path, usecols=COLUMNS, chunksize=chunksize):
        for rec in chunk.to_dict("records"):
            if limit is not None and n >= limit:
                return
            n += 1
            rec["txn_id"] = n
            rec["variant"] = assign_variant(rec["nameOrig"], s.ab_split_a, s.experiment_salt)
            rec["produced_at"] = time.time() * 1000
            yield rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=None, help="max events to send")
    ap.add_argument("--rate", type=float, default=0, help="events per second (0 = as fast as possible)")
    ap.add_argument("--dry-run", action="store_true", help="print events instead of sending")
    args = ap.parse_args()
    s = get_settings()

    if args.dry_run:
        for ev in iter_events(args.source, args.limit):
            print(json.dumps(ev))
        return

    from confluent_kafka import Producer  # imported lazily so tests / dry-run need no Kafka client

    errors = {"n": 0}

    def on_delivery(err, msg):
        if err is not None:
            errors["n"] += 1
            log.error("delivery failed: %s", err)

    producer = Producer({"bootstrap.servers": s.kafka_bootstrap, "enable.idempotence": True, "acks": "all",
                         "compression.type": "lz4", "linger.ms": 20, "batch.num.messages": 10_000})
    sent, t0 = 0, time.time()
    log.info("producing from %s to topic %s", args.source.name, s.kafka_topic_raw)
    for ev in iter_events(args.source, args.limit):
        while True:
            try:
                producer.produce(s.kafka_topic_raw, key=str(ev["nameOrig"]).encode(),
                                 value=json.dumps(ev).encode(), on_delivery=on_delivery)
                break
            except BufferError:
                producer.poll(0.5)  # local queue full: wait for deliveries
        producer.poll(0)
        sent += 1
        if args.rate:
            time.sleep(max(0.0, sent / args.rate - (time.time() - t0)))
        if sent % 50_000 == 0:
            log.info("sent %d events (%.0f/s)", sent, sent / (time.time() - t0))
    producer.flush(30)
    log.info("done: sent=%d delivery_errors=%d elapsed=%.1fs", sent, errors["n"], time.time() - t0)


if __name__ == "__main__":
    main()
