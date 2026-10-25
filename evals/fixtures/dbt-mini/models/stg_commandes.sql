select order_id, customer_id, order_date, amount from {{ source("shop","orders") }}
