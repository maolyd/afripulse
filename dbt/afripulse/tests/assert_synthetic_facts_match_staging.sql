-- The incremental facts must hold exactly the rows currently in staging:
-- no missing rows (incremental filter too strict) and no stale rows from an
-- older generator run (pre-hook failed). Returns a row per mismatching fact.
with counts as (
    select 'fact_retail_transactions' as fact,
           (select count(*) from {{ ref('fact_retail_transactions') }}) as fact_rows,
           (select count(*) from {{ ref('stg_synthetic__retail_transactions') }}) as staging_rows
    union all
    select 'fact_mobile_money',
           (select count(*) from {{ ref('fact_mobile_money') }}),
           (select count(*) from {{ ref('stg_synthetic__mobile_money_transactions') }})
    union all
    select 'fact_loyalty_transactions',
           (select count(*) from {{ ref('fact_loyalty_transactions') }}),
           (select count(*) from {{ ref('stg_synthetic__loyalty_events') }})
)
select * from counts where fact_rows <> staging_rows
