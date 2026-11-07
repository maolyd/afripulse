{#
    By default dbt names custom schemas "<target schema>_<custom>", e.g.
    "staging_marts". AfriPulse wants exactly "staging", "intermediate", "marts",
    so use the custom schema name as given.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
