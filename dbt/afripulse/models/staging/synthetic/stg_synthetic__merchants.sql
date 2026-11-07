-- SYNTHETIC. One row per generated merchant.
select
    merchant_id,
    merchant_name,
    country_iso3,
    city,
    category,
    accepts_card,
    accepts_mobile_money,
    onboard_date,
    is_synthetic,
    generator_run_id
from {{ source('raw_synthetic', 'merchants') }}
