-- REAL statistics. One row per country x year: every indicator side by side,
-- default source, actual values only (no projections). Dashboards 1-4.
-- Wide and denormalised on purpose: Tableau Public works from flat extracts.

with values_default as (

    select country_iso3, year, indicator_code, value
    from {{ ref('int_indicator_values_compared') }}
    where is_default_source
      and year >= 2000
      -- Actuals only, EXCEPT UN demographic values up to the current year: WPP 2024
      -- labels 2024+ as projections, but they are the official current estimates
      -- (the World Bank publishes the same numbers, F-UN-2). Without them, 2024
      -- has no population and population-weighted averages break.
      and (
          not is_projection
          or (source_id = 'un_wpp' and year <= extract(year from current_date)::integer)
      )

),

pivoted as (

    select
        country_iso3,
        year,
        {%- for code in [
            'population_total', 'urban_population_pct', 'median_age_years',
            'life_expectancy_years', 'gdp_current_usd', 'gdp_per_capita_current_usd',
            'gdp_real_growth_pct', 'inflation_cpi_pct', 'internet_users_pct',
            'mobile_subscriptions_per_100', 'fixed_broadband_per_100',
            'account_ownership_pct', 'fi_account_pct', 'mobile_money_account_pct',
            'borrowed_any_pct'
        ] %}
        max(value) filter (where indicator_code = '{{ code }}') as {{ code }}
        {%- if not loop.last %},{% endif %}
        {%- endfor %}
    from values_default
    group by country_iso3, year

)

select
    c.country_iso3,
    c.country_name,
    c.au_region,
    c.income_group_name,
    c.latitude,
    c.longitude,
    c.is_synthetic_market,
    p.year,
    p.population_total,
    round(p.population_total / 1e6, 2)                          as population_millions,
    p.urban_population_pct,
    p.median_age_years,
    p.life_expectancy_years,
    p.gdp_current_usd,
    round(p.gdp_current_usd / 1e9, 2)                           as gdp_billions_usd,
    p.gdp_per_capita_current_usd,
    p.gdp_real_growth_pct,
    p.inflation_cpi_pct,
    p.internet_users_pct,
    p.mobile_subscriptions_per_100,
    p.fixed_broadband_per_100,
    p.account_ownership_pct,
    p.fi_account_pct,
    p.mobile_money_account_pct,
    p.borrowed_any_pct,
    -- F9: so a dashboard can say "as of 2017" instead of implying it is current
    max(p.year) filter (where p.internet_users_pct is not null)
        over (partition by p.country_iso3)                      as latest_internet_year,
    max(p.year) filter (where p.mobile_money_account_pct is not null)
        over (partition by p.country_iso3)                      as latest_findex_year,
    'REAL'                                                      as data_label
from pivoted as p
inner join {{ ref('dim_country') }} as c
    on c.country_iso3 = p.country_iso3
