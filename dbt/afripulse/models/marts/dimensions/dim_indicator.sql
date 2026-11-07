-- One row per AfriPulse indicator concept (seed: indicator_concepts).
select
    {{ surrogate_key(['indicator_code']) }}   as indicator_key,
    indicator_code,
    indicator_name,
    unit,
    theme,
    default_source_id,
    higher_is_better
from {{ ref('indicator_concepts') }}
