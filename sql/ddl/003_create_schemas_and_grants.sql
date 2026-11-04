-- =====================================================================
-- 003_create_schemas_and_grants.sql
-- Creates the landing schemas and applies least-privilege permissions.
-- Run as: admin (superuser), connected to the 'afripulse' database.
-- Idempotent: safe to run more than once.
-- =====================================================================

-- ---------- Database-level access ----------
-- By default every role may connect to every database. Lock that down.
REVOKE ALL ON DATABASE afripulse FROM PUBLIC;
GRANT CONNECT ON DATABASE afripulse TO afripulse_app, afripulse_dbt, afripulse_reader;

-- dbt creates its own schemas (staging, intermediate, marts).
GRANT CREATE ON DATABASE afripulse TO afripulse_dbt;

-- Nobody should create random tables in the default 'public' schema.
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- ---------- Landing schemas, owned by the ingestion role ----------
CREATE SCHEMA IF NOT EXISTS raw           AUTHORIZATION afripulse_app;
CREATE SCHEMA IF NOT EXISTS raw_synthetic AUTHORIZATION afripulse_app;
CREATE SCHEMA IF NOT EXISTS audit         AUTHORIZATION afripulse_app;

COMMENT ON SCHEMA raw           IS 'Real public source data, stored as ingested, with lineage metadata';
COMMENT ON SCHEMA raw_synthetic IS 'SYNTHETIC generated data. Never present as real-world observations';
COMMENT ON SCHEMA audit         IS 'Pipeline operations: ingestion runs, data quality results';

-- ---------- dbt may READ everything in the landing schemas ----------
GRANT USAGE  ON SCHEMA raw, raw_synthetic, audit TO afripulse_dbt;
GRANT SELECT ON ALL TABLES IN SCHEMA raw, raw_synthetic, audit TO afripulse_dbt;

-- ...including tables the ingestion role creates in the FUTURE.
ALTER DEFAULT PRIVILEGES FOR ROLE afripulse_app IN SCHEMA raw, raw_synthetic, audit
    GRANT SELECT ON TABLES TO afripulse_dbt;

-- afripulse_reader receives SELECT on marts later, managed by dbt (Phase 5).