select customer_id, customer_email, country, first_order_date from {{ ref("stg_customers") }}
