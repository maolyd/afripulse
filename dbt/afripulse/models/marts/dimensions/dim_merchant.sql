-- SYNTHETIC. One row per generated merchant, plus the unknown member
-- (used for mobile money transactions that are not merchant payments).

with merchants as (

    select
        {{ surrogate_key(['merchant_id']) }}   as merchant_key,
        merchant_id,
        merchant_name,
        country_iso3,
        city,
        category,
        accepts_card,
        accepts_mobile_money,
        onboard_date,
        is_synthetic
    from {{ ref('stg_synthetic__merchants') }}

),

unknown_member as (

    select
        '-1', 'N/A', 'Not applicable', 'N/A', 'Not applicable', 'Not applicable',
        false, false, null::date, true

)

select * from merchants
union all
select * from unknown_member
