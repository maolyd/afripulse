-- Type 2 integrity: every country has exactly one current (open) income period.
select country_key, count(*) as current_rows
from {{ ref('dim_country_income_history') }}
where is_current
group by country_key
having count(*) <> 1
