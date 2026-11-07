-- SYNTHETIC. One row per mobile money wallet transaction. Dashboard 4.

select
    f.mm_txn_id,
    d.calendar_date                         as txn_date,
    d.month_start_date                      as txn_month,
    c.country_name,
    c.au_region,
    f.txn_type,
    f.status,
    cu.gender                               as sender_gender,
    cu.age_band                             as sender_age_band,
    m.category                              as merchant_category,
    f.amount_usd,
    f.fee_usd,
    'SYNTHETIC'                             as data_label
from {{ ref('fact_mobile_money') }} as f
inner join {{ ref('dim_date') }} as d on d.date_key = f.date_key
inner join {{ ref('dim_country') }} as c on c.country_key = f.country_key
inner join {{ ref('dim_customer') }} as cu on cu.customer_key = f.customer_key
inner join {{ ref('dim_merchant') }} as m on m.merchant_key = f.merchant_key
