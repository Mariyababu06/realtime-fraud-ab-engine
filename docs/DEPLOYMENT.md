# Deployment

## Local (Docker Compose)
```bash
make env && make up        # infra + topics + tables + roles
make app                   # consumer + dashboard (http://localhost:8501)
make produce               # send data
make logs                  # follow consumer logs
make down                  # stop everything (add -v to the compose command to delete data volumes)
```

Startup order is enforced with health checks: ZooKeeper > Kafka > topics-init, and ClickHouse > db-init > consumer/dashboard.

## CI/CD (`.github/workflows/ci-cd.yml`)
1. **lint-and-test**: `ruff` + `pytest` on Python 3.11 and 3.12 (SQL tests run on embedded ClickHouse).
2. **security**: `pip-audit`, fail if secrets files are tracked.
3. **docker**: validate the compose file and build the image.
4. **publish** (main branch only): push the image to GitHub Container Registry with `latest` and commit-SHA tags.

## Cloud path (when you outgrow one machine)
- Kafka: Confluent Cloud / MSK; ClickHouse: ClickHouse Cloud or a 2-shard x 2-replica cluster.
- Run `consumer` as 1 container per partition group (6 partitions = up to 6 consumers in the same group).
- Dashboard: any container host (Cloud Run, ECS, Azure Container Apps) with `CLICKHOUSE_ANALYST_*` secrets from a secret manager.
- Scale-out checklist: increase partitions, add consumer replicas, raise `BATCH_SIZE`, monitor consumer lag and p95 latency vs SLA.
