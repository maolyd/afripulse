-- =====================================================================
-- 004_audit_tables.sql
-- Operational audit tables for pipeline monitoring.
-- Run as: admin, connected to the 'afripulse' database.
-- Idempotent: safe to run more than once.
-- =====================================================================

-- Create objects AS the ingestion role, so it owns them. Ownership matters:
-- the default privileges from 003 (dbt may SELECT) apply to tables
-- created by afripulse_app.
SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS audit.ingestion_runs (
    run_id            uuid         PRIMARY KEY,
    source_id         text         NOT NULL,
    status            text         NOT NULL
        CHECK (status IN ('running', 'success', 'skipped', 'failed')),
    started_at        timestamptz  NOT NULL DEFAULT now(),
    finished_at       timestamptz,
    duration_seconds  numeric(10, 3),
    rows_extracted    integer      CHECK (rows_extracted >= 0),
    rows_loaded       integer      CHECK (rows_loaded >= 0),
    rows_rejected     integer      CHECK (rows_rejected >= 0),
    source_release    text,
    source_checksum   text,
    error_message     text,
    triggered_by      text         NOT NULL DEFAULT session_user
);

COMMENT ON TABLE audit.ingestion_runs IS
    'One row per ingestion run per source: status, row counts, timing and errors';
COMMENT ON COLUMN audit.ingestion_runs.status IS
    'running = in progress; success; skipped = source unchanged; failed';
COMMENT ON COLUMN audit.ingestion_runs.source_checksum IS
    'SHA-256 of the source file (file sources), used for incremental loading';

-- Speeds up the most common question: "latest runs for source X".
CREATE INDEX IF NOT EXISTS ix_ingestion_runs_source_started
    ON audit.ingestion_runs (source_id, started_at DESC);

RESET ROLE;