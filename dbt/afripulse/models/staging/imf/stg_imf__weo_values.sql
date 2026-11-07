-- One row per IMF WEO release x indicator x country x year.
-- F-IMF-5: projections are flagged. Provisional rule (sources.yml projection_rule):
-- a value is a projection if its year is on or after the release year
-- (WEO-2026-10 -> 2026 and later are projections).

with source as (

    select * from {{ source('raw', 'imf_weo_values') }}

),

renamed as (

    select
        area_code                                              as country_iso3,
        indicator_code                                         as source_indicator_code,
        year,
        (payload ->> 'value')::numeric                         as value,
        release                                                as source_release,
        substring(release from 5 for 4)::integer               as release_year,
        year >= substring(release from 5 for 4)::integer       as is_projection,
        _batch_id                                              as batch_id,
        _ingested_at                                           as ingested_at
    from source

)

select * from renamed
