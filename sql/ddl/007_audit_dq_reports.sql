-- =====================================================================
-- 007_audit_dq_reports.sql
-- One row per data quality report: the overall status and a summary of
-- every check, so data quality can be tracked over time with SQL.
-- Also lets the ingestion role READ the marts (to measure coverage), by
-- making it a member of the read-only reporting role. It still cannot
-- change anything in the marts.
-- Run as: admin, connected to the 'afripulse' database. Idempotent.
-- =====================================================================

SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS audit.dq_reports (
    report_id      uuid         PRIMARY KEY,
    generated_at   timestamptz  NOT NULL DEFAULT now(),
    status         text         NOT NULL CHECK (status IN ('GREEN', 'AMBER', 'RED')),
    red_issues     integer      NOT NULL,
    amber_issues   integer      NOT NULL,
    summary        jsonb        NOT NULL,
    report_path    text
);

COMMENT ON TABLE audit.dq_reports IS
    'Data quality report per pipeline run: GREEN / AMBER / RED with all check results in summary';

RESET ROLE;

GRANT afripulse_reader TO afripulse_app;
