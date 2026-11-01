"""Appariement vente DVF ↔ DPE ADEME.

Deux sources de candidats, puis une attribution un-pour-un :

1. **Adresse** : même adresse normalisée (commune + numéro + voie) et même type de bien.
2. **Proximité spatiale**, pour les ventes sans aucun candidat à l'adresse
   (lieux-dits, voies nommées différemment dans DVF et la BAN) : DPE de même
   type dans la même commune, à moins de RAYON_SPATIAL_M du centroïde de la
   parcelle DVF.

Filtres communs : DPE établi avant la vente (au plus DELAI_MAX_DPE_JOURS avant),
surfaces compatibles (TOLERANCE_SURFACE).

Chaque candidat reçoit un score (plus petit = meilleur) combinant écart de
surface, ancienneté du DPE et distance. Un DPE décrit un seul logement : il ne
peut pas être attribué à deux logements différents (par tours successifs de
« meilleurs choix »). Sans cette règle, deux appartements de surface proche dans
le même immeuble recevaient le même DPE. Plusieurs ventes du même logement
(même parcelle et même lot, voir clean.identifiant_logement) peuvent en revanche
partager un DPE, par exemple lors d'une revente rapide.

Les ventes non appariées sont conservées (`apparie` = False) pour étudier la
sélection de l'échantillon apparié.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C

COLS_DPE_SORTIE = [
    "numero_dpe", "date_etablissement_dpe", "version_dpe", "etiquette_dpe", "etiquette_ges",
    "conso_5_usages_par_m2_ep", "emission_ges_5_usages_par_m2", "surface_habitable_logement",
    "periode_construction", "annee_construction", "numero_etage_appartement", "zone_climatique",
    "type_energie_principale_chauffage", "identifiant_ban", "id_rnb", "dpe_genere_immeuble",
]


# ---------------------------------------------------------------------------
# Projection Lambert-93 (EPSG:2154), formules IGN, sans dépendance externe
# ---------------------------------------------------------------------------
_E = 0.0818191910428158        # excentricité GRS80
_N = 0.7256077650532670
_CC = 11754255.426096
_XS, _YS = 700000.0, 12655612.049876
_LON0 = np.radians(3.0)


def lambert93(lon, lat):
    """(longitude, latitude) WGS84 en degrés -> (x, y) Lambert-93 en mètres."""
    phi = np.radians(np.asarray(lat, dtype=float))
    lam = np.radians(np.asarray(lon, dtype=float))
    es = _E * np.sin(phi)
    lat_iso = np.log(np.tan(np.pi / 4 + phi / 2) * ((1 - es) / (1 + es)) ** (_E / 2))
    r = _CC * np.exp(-_N * lat_iso)
    gamma = _N * (lam - _LON0)
    return _XS + r * np.sin(gamma), _YS - r * np.cos(gamma)


# ---------------------------------------------------------------------------
# Génération des candidats
# ---------------------------------------------------------------------------
def _candidats_adresse(v: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    gauche = v[v["cle_adresse"].notna()][["id_vente", "cle_adresse", "type_bien"]]
    droite = d[d["cle_adresse"].notna()][["cle_adresse", "type_bien", "id_dpe"]]
    c = gauche.merge(droite, on=["cle_adresse", "type_bien"])[["id_vente", "id_dpe"]]
    return c.assign(methode="adresse", distance_m=np.nan)


def _candidats_spatiaux(v: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Voisinage par grille : chaque DPE est rangé dans une case de côté
    max(rayons) ; chaque vente est comparée aux DPE des 9 cases voisines."""
    rayons = C.RAYON_SPATIAL_M
    pas = float(max(rayons.values()))
    v = v.dropna(subset=["x_l93", "y_l93"])
    d = d.dropna(subset=["x_l93", "y_l93"])
    if v.empty or d.empty:
        return pd.DataFrame(columns=["id_vente", "id_dpe", "methode", "distance_m"])

    d = d.assign(gx=(d["x_l93"] // pas).astype(np.int64), gy=(d["y_l93"] // pas).astype(np.int64))
    gx0 = (v["x_l93"] // pas).astype(np.int64)
    gy0 = (v["y_l93"] // pas).astype(np.int64)
    voisins = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            voisins.append(pd.DataFrame({
                "id_vente": v["id_vente"].values, "type_bien": v["type_bien"].values,
                "code_commune": v["code_commune"].values,
                "xv": v["x_l93"].values, "yv": v["y_l93"].values,
                "gx": (gx0 + dx).values, "gy": (gy0 + dy).values}))
    vv = pd.concat(voisins, ignore_index=True)
    c = vv.merge(d[["id_dpe", "type_bien", "code_insee_ban", "x_l93", "y_l93", "gx", "gy"]],
                 left_on=["gx", "gy", "type_bien", "code_commune"],
                 right_on=["gx", "gy", "type_bien", "code_insee_ban"])
    c["distance_m"] = np.hypot(c["xv"] - c["x_l93"], c["yv"] - c["y_l93"])
    c = c[c["distance_m"] <= c["type_bien"].map(rayons)]
    return c[["id_vente", "id_dpe", "distance_m"]].assign(methode="spatial")


# ---------------------------------------------------------------------------
# Attribution un-pour-un
# ---------------------------------------------------------------------------
def attribution_unique(cand: pd.DataFrame) -> pd.DataFrame:
    """Chaque vente reçoit au plus un DPE, et chaque DPE décrit au plus un logement.

    Un DPE décrit un seul logement : il ne peut pas être attribué à deux
    logements différents. Plusieurs ventes d'un même logement (`id_logement`),
    par exemple une revente rapide, peuvent en revanche partager le même DPE.

    Tours successifs : chaque vente désigne son meilleur DPE encore disponible ;
    pour chaque DPE désigné, le logement de la vente au meilleur score l'obtient,
    pour toutes ses ventes qui l'ont désigné. Le DPE est ensuite retiré des
    candidats des autres logements. Chaque tour attribue au moins une vente,
    donc la boucle termine.
    """
    if "id_logement" not in cand.columns:
        cand = cand.assign(id_logement=cand["id_vente"].astype(str))
    cand = cand.sort_values(["score", "id_vente", "id_dpe"])
    retenus = []
    while len(cand):
        meilleurs = cand.drop_duplicates("id_vente")
        gagnant = meilleurs.drop_duplicates("id_dpe")[["id_dpe", "id_logement"]]
        choix = meilleurs.merge(gagnant, on=["id_dpe", "id_logement"])
        retenus.append(choix)
        proprio = gagnant.set_index("id_dpe")["id_logement"]
        cand = cand[~cand["id_vente"].isin(choix["id_vente"])]
        p = cand["id_dpe"].map(proprio)
        cand = cand[p.isna() | (p == cand["id_logement"])]
    return pd.concat(retenus, ignore_index=True) if retenus else cand


# ---------------------------------------------------------------------------
# Appariement
# ---------------------------------------------------------------------------
def apparier(ventes: pd.DataFrame, dpe: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {"n_ventes": len(ventes), "n_dpe": len(dpe)}
    if ventes.empty or dpe.empty:
        stats.update(n_apparie=0, taux_appariement=0.0)
        return ventes.assign(apparie=False), stats

    v = ventes.reset_index(drop=True).copy()
    v["id_vente"] = np.arange(len(v))
    v["x_l93"], v["y_l93"] = lambert93(v["longitude"], v["latitude"])

    d = dpe.rename(columns={"type_batiment": "type_bien"}).reset_index(drop=True).copy()
    d["id_dpe"] = np.arange(len(d))
    d["x_l93"] = pd.to_numeric(d["coordonnee_cartographique_x_ban"], errors="coerce")
    d["y_l93"] = pd.to_numeric(d["coordonnee_cartographique_y_ban"], errors="coerce")

    c_adr = _candidats_adresse(v, d)
    sans_adresse = v[~v["id_vente"].isin(c_adr["id_vente"])]
    c_spa = _candidats_spatiaux(sans_adresse, d)
    cand = pd.concat([c_adr, c_spa], ignore_index=True)
    stats["n_ventes_candidat_adresse"] = int(c_adr["id_vente"].nunique())
    stats["n_ventes_candidat_spatial"] = int(c_spa["id_vente"].nunique())

    if "id_logement" not in v.columns:
        v["id_logement"] = "vente|" + v["id_vente"].astype(str)
    cand = (cand.merge(v[["id_vente", "id_logement", "type_bien", "date_mutation", "surface"]],
                       on="id_vente")
                .merge(d[["id_dpe", "date_etablissement_dpe", "surface_habitable_logement",
                          "etiquette_dpe"]], on="id_dpe"))
    cand["delai_jours"] = (cand["date_mutation"] - cand["date_etablissement_dpe"]).dt.days
    cand = cand[cand["delai_jours"].between(-C.DELAI_APRES_VENTE_JOURS, C.DELAI_MAX_DPE_JOURS)]
    surf_dpe = pd.to_numeric(cand["surface_habitable_logement"], errors="coerce")
    cand["ecart_surface"] = (cand["surface"] - surf_dpe).abs() / surf_dpe
    tol = cand["type_bien"].map(C.TOLERANCE_SURFACE)
    cand = cand[cand["ecart_surface"] <= tol].copy()

    # Score : chaque terme vaut 1 à la limite de tolérance.
    rayon = cand["type_bien"].map(C.RAYON_SPATIAL_M)
    cand["score"] = (cand["ecart_surface"] / tol
                     + C.POIDS_DELAI * cand["delai_jours"].clip(lower=0) / C.DELAI_MAX_DPE_JOURS
                     + cand["distance_m"].fillna(0) / rayon)

    choix = attribution_unique(cand)

    # Fiabilité : un autre candidat de score proche porte-t-il une étiquette différente ?
    n_cand = cand.groupby("id_vente").size().rename("n_candidats")
    alt = cand.merge(choix[["id_vente", "id_dpe", "score", "etiquette_dpe"]],
                     on="id_vente", suffixes=("", "_choisi"))
    alt = alt[(alt["id_dpe"] != alt["id_dpe_choisi"])
              & (alt["etiquette_dpe"] != alt["etiquette_dpe_choisi"])
              & (alt["score"] - alt["score_choisi"] <= C.MARGE_AMBIGUITE)]
    choix = choix.join(n_cand, on="id_vente")
    choix["ambigu"] = choix["id_vente"].isin(alt["id_vente"])
    choix = choix.rename(columns={"methode": "methode_appariement"})

    garder = ["id_vente", "id_dpe", "methode_appariement", "distance_m", "delai_jours",
              "ecart_surface", "score", "n_candidats", "ambigu"]
    out = (v.merge(choix[garder], on="id_vente", how="left")
            .merge(d[["id_dpe"] + COLS_DPE_SORTIE], on="id_dpe", how="left"))
    out["apparie"] = out["numero_dpe"].notna()
    out["ambigu"] = out["ambigu"].astype("boolean")

    n_app = int(out["apparie"].sum())
    stats.update(
        n_apparie=n_app,
        taux_appariement=round(n_app / len(out), 4) if len(out) else 0.0,
        n_apparie_adresse=int((out["methode_appariement"] == "adresse").sum()),
        n_apparie_spatial=int((out["methode_appariement"] == "spatial").sum()),
        n_ambigu=int(out["ambigu"].fillna(False).sum()),
        n_ventes_dpe_partage=int(out.loc[out["apparie"], "numero_dpe"].duplicated(keep=False).sum()),
    )
    for t in ("maison", "appartement"):
        sous = out[out["type_bien"] == t]
        stats[f"taux_{t}"] = round(sous["apparie"].mean(), 4) if len(sous) else None
    return out.drop(columns=["id_vente", "id_dpe", "x_l93", "y_l93"]), stats
