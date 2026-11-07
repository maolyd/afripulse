-- One row per calendar day between var('date_spine_start') and var('date_spine_end').
-- date_key is a readable integer, YYYYMMDD (ADR 0002, decision 5).

with days as (

    select generate_series(
        date '{{ var("date_spine_start") }}',
        date '{{ var("date_spine_end") }}',
        interval '1 day'
    )::date as calendar_date

)

select
    to_char(calendar_date, 'YYYYMMDD')::integer           as date_key,
    calendar_date,
    extract(year from calendar_date)::integer             as year,
    extract(quarter from calendar_date)::integer          as quarter,
    extract(month from calendar_date)::integer            as month,
    trim(to_char(calendar_date, 'Month'))                 as month_name,
    extract(day from calendar_date)::integer              as day_of_month,
    trim(to_char(calendar_date, 'Day'))                   as day_name,
    extract(isodow from calendar_date)::integer           as iso_day_of_week,
    extract(week from calendar_date)::integer             as iso_week,
    extract(isodow from calendar_date) in (6, 7)          as is_weekend,
    extract(day from calendar_date) >= 25                 as is_month_end_window,
    date_trunc('month', calendar_date)::date              as month_start_date
from days
