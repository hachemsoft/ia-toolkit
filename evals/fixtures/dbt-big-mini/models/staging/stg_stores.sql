select store_id, city from {{ source("shop", "stores") }}
