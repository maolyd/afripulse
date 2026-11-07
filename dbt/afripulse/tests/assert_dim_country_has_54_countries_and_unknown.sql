-- dim_country must hold the 54 countries of ADR 0001 plus exactly one unknown member.
select count(*) filter (where country_key <> '-1') as countries,
       count(*) filter (where country_key = '-1')  as unknown_members
from {{ ref('dim_country') }}
having count(*) filter (where country_key <> '-1') <> 54
    or count(*) filter (where country_key = '-1') <> 1
