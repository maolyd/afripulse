-- Type 2 history of World Bank income groups for the countries in scope.
-- Use to analyse a country "as classified at the time": join on country_key AND
-- the date falling between valid_from and valid_to.

select
    {{ surrogate_key(['snap.country_iso3', 'snap.dbt_valid_from']) }}   as country_income_key,
    {{ surrogate_key(['snap.country_iso3']) }}                          as country_key,
    snap.country_iso3,
    snap.income_group_code,
    snap.income_group_name,
    snap.dbt_valid_from                                                 as valid_from,
    snap.dbt_valid_to                                                   as valid_to,
    snap.dbt_valid_to is null                                           as is_current
from {{ ref('snap_worldbank_country_income') }} as snap
inner join {{ ref('african_countries') }} as reference
    on reference.iso3 = snap.country_iso3
