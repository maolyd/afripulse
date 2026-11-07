{#
    Deterministic surrogate key: md5 hash of one or more columns (ADR 0002).
    Same input -> same key on every rebuild. Nulls are replaced by a marker so
    that (null, 'a') and ('', 'a') do not collide.
    Equivalent to dbt_utils.generate_surrogate_key, without the dependency.

    Usage: {{ surrogate_key(['country_iso3']) }}
#}
{% macro surrogate_key(columns) -%}
    md5(
        {%- for column in columns %}
        coalesce(cast({{ column }} as text), '_null_')
        {%- if not loop.last %} || '|' || {% endif -%}
        {% endfor %}
    )
{%- endmacro %}
