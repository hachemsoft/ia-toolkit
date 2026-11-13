select payment_id, order_id, amount, method from {{ source("shop", "payments") }}
