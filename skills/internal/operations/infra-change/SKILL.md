---
name: infra-change
description: "Préparer ou revoir un changement d’infrastructure ou de livraison : Terraform, Kubernetes, Helm, pipeline CI/CD, Dockerfile, configuration cloud. Déclencheurs : modifier le pipeline, ajouter une ressource, changer un déploiement, ouvrir un port, monter de version une image, revoir ce plan Terraform."
---

# infra-change

Lire `AGENTS.md`, la structure des environnements (dossiers, workspaces, overlays, valeurs Helm) et la façon dont le repo déploie : qui applique, depuis où, avec quel compte. Travailler sur l’environnement de développement ou de recette que le repo désigne ; jamais la production sans instruction explicite. Avant tout changement, dire le rayon d’impact : ressources créées, modifiées, détruites ou recréées, services touchés, coupure possible. Produire la preuve en lecture seule que le repo prévoit (`terraform plan`, `helm diff`, `kubectl diff`, `--dry-run`, validation du pipeline) et la lire ligne à ligne ; une destruction ou un remplacement non voulu arrête le travail. Ne jamais lancer `apply`, `destroy`, un déploiement ou une commande qui modifie un environnement partagé : proposer la commande et la laisser à la personne ou au pipeline. Vérifier le moindre privilège (droits IAM, ports, exposition publique), l’absence de secret en clair (variables, fichiers, journaux du pipeline) et l’épinglage des versions (images, modules, providers, actions). Écrire le retour arrière avant la livraison. Décrire la livraison avec le skill mr, plan ou diff à l’appui.

## Excuses entendues et réponses
| Excuse | Réponse |
| --- | --- |
| « C’est juste une variable, pas besoin de plan » | Une variable peut recréer une ressource ; le plan le dit en dix secondes. |
| « J’applique en dev, ça ne casse rien » | Un environnement partagé reste partagé ; proposer la commande, ne pas la lancer. |
| « Je mets `latest`, ce sera toujours à jour » | Une version non épinglée change sans revue ; épingler et monter de version par MR. |
| « Le retour arrière, on verra si ça casse » | Sans retour arrière écrit, l’incident dure le temps de l’inventer. |
