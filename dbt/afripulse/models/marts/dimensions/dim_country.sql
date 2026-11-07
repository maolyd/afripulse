-- One row per African country in scope (ADR 0001), plus the unknown member.
-- Built from OUR reference list, enriched with World Bank attributes.
-- SCD Type 1: the current income group (history: snapshot, Task 5.5).

with reference as (

    select * from {{ ref('african_countries') }}

),

worldbank as (

    select * from {{ ref('stg_worldbank__countries') }}
    where not is_aggregate

),

synthetic_markets as (

    select distinct country_iso3 from {{ ref('stg_synthetic__customers') }}

),

countries as (

    select
        {{ surrogate_key(['reference.iso3']) }}            as country_key,
        reference.iso3                                     as country_iso3,
        reference.iso2                                     as country_iso2,
        reference.country_name,
        reference.country_name_wb,
        reference.au_region,
        worldbank.wb_region_name,
        worldbank.income_group_code,
        worldbank.income_group_name,
        reference.capital_city,
        reference.latitude,
        reference.longitude,
        synthetic_markets.country_iso3 is not null         as is_synthetic_market
    from reference
    left join worldbank
        on worldbank.country_iso3 = reference.iso3
    left join synthetic_markets
        on synthetic_markets.country_iso3 = reference.iso3

),

unknown_member as (

    select
        '-1', 'N/A', 'N/A', 'Not applicable', 'Not applicable', 'Not applicable',
        null, null, null, null, null::numeric, null::numeric, false

)

select * from countries
union all
select * from unknown_member
