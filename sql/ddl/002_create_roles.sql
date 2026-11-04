-- =====================================================================
-- 002_create_roles.sql
-- Creates one login role per platform component (least privilege).
-- Run as: admin (superuser).
-- Passwords are NOT set here. Secrets never go into files tracked by Git.
-- They are set interactively afterwards with psql's \password command.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'afripulse_app') THEN
        CREATE ROLE afripulse_app LOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'afripulse_dbt') THEN
        CREATE ROLE afripulse_dbt LOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'afripulse_reader') THEN
        CREATE ROLE afripulse_reader LOGIN;
    END IF;
END
$$;

COMMENT ON ROLE afripulse_app    IS 'Python ingestion pipeline: owns raw, raw_synthetic and audit';
COMMENT ON ROLE afripulse_dbt    IS 'dbt transformations: reads raw layers, builds staging/intermediate/marts';
COMMENT ON ROLE afripulse_reader IS 'BI / Tableau: read-only access to marts';