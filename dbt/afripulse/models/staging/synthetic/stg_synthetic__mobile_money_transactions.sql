-- SYNTHETIC. One row per generated mobile money wallet transaction.
select
    mm_txn_id,
    customer_id,
    counterparty_customer_id,
    merchant_id,
    retail_txn_id,
    txn_type,
    status,
    txn_ts,
    txn_ts::date                 as txn_date,
    amount_usd,
    fee_usd,
    is_synthetic,
    generator_run_id
from {{ source('raw_synthetic', 'mobile_money_transactions') }}
