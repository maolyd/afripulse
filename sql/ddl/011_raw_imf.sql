-- =====================================================================
-- 011_raw_imf.sql
-- Raw landing table for the IMF World Economic Outlook (DataMapper API).
-- Run as: admin, connected to the 'afripulse' database. Idempotent.
--
-- The release is part of the primary key: each WEO release (April, October)
-- revises past values, so every release is kept side by side (F-IMF-3).
-- =====================================================================

SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS raw.imf_weo_values (
    release          text         NOT NULL,
    indicator_code   text         NOT NULL,
    area_code        text         NOT NULL,
    year             integer      NOT NULL,
    payload          jsonb        NOT NULL,
    _record_hash     text         NOT NULL,
    _source_url      text         NOT NULL,
    _source_release  text,
    _batch_id        uuid         NOT NULL,
    _ingested_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_imf_weo_values PRIMARY KEY (release, indicator_code, area_code, year)
);

COMMENT ON TABLE raw.imf_weo_values IS
    'IMF WEO values for African countries, one row per release x indicator x country x year, including projections (F-IMF-5)';

RESET ROLE;
