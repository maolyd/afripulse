-- =====================================================================
-- 006_audit_validation_results.sql
-- One row per validation check per ingestion run.
-- Run as: admin, connected to the 'afripulse' database. Idempotent.
-- =====================================================================

SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS audit.validation_results (
    run_id       uuid         NOT NULL
        REFERENCES audit.ingestion_runs (run_id) ON DELETE CASCADE,
    check_name   text         NOT NULL,
    severity     text         NOT NULL CHECK (severity IN ('error', 'warning')),
    passed       boolean      NOT NULL,
    observed     numeric,
    threshold    numeric,
    message      text         NOT NULL,
    checked_at   timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_validation_results PRIMARY KEY (run_id, check_name)
);

COMMENT ON TABLE audit.validation_results IS
    'Pre-load validation checks: errors block the load, warnings are recorded and the load continues';

RESET ROLE;
