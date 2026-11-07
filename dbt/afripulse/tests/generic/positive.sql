{# Fails for values that are zero or negative. Nulls are ignored. #}
{% test positive(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} <= 0

{% endtest %}
