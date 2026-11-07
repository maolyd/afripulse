-- SYNTHETIC. One row per generated loyalty event (points earned or redeemed).
select
    event_id,
    customer_id,
    retail_txn_id,
    event_type,
    points,
    balance_after,
    event_ts,
    event_ts::date               as event_date,
    is_synthetic,
    generator_run_id
from {{ source('raw_synthetic', 'loyalty_events') }}
