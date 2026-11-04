"""Central configuration. Everything comes from environment variables (see .env.example); no secrets in code."""
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""


@dataclass(frozen=True)
class Settings:
    # Kafka
    kafka_bootstrap: str = field(default_factory=lambda: _env("KAFKA_BOOTSTRAP", "localhost:29092"))
    kafka_topic_raw: str = field(default_factory=lambda: _env("KAFKA_TOPIC_RAW", "transactions.raw"))
    kafka_topic_dlq: str = field(default_factory=lambda: _env("KAFKA_TOPIC_DLQ", "transactions.dlq"))
    kafka_group: str = field(default_factory=lambda: _env("KAFKA_GROUP", "fraud-scorer"))
    # ClickHouse
    ch_host: str = field(default_factory=lambda: _env("CLICKHOUSE_HOST", "localhost"))
    ch_port: int = field(default_factory=lambda: int(_env("CLICKHOUSE_HTTP_PORT", "8123")))
    ch_db: str = field(default_factory=lambda: _env("CLICKHOUSE_DB", "fraud"))
    ch_pipeline_user: str = field(default_factory=lambda: _env("CLICKHOUSE_PIPELINE_USER", "pipeline_user"))
    ch_pipeline_password: str = field(default_factory=lambda: _env("CLICKHOUSE_PIPELINE_PASSWORD", ""))
    ch_analyst_user: str = field(default_factory=lambda: _env("CLICKHOUSE_ANALYST_USER", "analyst_user"))
    ch_analyst_password: str = field(default_factory=lambda: _env("CLICKHOUSE_ANALYST_PASSWORD", ""))
    # Security / experiment
    pii_salt: str = field(default_factory=lambda: _env("PII_SALT", "dev-only-salt-change-me"))
    experiment_salt: str = field(default_factory=lambda: _env("EXPERIMENT_SALT", "exp-fraud-rules-v1"))
    ab_split_a: int = field(default_factory=lambda: int(_env("AB_SPLIT_A", "50")))  # % of users in variant A
    # Processing
    batch_size: int = field(default_factory=lambda: int(_env("BATCH_SIZE", "500")))
    latency_sla_ms: float = field(default_factory=lambda: float(_env("LATENCY_SLA_MS", "100")))
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))


def get_settings() -> Settings:
    return Settings()


def load_kafka_config(path: Path | None = None) -> dict:
    with open(path or ROOT / "config" / "kafka_config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)
