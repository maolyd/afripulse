-- Accounting check: for every customer, earned - redeemed must equal the
-- balance after their last event. A failure means points were lost or invented.
with totals as (
    select
        customer_key,
        sum(points_earned) - sum(points_redeemed) as net_points
    from {{ ref('fact_loyalty_transactions') }}
    group by customer_key
),
last_balance as (
    select distinct on (customer_key) customer_key, balance_after
    from {{ ref('fact_loyalty_transactions') }}
    order by customer_key, event_ts desc, event_id desc
)
select t.customer_key, t.net_points, l.balance_after
from totals t
join last_balance l using (customer_key)
where t.net_points <> l.balance_after
