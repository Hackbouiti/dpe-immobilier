"""Paramètres du projet : périmètre, chemins, sources."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_DVF = DATA / "raw" / "dvf"
RAW_DPE = DATA / "raw" / "dpe"
RAW_INSEE = DATA / "raw" / "insee"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"

# Périmètre : France métropolitaine hors Alsace-Moselle.
# 57, 67, 68 : absents de DVF (livre foncier). DROM exclus : méthode DPE 2021
# pensée pour la métropole, Mayotte absente de DVF.
EXCLUS = {"57", "67", "68"}
DEPARTEMENTS = [
    d for d in [f"{i:02d}" for i in range(1, 96) if i != 20] + ["2A", "2B"]
    if d not in EXCLUS
]

# Ventes retenues : années civiles complètes postérieures à la réforme du DPE (juillet 2021).
ANNEES_DVF = [2022, 2023, 2024, 2025]

URL_DVF = "https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{dep}.csv.gz"
URL_DPE_API = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"
URL_INSEE_COMPARATEUR = "https://www.insee.fr/fr/statistiques/fichier/2521169/comparateur.parquet"

COLONNES_DPE = [
    "numero_dpe", "numero_dpe_remplace", "date_etablissement_dpe", "version_dpe",
    "methode_application_dpe", "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ep", "emission_ges_5_usages_par_m2",
    "type_batiment", "surface_habitable_logement", "periode_construction",
    "annee_construction", "numero_etage_appartement", "zone_climatique",
    "type_energie_principale_chauffage",
    "identifiant_ban", "numero_voie_ban", "nom_rue_ban", "code_postal_ban",
    "code_insee_ban", "code_departement_ban", "score_ban", "id_rnb",
    "coordonnee_cartographique_x_ban", "coordonnee_cartographique_y_ban",
]

# Règles d'appariement
# Écart relatif maximal entre surfaces DVF et DPE. Plus large pour les maisons :
# la surface DVF est la surface réelle bâtie, pas la surface habitable.
TOLERANCE_SURFACE = {"appartement": 0.10, "maison": 0.20}
DELAI_MAX_DPE_JOURS = 3 * 365 # DPE établi au plus 3 ans avant la vente
DELAI_APRES_VENTE_JOURS = 0   # DPE obligatoire avant la vente
SCORE_BAN_MIN = 0.5           # géocodage DPE trop incertain en dessous

# Repli spatial (ventes sans DPE à la même adresse) : distance maximale entre le
# centroïde de la parcelle DVF et le point adresse BAN du DPE. Plus large pour les
# maisons, dont les parcelles rurales sont grandes ; étroit pour les appartements
# pour ne pas attraper l'immeuble voisin.
RAYON_SPATIAL_M = {"appartement": 20.0, "maison": 60.0}

# Score d'un candidat = écart de surface / tolérance
#                     + POIDS_DELAI × ancienneté du DPE / délai max
#                     + distance / rayon (repli spatial seulement)
POIDS_DELAI = 0.25
# Vente signalée « ambiguë » si un autre DPE d'étiquette différente a un score
# à moins de MARGE_AMBIGUITE du DPE retenu.
MARGE_AMBIGUITE = 0.10

# Deux ventes du même logement à moins de ce délai sont signalées
# (cessions de droits partiels plutôt que reventes) : colonne `vente_rapprochee`.
ECART_MIN_REVENTE_JOURS = 30

# Filtres de qualité sur les ventes
SURFACE_MIN, SURFACE_MAX = 9, 400
PRIX_MIN = 10_000
QUANTILES_PRIX_M2 = (0.01, 0.99)  # écrêtage par département et type de bien
