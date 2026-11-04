-- Runs once on first container start (mounted into /docker-entrypoint-initdb.d/).
-- Tables, the masking view, roles and users are created by scripts/init_db.py because they need secrets from .env.
CREATE DATABASE IF NOT EXISTS fraud;
