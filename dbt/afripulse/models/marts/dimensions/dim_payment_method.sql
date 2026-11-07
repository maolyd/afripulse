-- One row per payment method (seed: payment_methods).
select
    {{ surrogate_key(['payment_method_code']) }}   as payment_method_key,
    payment_method_code,
    payment_method_name,
    is_digital,
    sort_order
from {{ ref('payment_methods') }}
