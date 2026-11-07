-- One row per Findex release x country x year x demographic group x indicator.
-- The raw table is WIDE (466 columns in the payload); this model UNPIVOTS only
-- the configured indicators (seed indicator_source_map) into rows.
-- Rules: F-FX-3 fractions converted to percent (x100); F-FX-8 2021 and 2022
-- treated as one survey wave; F-FX-9 ".s" sub-sample columns are not mapped.

with source as (

    select * from {{ source('raw', 'findex_values') }}

),

indicators as (

    select source_indicator_code
    from {{ ref('indicator_source_map') }}
    where source_id = 'findex'

),

unpivoted as (

    select
        source.codewb                                                as country_iso3,
        source.year,
        source.demographic_group,
        source.demographic_subgroup,
        indicators.source_indicator_code,
        (source.payload ->> indicators.source_indicator_code)::numeric * 100 as value,
        (source.payload ->> 'pop_adult')::numeric                    as adult_population,
        case when source.year in (2021, 2022) then 2021 else source.year end as survey_wave,
        source.release                                               as source_release,
        source._batch_id                                             as batch_id,
        source._ingested_at                                          as ingested_at
    from source
    cross join indicators
    where source.payload ->> indicators.source_indicator_code is not null

)

select * from unpivoted
