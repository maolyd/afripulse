-- REAL statistics. One row per country x year x indicator x source, including
-- projections. For comparing sources (IMF vs World Bank) and showing forecasts.

select
    c.country_iso3,
    c.country_name,
    c.au_region,
    v.year,
    i.indicator_name,
    i.indicator_code,
    i.unit,
    i.theme,
    s.provider                      as source_provider,
    v.source_id,
    v.source_release,
    v.value,
    v.is_projection,
    case when v.is_projection then 'Projection' else 'Actual' end as value_type,
    v.is_default_source,
    v.sources_disagree,
    'REAL'                          as data_label
from {{ ref('int_indicator_values_compared') }} as v
inner join {{ ref('dim_country') }} as c on c.country_iso3 = v.country_iso3
inner join {{ ref('dim_indicator') }} as i on i.indicator_code = v.indicator_code
inner join {{ ref('dim_source') }} as s on s.source_id = v.source_id
