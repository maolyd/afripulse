-- SYNTHETIC. One row per generated retail purchase.
select
    txn_id,
    customer_id,
    merchant_id,
    txn_ts,
    txn_ts::date                 as txn_date,
    payment_method               as payment_method_code,
    amount_usd,
    item_count,
    is_synthetic,
    generator_run_id
from {{ source('raw_synthetic', 'retail_transactions') }}
