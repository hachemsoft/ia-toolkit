select customer_id, customer_email, country, created_at from {{ source("shop", "customers") }}
