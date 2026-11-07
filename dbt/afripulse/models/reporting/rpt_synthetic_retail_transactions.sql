-- SYNTHETIC. One row per retail purchase, with customer, merchant and payment
-- attributes flattened in. Dashboard 5 (retail and consumer transactions).

select
    f.txn_id,
    d.calendar_date                         as txn_date,
    d.month_start_date                      as txn_month,
    d.day_name,
    d.is_weekend,
    d.is_month_end_window,
    c.country_name,
    c.au_region,
    cu.city,
    cu.gender,
    cu.age_band,
    cu.is_loyalty_member,
    m.category                              as merchant_category,
    m.merchant_name,
    pm.payment_method_name                  as payment_method,
    pm.is_digital                           as is_digital_payment,
    f.amount_usd,
    f.item_count,
    'SYNTHETIC'                             as data_label
from {{ ref('fact_retail_transactions') }} as f
inner join {{ ref('dim_date') }} as d on d.date_key = f.date_key
inner join {{ ref('dim_country') }} as c on c.country_key = f.country_key
inner join {{ ref('dim_customer') }} as cu on cu.customer_key = f.customer_key
inner join {{ ref('dim_merchant') }} as m on m.merchant_key = f.merchant_key
inner join {{ ref('dim_payment_method') }} as pm on pm.payment_method_key = f.payment_method_key
