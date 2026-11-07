-- =====================================================================
-- 010_raw_worldbank.sql
-- Raw landing tables for the World Bank sources.
-- Run as: admin, connected to the 'afripulse' database.
-- Idempotent: safe to run more than once.
--
-- Raw-layer design (same for every source):
--   * natural key columns, extracted from the record  -> PRIMARY KEY
--   * payload       : the ORIGINAL record, untouched, as JSONB
--   * _record_hash  : SHA-256 of the payload, to detect changed records
--   * _source_url, _source_release, _batch_id, _ingested_at : lineage
-- Cleaning, typing and renaming happen later, in dbt staging models.
-- =====================================================================

SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS raw.worldbank_countries (
    country_code     text         NOT NULL,
    payload          jsonb        NOT NULL,
    _record_hash     text         NOT NULL,
    _source_url      text         NOT NULL,
    _source_release  text,
    _batch_id        uuid         NOT NULL,
    _ingested_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_worldbank_countries PRIMARY KEY (country_code)
);

COMMENT ON TABLE raw.worldbank_countries IS
    'World Bank /country endpoint, one row per economy or aggregate, as received (F1: aggregates kept in raw, filtered in staging)';

CREATE TABLE IF NOT EXISTS raw.worldbank_indicator_values (
    indicator_code   text         NOT NULL,
    country_iso3     text         NOT NULL,
    year             integer      NOT NULL,
    payload          jsonb        NOT NULL,
    _record_hash     text         NOT NULL,
    _source_url      text         NOT NULL,
    _source_release  text,
    _batch_id        uuid         NOT NULL,
    _ingested_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_worldbank_indicator_values PRIMARY KEY (indicator_code, country_iso3, year)
);

COMMENT ON TABLE raw.worldbank_indicator_values IS
    'World Bank WDI indicator values for African countries, one row per indicator x country x year, as received (nulls kept, F11)';
COMMENT ON COLUMN raw.worldbank_indicator_values._source_release IS
    'The API''s lastupdated date for the indicator at extraction time (F12)';

RESET ROLE;
