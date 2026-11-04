-- Least-privilege access model. Placeholders are injected from environment variables by scripts/init_db.py.
-- Profiles (query limits) come from config/clickhouse_config.xml.

CREATE ROLE IF NOT EXISTS pipeline_role;
CREATE ROLE IF NOT EXISTS analyst_role;

-- Pipeline service account: can write and read the raw table. Cannot create/drop anything.
GRANT INSERT, SELECT ON fraud.transactions TO pipeline_role;

-- Analysts: ONLY the masked view. No access to raw ids, the base table, or system tables.
GRANT SELECT ON fraud.v_transactions_masked TO analyst_role;

CREATE USER IF NOT EXISTS pipeline_user IDENTIFIED WITH sha256_password BY '__PIPELINE_PASSWORD__'
    DEFAULT ROLE pipeline_role SETTINGS PROFILE 'pipeline_profile';
CREATE USER IF NOT EXISTS analyst_user IDENTIFIED WITH sha256_password BY '__ANALYST_PASSWORD__'
    DEFAULT ROLE analyst_role SETTINGS PROFILE 'analyst_profile';

GRANT pipeline_role TO pipeline_user;
GRANT analyst_role TO analyst_user;

-- Hourly cost cap for the analyst account (guards against runaway dashboards / exploratory queries)
CREATE QUOTA IF NOT EXISTS analyst_quota
    FOR INTERVAL 1 hour MAX queries = 2000, errors = 200, read_rows = 1000000000
    TO analyst_user;
