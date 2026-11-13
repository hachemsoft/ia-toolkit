select order_id, amount from {{ ref("orders") }} where amount < 0
