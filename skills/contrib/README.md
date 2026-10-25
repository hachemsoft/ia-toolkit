# Skills contribués

Ici vont les skills que les personnes de l’organisation proposent au kit, un dossier par skill : `skills/contrib/<nom>/SKILL.md`. Ce qui est sous `skills/internal/` est livré et maintenu par les mainteneurs du kit ; ce qui est ici est maintenu par la personne nommée dans le catalogue.

Règles, vérifiées par les tests :

- une entrée dans `skills/catalog.json` avec `"origin": "contrib"`, `"owner": "<prénom.nom ou équipe>"`, et `"tier": "optional"` : un skill contribué ne s’installe jamais par défaut, chacun l’active d’une ligne (`extra_skills` dans `~/.ai-kit/overrides.json`) ;
- un nom qui n’existe pas déjà dans le kit ; pour remplacer un skill livré, voir [docs/extending.md](../../docs/extending.md) ;
- un cas d’évaluation dans `evals/cases/` qui montre le skill en action, ou une ligne « Déclencheurs » dans la description qui dit quand il s’active.

Promotion : quand la revue d’usage montre qu’un skill contribué sert largement, il passe sous `skills/internal/` avec `"origin": "internal"`, et entre dans un profil. Retrait : un skill contribué sans propriétaire joignable est retiré à la revue d’usage suivante.
