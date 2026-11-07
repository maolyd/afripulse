-- One row per World Bank indicator x country x year WITH a value.
-- Rules: G7 rows without a value are removed here (kept in raw, F11);
-- F6 year already an integer key; F12 lastupdated kept as the source release.

with source as (

    select * from {{ source('raw', 'worldbank_indicator_values') }}

),

renamed as (

    select
        country_iso3,
        indicator_code                                         as source_indicator_code,
        year,
        (payload ->> 'value')::numeric                         as value,
        nullif(trim(payload ->> 'obs_status'), '')             as observation_status,
        _source_release                                        as source_release,
        _batch_id                                              as batch_id,
        _ingested_at                                           as ingested_at
    from source
    where payload ->> 'value' is not null

)

select * from renamed
