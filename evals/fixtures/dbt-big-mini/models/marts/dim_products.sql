select product_id, category, price from {{ ref("stg_products") }}
