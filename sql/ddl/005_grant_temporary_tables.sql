-- =====================================================================
-- 005_grant_temporary_tables.sql
-- Fix for 003: "REVOKE ALL ON DATABASE afripulse FROM PUBLIC" also removed
-- the TEMPORARY privilege, which every role has by default. The loader stages
-- batches in temporary tables, and dbt uses them for incremental models.
-- Run as: admin, connected to the 'afripulse' database. Idempotent.
-- =====================================================================

GRANT TEMPORARY ON DATABASE afripulse TO afripulse_app, afripulse_dbt;
