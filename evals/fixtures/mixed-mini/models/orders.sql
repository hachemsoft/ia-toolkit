select order_id, customer_id, amount
from {{ source('shop', 'raw_orders') }}
