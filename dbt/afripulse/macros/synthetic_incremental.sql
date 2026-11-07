{#
    Incremental strategy for SYNTHETIC transaction facts.

    The generator replaces the whole raw_synthetic dataset in one run, stamping
    every row with that run's generator_run_id. So, on an incremental build:
      1. pre-hook: delete fact rows from any OLDER generator run (they no longer
         exist in raw) -> no stale rows, even if the new dataset is smaller;
      2. select only staging rows whose generator_run_id is not yet in the fact.
    If nothing was regenerated, step 1 deletes nothing and step 2 selects nothing:
    the model finishes in a fraction of a second instead of rebuilding everything.
#}
{% macro delete_stale_synthetic_rows(staging_model) %}
    {% if is_incremental() %}
        delete from {{ this }}
        where generator_run_id not in (
            select distinct generator_run_id from {{ ref(staging_model) }}
        )
    {% endif %}
{% endmacro %}

{% macro only_new_synthetic_runs() %}
    {% if is_incremental() %}
        where generator_run_id not in (select distinct generator_run_id from {{ this }})
    {% endif %}
{% endmacro %}
