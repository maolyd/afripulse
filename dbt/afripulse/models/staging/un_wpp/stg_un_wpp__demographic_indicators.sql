-- One row per country x year from UN World Population Prospects (wide).
-- Rules: F-UN-1 counts converted from thousands to persons (x1000);
-- F-UN-8 year 2101 removed (1 January only); F-UN-9 mid-year population used;
-- F-UN-10 projections flagged from var('un_wpp_projection_start_year').

with source as (

    select * from {{ source('raw', 'un_wpp_demographic_indicators') }}

),

renamed as (

    select
        upper(trim(payload ->> 'ISO3_code'))                         as country_iso3,
        loc_id                                                       as un_location_id,
        year,
        release                                                      as source_release,
        payload ->> 'Variant'                                        as projection_variant,
        (payload ->> 'TPopulation1July')::numeric * 1000             as population_total,
        (payload ->> 'TPopulationMale1July')::numeric * 1000         as population_male,
        (payload ->> 'TPopulationFemale1July')::numeric * 1000       as population_female,
        (payload ->> 'PopDensity')::numeric                          as population_density_per_km2,
        (payload ->> 'MedianAgePop')::numeric                        as median_age_years,
        (payload ->> 'LEx')::numeric                                 as life_expectancy_years,
        (payload ->> 'TFR')::numeric                                 as fertility_rate,
        (payload ->> 'PopGrowthRate')::numeric                       as population_growth_pct,
        (payload ->> 'NetMigrations')::numeric * 1000                as net_migration,
        payload ->> 'Notes'                                          as un_note_code,
        year >= {{ var('un_wpp_projection_start_year') }}            as is_projection,
        _batch_id                                                    as batch_id,
        _ingested_at                                                 as ingested_at
    from source
    where year <= 2100

)

select * from renamed
