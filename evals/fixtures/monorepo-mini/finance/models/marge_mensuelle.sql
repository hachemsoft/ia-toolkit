-- grain: one month
select date_trunc(order_date, month) as mois, sum(amount) - sum(cost) as marge
from {{ source('shop', 'orders') }}
group by 1
