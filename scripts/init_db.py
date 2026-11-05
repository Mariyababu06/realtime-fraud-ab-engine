"""Applies database/schemas + database/security to ClickHouse, injecting secrets from the environment.
Runs once after ClickHouse is healthy (docker-compose service `db-init`) and is safe to re-run.

Needs: CLICKHOUSE_ADMIN_USER / CLICKHOUSE_ADMIN_PASSWORD, PII_SALT, CLICKHOUSE_PIPELINE_PASSWORD, CLICKHOUSE_ANALYST_PASSWORD
"""
import os
import sys
from pathlib import Path

import clickhouse_connect

from pipeline.hashing import hmac_pads_hex
from pipeline.logging_config import get_logger

log = get_logger("init_db")
ROOT = Path(__file__).resolve().parents[1]
FILES = ["database/schemas/01_table_transactions.sql", "database/schemas/02_view_pii_masking.sql",
         "database/security/03_rbac_setup.sql"]
PLACEHOLDERS = {"__PIPELINE_PASSWORD__": "CLICKHOUSE_PIPELINE_PASSWORD",
                "__ANALYST_PASSWORD__": "CLICKHOUSE_ANALYST_PASSWORD"}


def render(sql: str) -> str:
    if "__HMAC_" in sql:
        if "change-me" in os.getenv("PII_SALT", ""):
            sys.exit("PII_SALT must be set to a real secret (see .env.example)")
        ipad, opad = hmac_pads_hex(os.getenv("PII_SALT", ""))
        sql = sql.replace("__HMAC_IPAD_HEX__", ipad).replace("__HMAC_OPAD_HEX__", opad)
    for token, env in PLACEHOLDERS.items():
        if token in sql:
            value = os.getenv(env)
            if not value or "change-me" in value:
                sys.exit(f"{env} must be set to a real secret (see .env.example)")
            sql = sql.replace(token, value.replace("'", "''"))
    return sql


def statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main() -> None:
    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"), port=int(os.getenv("CLICKHOUSE_HTTP_PORT", "8123")),
        username=os.getenv("CLICKHOUSE_ADMIN_USER", "admin"), password=os.getenv("CLICKHOUSE_ADMIN_PASSWORD", ""))
    client.command("CREATE DATABASE IF NOT EXISTS fraud")
    for rel in FILES:
        for stmt in statements(render((ROOT / rel).read_text(encoding="utf-8"))):
            client.command(stmt)
        log.info("applied %s", rel)
    log.info("database ready")


if __name__ == "__main__":
    main()
