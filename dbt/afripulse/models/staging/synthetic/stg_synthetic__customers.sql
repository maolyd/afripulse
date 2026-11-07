-- SYNTHETIC. One row per generated customer.
select
    customer_id,
    country_iso3,
    city,
    gender,
    age_band,
    signup_date,
    has_mobile_money,
    has_bank_account,
    is_loyalty_member,
    is_synthetic,
    generator_run_id
from {{ source('raw_synthetic', 'customers') }}
