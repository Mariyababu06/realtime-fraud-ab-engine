# Security Model

| Threat | Control | Where |
|---|---|---|
| Analyst reads customer account ids | Salted SHA-256 masked view; analysts have no grant on the base table | `02_view_pii_masking.sql`, `03_rbac_setup.sql` |
| Analyst runs a huge query | Read-only profile, max time 30s, memory 2 GB, row limits, hourly quota | `clickhouse_config.xml`, `03_rbac_setup.sql` |
| Pipeline account misused | Insert/select on one table only, no DDL | `pipeline_role` |
| Secrets leaked to Git | `.env` ignored, `.env.example` has placeholders, `init_db.py` rejects placeholders, CI blocks tracked `.env`/keys | `.gitignore`, `scripts/init_db.py`, CI |
| PII in logs | Regex redaction filter on every handler | `pipeline/logging_config.py` |
| Spoofed A/B variant | Consumer recomputes the variant from the account id | `pipeline/scoring.py` |
| Bad or malicious events | Schema/type validation, dead-letter topic | `pipeline/scoring.py`, consumer |
| Container escape / exposure | Non-root user, ports bound to 127.0.0.1 | `docker/` |
| Vulnerable dependencies | `pip-audit` in CI | `ci-cd.yml` |

## Known limits and production hardening

- **Masking is pseudonymisation, not anonymisation.** Account ids have a guessable format, so a leaked salt would allow brute-force
  reversal. Keep `PII_SALT` in a secret manager, rotate it, and restrict `SHOW CREATE VIEW` (the salt is embedded in the view).
- Add TLS and SASL to Kafka and HTTPS to ClickHouse; the dev compose file uses plaintext on localhost only.
- Use 3 Kafka brokers (`replication_factor: 3`, `min.insync.replicas: 2`) and a ClickHouse cluster for availability.
- Add row policies if analysts should be limited to some regions, and audit logging via `system.query_log`.
- PaySim is synthetic; with real data, add data-retention rules and a documented lawful basis (GDPR / RBI guidelines).
