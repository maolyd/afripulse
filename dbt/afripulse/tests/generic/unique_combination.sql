{#
    Fails if any combination of `columns` appears more than once.
    Used to enforce the grain of tables whose key spans several columns.
#}
{% test unique_combination(model, columns) %}

select {{ columns | join(', ') }}, count(*) as occurrences
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1

{% endtest %}
