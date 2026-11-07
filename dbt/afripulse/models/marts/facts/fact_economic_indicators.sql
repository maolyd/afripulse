-- Grain: one row per country x year x indicator x source (latest release).
-- Periodic snapshot of REAL statistics. value is NON-ADDITIVE (rates, per-capita
-- values): never sum it; average with population weights (data dictionary).
{{ config(
    indexes=[
        {'columns': ['country_key', 'indicator_key', 'source_key', 'year'], 'unique': true},
        {'columns': ['indicator_key', 'year']},
    ]
) }}

select
    {{ surrogate_key(['v.country_iso3']) }}     as country_key,
    {{ surrogate_key(['v.indicator_code']) }}   as indicator_key,
    {{ surrogate_key(['v.source_id']) }}        as source_key,
    v.year,
    v.source_release,
    v.value,
    v.is_projection,
    v.is_default_source,
    v.sources_disagree
from {{ ref('int_indicator_values_compared') }} as v
