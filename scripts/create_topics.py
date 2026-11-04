"""Creates Kafka topics from config/kafka_config.yaml (single source of truth). Idempotent."""
import time

from confluent_kafka.admin import AdminClient, NewTopic

from pipeline.logging_config import get_logger
from pipeline.settings import get_settings, load_kafka_config

log = get_logger("create_topics")


def main() -> None:
    admin = AdminClient({"bootstrap.servers": get_settings().kafka_bootstrap})
    for _ in range(30):  # wait for the broker
        try:
            admin.list_topics(timeout=5)
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    topics = [NewTopic(t["name"], t["partitions"], t["replication_factor"],
                       config={k: str(v) for k, v in t.get("config", {}).items()})
              for t in load_kafka_config()["topics"]]
    for name, fut in admin.create_topics(topics).items():
        try:
            fut.result()
            log.info("created topic %s", name)
        except Exception as exc:  # noqa: BLE001
            log.info("topic %s: %s", name, str(exc).splitlines()[0])


if __name__ == "__main__":
    main()
