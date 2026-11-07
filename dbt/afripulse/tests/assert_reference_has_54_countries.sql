-- ADR 0001: AfriPulse covers exactly the 54 UN-recognised African Union members.
-- A singular test: returns a row (and fails) if the count is anything else.
select count(*) as countries
from {{ ref('african_countries') }}
having count(*) <> 54
