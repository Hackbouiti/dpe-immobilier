"""Chargement des ventes pour l'analyse.

Tout le monde passe par ces fonctions, pour travailler sur le même échantillon.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from . import config as C

ETIQUETTES = list("ABCDEFG")

# Copie des fichiers de data/processed sur le stockage du SSP Cloud (dossier
# public `diffusion`), pour ne pas avoir à relancer la chaîne de traitement.
URL_SSP = "https://minio.lab.sspcloud.fr/mbouitibanza/diffusion/dpe-immobilier"

COLONNES_ANALYSE = [
    "id_mutation", "date_mutation", "prix", "type_bien", "surface", "nb_pieces", "prix_m2",
    "code_commune", "code_departement", "longitude", "latitude",
    "apparie", "vente_rapprochee", "methode_appariement", "ambigu", "n_candidats",
    "delai_jours", "ecart_surface", "distance_m",
    "etiquette_dpe", "etiquette_ges", "conso_5_usages_par_m2_ep", "version_dpe",
    "periode_construction", "annee_construction", "zone_climatique",
]


def fichier(nom: str) -> Path:
    """Chemin d'un fichier de data/processed.

    S'il n'existe pas en local, il est d'abord téléchargé depuis le SSP Cloud
    (une seule fois : les fois suivantes, la copie locale est lue).
    """
    chemin = C.PROCESSED / nom
    if chemin.exists():
        return chemin
    chemin.parent.mkdir(parents=True, exist_ok=True)
    partiel = chemin.with_name(chemin.name + ".part")
    print(f"Téléchargement de {nom} depuis le SSP Cloud...")
    with requests.get(f"{URL_SSP}/{nom}", stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(partiel, "wb") as f:
            for bloc in r.iter_content(chunk_size=1 << 20):
                f.write(bloc)
    partiel.replace(chemin)
    return chemin


def charger_ventes(departement: str | None = None, colonnes: list[str] | None = None) -> pd.DataFrame:
    """Toutes les ventes, appariées ou non.

    `departement` : code d'un département ("44") pour un essai rapide, None pour la France.
    Ajoute l'année et le trimestre de vente, et met l'étiquette dans l'ordre A à G.
    """
    colonnes = colonnes or COLONNES_ANALYSE
    local = C.PROCESSED / "ventes" / f"{departement}.parquet"
    if departement and local.exists():
        ventes = pd.read_parquet(local, columns=colonnes)
    elif departement:
        ventes = pd.read_parquet(fichier("ventes_france.parquet"), columns=colonnes,
                                 filters=[("code_departement", "==", departement)])
    else:
        ventes = pd.read_parquet(fichier("ventes_france.parquet"), columns=colonnes)
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
