-- One row per data source, with its licence (seed: data_sources).
select
    {{ surrogate_key(['source_id']) }}   as source_key,
    source_id,
    provider,
    dataset,
    licence,
    is_synthetic,
    homepage
from {{ ref('data_sources') }}
