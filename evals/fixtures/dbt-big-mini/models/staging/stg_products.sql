select product_id, category, price from {{ source("shop", "products") }}
