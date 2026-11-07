-- SYNTHETIC. One row per loyalty member: spend, points and engagement.
-- Dashboard 6 (customer loyalty). balance_now is the LATEST balance per
-- customer (semi-additive measure handled correctly here, not in Tableau).

with members as (

    select * from {{ ref('dim_customer') }}
    where is_loyalty_member and customer_key <> '-1'

),

purchases as (

    select customer_key, count(*) as purchases, sum(amount_usd) as spend_usd,
           max(txn_ts)::date as last_purchase_date
    from {{ ref('fact_retail_transactions') }}
    group by customer_key

),

points as (

    select customer_key,
           sum(points_earned)                               as points_earned,
           sum(points_redeemed)                             as points_redeemed,
           count(*) filter (where event_type = 'redeem')    as redemptions,
           (array_agg(balance_after order by event_ts desc, event_id desc))[1] as balance_now
    from {{ ref('fact_loyalty_transactions') }}
    group by customer_key

),

period_end as (

    select max(txn_ts)::date as as_of_date from {{ ref('fact_retail_transactions') }}

)

select
    mb.customer_id,
    mb.country_iso3,
    c.country_name,
    mb.city,
    mb.gender,
    mb.age_band,
    mb.signup_date,
    mb.has_mobile_money,
    mb.has_bank_account,
    coalesce(pu.purchases, 0)                               as purchases,
    coalesce(pu.spend_usd, 0)                               as spend_usd,
    coalesce(pt.points_earned, 0)                           as points_earned,
    coalesce(pt.points_redeemed, 0)                         as points_redeemed,
    coalesce(pt.redemptions, 0)                             as redemptions,
    coalesce(pt.balance_now, 0)                             as balance_now,
    pu.last_purchase_date,
    pe.as_of_date - pu.last_purchase_date                   as days_since_last_purchase,
    case
        when pu.last_purchase_date is null then 'Never purchased'
        when pe.as_of_date - pu.last_purchase_date <= 30 then 'Active (30 days)'
        when pe.as_of_date - pu.last_purchase_date <= 90 then 'Lapsing (31-90 days)'
        else 'Dormant (90+ days)'
    end                                                     as engagement_status,
    coalesce(pt.redemptions, 0) = 0
        and coalesce(pt.points_earned, 0) > 0               as never_redeemed,
    'SYNTHETIC'                                             as data_label
from members as mb
inner join {{ ref('dim_country') }} as c on c.country_iso3 = mb.country_iso3
left join purchases as pu on pu.customer_key = mb.customer_key
left join points as pt on pt.customer_key = mb.customer_key
cross join period_end as pe
