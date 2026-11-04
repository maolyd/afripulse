-- =====================================================================
-- 001_create_database.sql
-- Creates the AfriPulse database.
-- Run as: admin (superuser), connected to the 'postgres' database.
-- Idempotent: safe to run more than once.
-- =====================================================================

-- PostgreSQL has no "CREATE DATABASE IF NOT EXISTS", so we build the
-- statement only when the database is missing, then \gexec runs it.
SELECT 'CREATE DATABASE afripulse'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'afripulse')
\gexec

COMMENT ON DATABASE afripulse IS
    'AfriPulse: African Digital Economy and Consumer Intelligence Data Platform';