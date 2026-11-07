-- Every indicator value from every real source, in ONE long, conformed shape:
--   country_iso3 | year | indicator_code (AfriPulse concept) | source_id | value
-- Source codes are mapped to concepts with the indicator_source_map seed, so
-- NGDP_RPCH (IMF) and NY.GDP.MKTP.KD.ZG (World Bank) both become gdp_real_growth_pct.
-- Units are already standardised in staging (% as 0-100, counts in persons).

with source_map as (

    select * from {{ ref('indicator_source_map') }}

),

worldbank as (

    select
        wb.country_iso3,
        wb.year,
        map.indicator_code,
        'worldbank_wdi'                 as source_id,
        wb.source_release,
        wb.value,
        false                           as is_projection
    from {{ ref('stg_worldbank__indicator_values') }} as wb
    inner join source_map as map
        on map.source_id = 'worldbank_wdi'
        and map.source_indicator_code = wb.source_indicator_code

),

imf_latest_release as (

    -- Keep only the newest WEO release; older releases stay in raw for history.
    -- 'WEO-YYYY-MM' sorts correctly as text.
    select max(source_release) as source_release
    from {{ ref('stg_imf__weo_values') }}

),

imf as (

    select
        imf.country_iso3,
        imf.year,
        map.indicator_code,
        'imf_weo'                       as source_id,
        imf.source_release,
        imf.value,
        imf.is_projection
    from {{ ref('stg_imf__weo_values') }} as imf
    inner join imf_latest_release as latest
        on latest.source_release = imf.source_release
    inner join source_map as map
        on map.source_id = 'imf_weo'
        and map.source_indicator_code = imf.source_indicator_code

),

un_wpp as (

    -- The UN model is wide (one column per measure): unpivot the mapped columns.
    select
        wpp.country_iso3,
        wpp.year,
        map.indicator_code,
        'un_wpp'                        as source_id,
        wpp.source_release,
        measures.value,
        wpp.is_projection
    from {{ ref('stg_un_wpp__demographic_indicators') }} as wpp
    cross join lateral (
        values
            ('population_total', wpp.population_total),
            ('median_age_years', wpp.median_age_years),
            ('life_expectancy_years', wpp.life_expectancy_years),
            ('fertility_rate', wpp.fertility_rate),
            ('population_growth_pct', wpp.population_growth_pct)
    ) as measures (source_indicator_code, value)
    inner join source_map as map
        on map.source_id = 'un_wpp'
        and map.source_indicator_code = measures.source_indicator_code
    where measures.value is not null

),

findex as (

    -- Headline figures only (all adults); demographic splits stay in staging.
    select
        fx.country_iso3,
        fx.year,
        map.indicator_code,
        'findex'                        as source_id,
        fx.source_release,
        fx.value,
        false                           as is_projection
    from {{ ref('stg_findex__values') }} as fx
    inner join source_map as map
        on map.source_id = 'findex'
        and map.source_indicator_code = fx.source_indicator_code
    where fx.demographic_group = 'all'

)

select * from worldbank
union all
select * from imf
union all
select * from un_wpp
union all
select * from findex
