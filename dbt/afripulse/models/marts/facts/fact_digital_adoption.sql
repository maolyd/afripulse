-- Grain: one row per country x year. Default sources, actual values only.
-- A WIDE view of fact_economic_indicators for side-by-side dashboards (ADR 0002,
-- decision 2): built from the same intermediate model, so numbers always agree.
{{ config(indexes=[{'columns': ['country_key', 'year'], 'unique': true}]) }}

with default_actuals as (

    select country_iso3, year, indicator_code, value
    from {{ ref('int_indicator_values_compared') }}
    where is_default_source
      -- Actuals only, except UN demographic estimates up to the current year
      -- (WPP 2024 labels 2024+ as projections; see rpt_country_year).
      and (
          not is_projection
          or (source_id = 'un_wpp' and year <= extract(year from current_date)::integer)
      )

),

pivoted as (

    select
        country_iso3,
        year,
        max(value) filter (where indicator_code = 'internet_users_pct')            as internet_users_pct,
        max(value) filter (where indicator_code = 'mobile_subscriptions_per_100')  as mobile_subscriptions_per_100,
        max(value) filter (where indicator_code = 'fixed_broadband_per_100')       as fixed_broadband_per_100,
        max(value) filter (where indicator_code = 'account_ownership_pct')         as account_ownership_pct,
        max(value) filter (where indicator_code = 'mobile_money_account_pct')      as mobile_money_account_pct,
        max(value) filter (where indicator_code = 'population_total')              as population_total
    from default_actuals
    group by country_iso3, year

)

select
    {{ surrogate_key(['country_iso3']) }}       as country_key,
    year,
    internet_users_pct,
    mobile_subscriptions_per_100,
    fixed_broadband_per_100,
    account_ownership_pct,
    mobile_money_account_pct,
    population_total,
    -- F9: the most recent year with internet data for this country, so
    -- dashboards can say "as of 2017" instead of implying it is current.
    max(year) filter (where internet_users_pct is not null)
        over (partition by country_iso3)       as latest_internet_year
from pivoted
