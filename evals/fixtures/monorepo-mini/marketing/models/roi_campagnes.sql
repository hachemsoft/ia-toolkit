-- grain : une campagne par mois
select c.campagne, c.mois, m.marge / nullif(c.depense, 0) as roi
from {{ source('ads', 'campagnes') }} c
join {{ ref('marge_mensuelle') }} m using (mois)
