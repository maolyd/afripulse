-- SYNTHETIC. One row per generated customer, plus the unknown member
-- (used for mobile money transactions without a counterparty).
-- No snowflake: the country is an attribute here, not a key (ADR 0002, decision 4).

with customers as (

    select
        {{ surrogate_key(['customer_id']) }}   as customer_key,
        customer_id,
        country_iso3,
        city,
        gender,
        age_band,
        signup_date,
        has_mobile_money,
        has_bank_account,
        is_loyalty_member,
        is_synthetic
    from {{ ref('stg_synthetic__customers') }}

),

unknown_member as (

    select
        '-1', 'N/A', 'N/A', 'Not applicable', 'Not applicable', 'Not applicable',
        null::date, false, false, false, true

)

select * from customers
union all
select * from unknown_member
