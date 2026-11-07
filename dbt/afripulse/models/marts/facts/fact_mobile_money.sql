-- SYNTHETIC. Grain: one row per mobile money wallet transaction.
-- Role-playing dimension: dim_customer is used for the sender (customer_key)
-- and for the P2P recipient (counterparty_customer_key). Missing merchant or
-- counterparty -> the unknown member '-1', never null (ADR 0002, decision 6).
{{ config(
    materialized='incremental',
    unique_key='mm_txn_id',
    incremental_strategy='delete+insert',
    pre_hook="{{ delete_stale_synthetic_rows('stg_synthetic__mobile_money_transactions') }}",
    indexes=[
        {'columns': ['mm_txn_id'], 'unique': true},
        {'columns': ['date_key']},
        {'columns': ['country_key', 'date_key']},
        {'columns': ['customer_key']},
    ]
) }}

with transactions as (

    select * from {{ ref('stg_synthetic__mobile_money_transactions') }}
    {{ only_new_synthetic_runs() }}

),

customers as (

    select customer_id, country_iso3 from {{ ref('stg_synthetic__customers') }}

)

select
    t.mm_txn_id,
    to_char(t.txn_date, 'YYYYMMDD')::integer             as date_key,
    {{ surrogate_key(['c.country_iso3']) }}              as country_key,
    {{ surrogate_key(['t.customer_id']) }}               as customer_key,
    case when t.counterparty_customer_id is null then '-1'
         else {{ surrogate_key(['t.counterparty_customer_id']) }} end
                                                         as counterparty_customer_key,
    case when t.merchant_id is null then '-1'
         else {{ surrogate_key(['t.merchant_id']) }} end as merchant_key,
    t.retail_txn_id,
    t.txn_type,
    t.status,
    t.txn_ts,
    t.amount_usd,
    t.fee_usd,
    t.is_synthetic,
    t.generator_run_id
from transactions as t
inner join customers as c
    on c.customer_id = t.customer_id
