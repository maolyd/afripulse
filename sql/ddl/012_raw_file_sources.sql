-- =====================================================================
-- 012_raw_file_sources.sql
-- Raw landing tables for the downloaded file sources (UN WPP, Findex).
-- Run as: admin, connected to the 'afripulse' database. Idempotent.
--
-- payload holds the whole source row, every value as TEXT exactly as it
-- appears in the file (empty cells as null). Units, types and renames are
-- applied in dbt staging (F-UN-1, F-FX-3).
-- =====================================================================

SET ROLE afripulse_app;

CREATE TABLE IF NOT EXISTS raw.un_wpp_demographic_indicators (
    release          text         NOT NULL,
    loc_id           integer      NOT NULL,
    year             integer      NOT NULL,
    payload          jsonb        NOT NULL,
    _record_hash     text         NOT NULL,
    _source_url      text         NOT NULL,
    _source_release  text,
    _batch_id        uuid         NOT NULL,
    _ingested_at     timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_un_wpp_demographic_indicators PRIMARY KEY (release, loc_id, year)
);

COMMENT ON TABLE raw.un_wpp_demographic_indicators IS
    'UN WPP demographic indicators (Medium variant) for African countries, one row per release x location x year (F-UN-7). Counts in thousands (F-UN-1).';

CREATE TABLE IF NOT EXISTS raw.findex_values (
    release               text         NOT NULL,
    codewb                text         NOT NULL,
    year                  integer      NOT NULL,
    demographic_group     text         NOT NULL,
    demographic_subgroup  text         NOT NULL,
    payload               jsonb        NOT NULL,
    _record_hash          text         NOT NULL,
    _source_url           text         NOT NULL,
    _source_release       text,
    _batch_id             uuid         NOT NULL,
    _ingested_at          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT pk_findex_values
        PRIMARY KEY (release, codewb, year, demographic_group, demographic_subgroup)
);

COMMENT ON TABLE raw.findex_values IS
    'Global Findex rows for African countries, one row per release x country x year x demographic group (F-FX-4). Values are fractions 0-1 (F-FX-3).';

RESET ROLE;
