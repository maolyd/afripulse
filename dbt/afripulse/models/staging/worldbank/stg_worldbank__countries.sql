-- One row per World Bank economy or aggregate, cleaned and typed.
-- Rules applied (docs/source_to_target_mapping.md): G3 trim text (F3), F5 names,
-- F6 coordinates cast from text; empty strings become null. Aggregates are KEPT and flagged (F1);
-- the country dimension filters to the reference list (ADR 0001).

with source as (

    select * from {{ source('raw', 'worldbank_countries') }}

),

renamed as (

    select
        upper(trim(payload ->> 'id'))                         as country_iso3,
        upper(trim(payload ->> 'iso2Code'))                   as country_iso2,
        trim(payload ->> 'name')                              as country_name_wb,
        nullif(trim(payload -> 'region' ->> 'id'), '')        as wb_region_code,
        trim(payload -> 'region' ->> 'value')                 as wb_region_name,
        nullif(trim(payload -> 'incomeLevel' ->> 'id'), '')   as income_group_code,
        trim(payload -> 'incomeLevel' ->> 'value')            as income_group_name,
        trim(payload -> 'lendingType' ->> 'value')            as lending_type,
        nullif(trim(payload ->> 'capitalCity'), '')           as capital_city,
        nullif(trim(payload ->> 'latitude'), '')::numeric     as latitude,
        nullif(trim(payload ->> 'longitude'), '')::numeric    as longitude,
        trim(payload -> 'region' ->> 'value') = 'Aggregates'  as is_aggregate,
        _source_release                                       as source_release,
        _batch_id                                             as batch_id,
        _ingested_at                                          as ingested_at
    from source

)

select * from renamed
