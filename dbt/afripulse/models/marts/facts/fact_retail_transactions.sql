-- SYNTHETIC. Grain: one row per retail purchase. Transaction fact.
-- Keys are computed with the same hash macro as the dimensions, so no join is
-- needed to look them up; relationships tests prove every key exists.
{{ config(
    materialized='incremental',
    unique_key='txn_id',
    incremental_strategy='delete+insert',
    pre_hook="{{ delete_stale_synthetic_rows('stg_synthetic__retail_transactions') }}",
    indexes=[
        {'columns': ['txn_id'], 'unique': true},
        {'columns': ['date_key']},
        {'columns': ['country_key', 'date_key']},
        {'columns': ['customer_key']},
        {'columns': ['merchant_key']},
    ]
) }}

with transactions as (

    select * from {{ ref('stg_synthetic__retail_transactions') }}
    {{ only_new_synthetic_runs() }}

),

customers as (

    select customer_id, country_iso3 from {{ ref('stg_synthetic__customers') }}

)

select
    t.txn_id,
    to_char(t.txn_date, 'YYYYMMDD')::integer             as date_key,
    {{ surrogate_key(['c.country_iso3']) }}              as country_key,
    {{ surrogate_key(['t.customer_id']) }}               as customer_key,
    {{ surrogate_key(['t.merchant_id']) }}               as merchant_key,
    {{ surrogate_key(['t.payment_method_code']) }}       as payment_method_key,
    t.txn_ts,
    t.amount_usd,
    t.item_count,
    t.is_synthetic,
    t.generator_run_id
from transactions as t
inner join customers as c
    on c.customer_id = t.customer_id
