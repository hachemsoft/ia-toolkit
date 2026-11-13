select store_id, city from {{ ref("stg_stores") }}
