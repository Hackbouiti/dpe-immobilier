"""Chargement des ventes pour l'analyse.

Tout le monde passe par ces fonctions, pour travailler sur le même échantillon.
"""
from __future__ import annotations

import pandas as pd

from . import config as C

ETIQUETTES = list("ABCDEFG")

COLONNES_ANALYSE = [
    "id_mutation", "date_mutation", "prix", "type_bien", "surface", "nb_pieces", "prix_m2",
    "code_commune", "code_departement", "longitude", "latitude",
    "apparie", "vente_rapprochee", "methode_appariement", "ambigu", "n_candidats",
    "delai_jours", "ecart_surface", "distance_m",
    "etiquette_dpe", "etiquette_ges", "conso_5_usages_par_m2_ep", "version_dpe",
    "periode_construction", "annee_construction", "zone_climatique",
]


def charger_ventes(departement: str | None = None, colonnes: list[str] | None = None) -> pd.DataFrame:
    """Toutes les ventes, appariées ou non.

    `departement` : code d'un département ("44") pour un essai rapide, None pour la France.
    Ajoute l'année et le trimestre de vente, et met l'étiquette dans l'ordre A à G.
    """
    if departement:
        fichier = C.PROCESSED / "ventes" / f"{departement}.parquet"
    else:
        fichier = C.PROCESSED / "ventes_france.parquet"
    ventes = pd.read_parquet(fichier, columns=colonnes or COLONNES_ANALYSE)
    return preparer(ventes)


def preparer(ventes: pd.DataFrame) -> pd.DataFrame:
    v = ventes.copy()
    if "date_mutation" in v:
        v["annee"] = v["date_mutation"].dt.year
        v["trimestre"] = v["date_mutation"].dt.to_period("Q").astype(str)
    if "etiquette_dpe" in v:
        v["etiquette_dpe"] = pd.Categorical(v["etiquette_dpe"], categories=ETIQUETTES, ordered=True)
    for col in ("vente_rapprochee", "ambigu"):
        if col in v:
            v[col] = v[col].astype("boolean").fillna(False).astype(bool)
    # Colonnes texte très répétées : en catégories, la table nationale tient
    # beaucoup moins de place en mémoire.
    for col in ("type_bien", "code_departement", "code_commune", "methode_appariement",
                "etiquette_ges", "version_dpe", "periode_construction", "zone_climatique", "trimestre"):
        if col in v:
            v[col] = v[col].astype("category")
    return v


def echantillon_analyse(ventes: pd.DataFrame) -> pd.DataFrame:
    """Ventes appariées, sans les ventes rapprochées d'un même logement.

    Les ventes rapprochées (moins de 30 jours d'écart) sont le plus souvent des
    cessions de parts : leur prix ne correspond pas au logement entier.
    """
    return ventes[ventes["apparie"] & ~ventes["vente_rapprochee"]].copy()


def appariement_strict(echantillon: pd.DataFrame) -> pd.DataFrame:
    """Sous-échantillon de vérification : sans les ventes ambiguës et sans
    les ventes appariées par la distance."""
    garde = ~echantillon["ambigu"] & (echantillon["methode_appariement"] == "adresse")
    return echantillon[garde].copy()
