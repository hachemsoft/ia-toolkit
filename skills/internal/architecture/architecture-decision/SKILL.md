---
name: architecture-decision
description: "Instruire et documenter une décision d’architecture (ADR) : options, critères, conséquences, réversibilité. Déclencheurs : quelle architecture choisir, faut-il découper ce service, choisir une base ou un framework, écrire un ADR, revoir ce design, cette décision est-elle réversible."
---

# architecture-decision

Partir du problème, pas de la solution : contraintes, qualités attendues (latence, volume, disponibilité, coût, sécurité, capacité de l’équipe à maintenir) et ce qui est hors périmètre. Lire les ADR existants du repo et l’architecture en place avant de proposer quoi que ce soit ; une décision qui en contredit une autre le dit et propose de la remplacer explicitement. Si le besoin est flou, l’éclaircir d’abord avec le skill grilling. Poser au moins deux options réelles, dont « ne rien changer » quand elle tient, et les comparer sur les mêmes critères, avec les preuves disponibles (mesures, documentation, prototype jetable avec le skill prototype). Pour chaque option : conséquences, coût de sortie, ce qui devient plus difficile. Classer la décision : réversible à faible coût (trancher vite) ou difficile à défaire (prendre le temps, faire relire). Rédiger l’ADR dans le dossier et le format du repo (sinon `docs/adr/NNNN-titre.md` : contexte, décision, options écartées, conséquences, statut) et demander confirmation avant d’écrire. Garder le vocabulaire du domaine avec le skill domain-modeling.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « Il n’y a qu’une option sérieuse » | Alors la comparer à « ne rien changer » prend cinq lignes ; sinon on ne sait pas ce qu’on achète. |
| « On documentera la décision plus tard » | Plus tard, les raisons sont oubliées et il ne reste que la décision ; l’ADR court s’écrit maintenant. |
| « Tout le monde utilise cette techno » | La question est ce qu’elle coûte ici, avec cette équipe et ces contraintes. |
| « C’est réversible de toute façon » | Dire ce que coûterait le retour : données migrées, contrats publiés, compétences à acquérir. |
