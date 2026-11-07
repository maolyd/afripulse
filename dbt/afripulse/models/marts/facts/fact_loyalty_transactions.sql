-- SYNTHETIC. Grain: one row per loyalty event (points earned or redeemed).
-- points_earned / points_redeemed are ADDITIVE (split into two columns so they
-- can simply be summed). balance_after is SEMI-ADDITIVE: never sum it over time.
{{ config(
    materialized='incremental',
    unique_key='event_id',
    incremental_strategy='delete+insert',
    pre_hook="{{ delete_stale_synthetic_rows('stg_synthetic__loyalty_events') }}",
    indexes=[
        {'columns': ['event_id'], 'unique': true},
        {'columns': ['date_key']},
        {'columns': ['customer_key', 'event_ts']},
    ]
) }}

with events as (

    select * from {{ ref('stg_synthetic__loyalty_events') }}
    {{ only_new_synthetic_runs() }}

),

customers as (

    select customer_id, country_iso3 from {{ ref('stg_synthetic__customers') }}

)

select
    e.event_id,
    to_char(e.event_date, 'YYYYMMDD')::integer                          as date_key,
    {{ surrogate_key(['c.country_iso3']) }}                             as country_key,
    {{ surrogate_key(['e.customer_id']) }}                              as customer_key,
    e.retail_txn_id,
    e.event_type,
    case when e.event_type = 'earn' then e.points else 0 end            as points_earned,
    case when e.event_type = 'redeem' then e.points else 0 end          as points_redeemed,
    e.balance_after,
    e.event_ts,
    e.is_synthetic,
    e.generator_run_id
from events as e
inner join customers as c
    on c.customer_id = e.customer_id
