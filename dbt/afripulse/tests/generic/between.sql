{# Fails for values outside [min_value, max_value]. Nulls are ignored. #}
{% test between(model, column_name, min_value, max_value) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} < {{ min_value }} or {{ column_name }} > {{ max_value }}

{% endtest %}
