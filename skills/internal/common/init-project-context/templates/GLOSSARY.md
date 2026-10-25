# <Nom du projet>

<Une ou deux phrases : le périmètre métier de ce repo et pourquoi il existe.>

## Language

**Grain**:
Ce que représente une ligne d’une table ou d’un résultat, énoncé avant toute jointure ou agrégation.
_Avoid_: granularité, niveau de détail

**Clé**:
Colonne ou combinaison de colonnes qui identifie une ligne au grain déclaré.
_Avoid_: identifiant, id technique

**Source**:
Donnée telle que livrée par le système d’origine, sans transformation.
_Avoid_: raw, brut, landing

**Staging**:
Première couche de transformation : renommage, typage, nettoyage léger, grain inchangé.
_Avoid_: stg, préparation

**Intermédiaire**:
Transformation métier réutilisée par plusieurs marts.
_Avoid_: int, couche technique

**Mart**:
Table finale destinée à un usage : reporting, exposition, modèle. Grain documenté.
_Avoid_: datamart, table finale, vue métier

**Dimension**:
Attributs descriptifs d’une entité, reliés aux faits par une clé.
_Avoid_: référentiel, table de référence

**Fait**:
Mesures au grain d’un événement, reliées aux dimensions.
_Avoid_: table de faits, transactions

**Partition**:
Découpage physique d’une table par une colonne, filtrée pour réduire les octets lus.
_Avoid_: shard, segment

**Clustering**:
Tri physique par colonnes au sein d’une table, utile aux filtres et jointures fréquents.
_Avoid_: index, tri

**Incrémental**:
Traitement des seules nouvelles données selon une clé et une règle de fraîcheur.
_Avoid_: delta, append

**Rejeu**:
Reconstruction d’une période de données ; son comportement se définit avant de choisir l’incrémental.
_Avoid_: backfill, full refresh (ce dernier désigne la commande, pas l’intention)
