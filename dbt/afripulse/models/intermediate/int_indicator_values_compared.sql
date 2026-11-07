-- Adds two comparison flags to every indicator value:
--   is_default_source  this source is the indicator's default (dim_indicator)
--   sources_disagree   another source differs by more than the threshold
--                      (percentage-point indicators only; F-IMF-9)

with values_unioned as (

    select * from {{ ref('int_indicator_values_unioned') }}

),

concepts as (

    select indicator_code, unit, default_source_id
    from {{ ref('indicator_concepts') }}

),

compared as (

    select
        v.*,
        v.source_id = c.default_source_id                         as is_default_source,
        c.unit,
        count(*) over (
            partition by v.country_iso3, v.year, v.indicator_code
        )                                                         as sources_available,
        max(v.value) over (partition by v.country_iso3, v.year, v.indicator_code)
          - min(v.value) over (partition by v.country_iso3, v.year, v.indicator_code)
                                                                  as source_spread
    from values_unioned as v
    inner join concepts as c
        on c.indicator_code = v.indicator_code

)

select
    country_iso3,
    year,
    indicator_code,
    source_id,
    source_release,
    value,
    is_projection,
    is_default_source,
    sources_available,
    coalesce(
        unit = '%'
        and sources_available > 1
        and source_spread > {{ var('sources_disagree_threshold_pp') }},
        false
    )                                                             as sources_disagree
from compared
