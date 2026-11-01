"""Agrégats communaux (repli si l'appariement individuel est insuffisant)
et mise en forme de la base Insee du comparateur de territoires."""
from __future__ import annotations

import pandas as pd


def agreger_communes(ventes: pd.DataFrame, dpe: pd.DataFrame) -> pd.DataFrame:
    """Par commune × année × type de bien : prix médian au m² et profil DPE."""
    v = ventes.assign(annee=ventes["date_mutation"].dt.year)
    prix = (v.groupby(["code_commune", "annee", "type_bien"])
             .agg(n_ventes=("prix", "size"), prix_m2_median=("prix_m2", "median"),
                  surface_mediane=("surface", "median"))
             .reset_index())
    d = dpe.assign(annee=dpe["date_etablissement_dpe"].dt.year,
                   code_commune=dpe["code_insee_ban"],
                   type_bien=dpe["type_batiment"],
                   passoire=dpe["etiquette_dpe"].isin(["F", "G"]),
                   performant=dpe["etiquette_dpe"].isin(["A", "B"]))
    prof = (d.groupby(["code_commune", "annee", "type_bien"])
             .agg(n_dpe=("numero_dpe", "size"), part_FG=("passoire", "mean"),
                  part_AB=("performant", "mean"),
                  conso_ep_mediane=("conso_5_usages_par_m2_ep", "median"))
             .reset_index())
    return prix.merge(prof, on=["code_commune", "annee", "type_bien"], how="left")


def comparateur_large(chemin, objets_geo=("COM", "ARM")) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Base Insee (format long) -> une ligne par commune, une colonne par indicateur.

    Garde, pour chaque indicateur, l'année la plus récente. Renvoie aussi le
    dictionnaire code -> libellé. Vérifier les modalités de GEO_OBJECT au
    premier passage (`df.GEO_OBJECT.unique()`) et ajuster `objets_geo` si besoin.
    """
    df = pd.read_parquet(chemin)
    df = df[df["GEO_OBJECT"].isin(objets_geo)]
    df = df.sort_values("TIME_PERIOD").drop_duplicates(["GEO", "TAB_MEASURE"], keep="last")
    large = df.pivot(index="GEO", columns="TAB_MEASURE", values="OBS_VALUE").reset_index()
    large = large.rename(columns={"GEO": "code_commune"})
    dico = (df[["TAB_MEASURE", "TAB_MEASURE_LABEL", "TIME_PERIOD"]]
              .drop_duplicates("TAB_MEASURE").sort_values("TAB_MEASURE"))
    return large, dico
