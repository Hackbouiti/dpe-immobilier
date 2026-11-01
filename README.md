# Immobilier et performance énergétique en France

Projet du cours Python pour la data science (ENSAE Paris), réalisé par Marc Olivier Bouiti Banza, Karlane Vasthi Foudjin Sipeuwo et Aniela Nomwendé Tania Zoungrana.

Nous cherchons à savoir si les logements mieux classés au diagnostic de performance énergétique (DPE) se vendent plus cher que des logements comparables, et si cet écart a changé entre 2022 et 2025, période où l'interdiction de louer les logements classés G est entrée en vigueur.

Le dépôt contient la chaîne de traitement qui relie les ventes immobilières aux diagnostics, puis l'analyse. Les choix de méthode sont expliqués dans `docs/note_de_projet.pdf`.

## Données

| Source | Producteur | Accès |
|---|---|---|
| [Demandes de valeurs foncières géolocalisées](https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees) | DGFiP et Etalab | un fichier CSV par année et par département |
| [DPE des logements existants depuis juillet 2021](https://data.ademe.fr/datasets/dpe03existant) | ADEME | API, interrogée département par département |
| [Base du comparateur de territoires](https://www.insee.fr/fr/statistiques/2521169) | Insee | un fichier Parquet national |

Le champ couvre les ventes de 2022 à 2025 dans 93 départements de France métropolitaine. L'Alsace et la Moselle n'en font pas partie, car elles ne figurent pas dans DVF. Seules les ventes d'un seul logement (maison ou appartement) sont gardées, éventuellement avec une cave ou un garage.

## Installation

```bash
python -m pip install -r requirements.txt
```

## Lancer la chaîne de traitement

Les commandes se lancent depuis la racine du dépôt.

```bash
# Quelques départements, pour un premier essai
python -m src.pipeline --deps 75 33 48

# Tous les départements, avec les données de l'Insee
python -m src.pipeline --insee

# Refaire l'appariement à partir des fichiers déjà téléchargés
python -m src.pipeline --sans-telechargement
```

Un fichier déjà téléchargé n'est pas téléchargé une seconde fois, et un département en erreur ne bloque pas les autres. Le téléchargement des DPE par l'API est l'étape la plus longue : compter plusieurs heures pour la France entière.

Les tests se lancent avec `python -m pytest`.

## Fichiers produits

| Fichier | Contenu |
|---|---|
| `data/processed/ventes/{dep}.parquet` | une ligne par vente ; les colonnes du DPE sont remplies quand la vente est appariée (`apparie`) |
| `data/processed/ventes_france.parquet` | les mêmes ventes pour la France entière |
| `data/processed/communes_france.parquet` | par commune, année et type de bien : prix médian au m², part des étiquettes F-G et A-B |
| `data/processed/insee_communes.parquet` | indicateurs de l'Insee par commune |
| `reports/journal_appariement.csv` | nombre de ventes, de DPE et taux d'appariement par département |
| `reports/insee_dictionnaire.csv` | libellés des indicateurs de l'Insee |

Le dossier `data/` n'est pas versionné. Sur l'ensemble du champ, 1 571 690 ventes sur 3 202 384 sont appariées à un DPE (49,1 %). Les ventes non appariées restent dans les fichiers, pour pouvoir les comparer aux ventes appariées.

## Appariement

Les deux bases n'ont pas d'identifiant commun. Une vente reçoit un DPE selon les règles suivantes (`src/match.py`, seuils dans `src/config.py`) :

1. même adresse et même type de logement ;
2. à défaut, un DPE de même type à moins de 20 m (appartement) ou 60 m (maison) du centre de la parcelle de la vente ;
3. une surface proche : écart d'au plus 10 % pour un appartement et 20 % pour une maison ;
4. un DPE établi avant la vente, depuis moins de trois ans ; à surface égale, le plus récent ;
5. un DPE ne peut pas être attribué à deux logements différents, mais plusieurs ventes du même logement peuvent partager le même DPE ;
6. une vente est signalée comme ambiguë (`ambigu`) quand un autre DPE presque aussi proche porte une étiquette différente.

La colonne `vente_rapprochee` signale les ventes d'un même logement à moins de 30 jours d'écart. Il s'agit le plus souvent de cessions de parts, dont le prix ne correspond pas au logement entier.

## Limites

Les bases n'indiquent pas le numéro de l'appartement : dans un immeuble, le DPE retenu peut être celui d'un voisin. Les DPE réalisés avant juillet 2021 ne sont pas dans la base de l'ADEME, ce qui explique le taux d'appariement plus faible en 2022. Les seuils des étiquettes ont changé le 1er juillet 2024 pour les logements de moins de 40 m². La note de projet détaille ces points.

## Organisation du dépôt

```
data/        données (non versionnées)
docs/        notes de projet et schéma de la chaîne de traitement
notebooks/   analyse
reports/     journal d'appariement
src/         collecte, nettoyage, appariement
tests/       tests sur des données fictives
```
