"""Nettoyage des ventes DVF et des DPE, et normalisation des adresses."""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from . import config as C

# ---------------------------------------------------------------------------
# Adresses
# ---------------------------------------------------------------------------
# DVF abrège le type de voie ("AV", "BD"), la BAN l'écrit en entier ("Avenue").
TYPES_VOIE = {
    "AV": "AVENUE", "AVE": "AVENUE", "BD": "BOULEVARD", "BLD": "BOULEVARD",
    "BOUL": "BOULEVARD", "CHE": "CHEMIN", "CHEM": "CHEMIN", "CH": "CHEMIN",
    "IMP": "IMPASSE", "ALL": "ALLEE", "PL": "PLACE", "RTE": "ROUTE",
    "SQ": "SQUARE", "CRS": "COURS", "QU": "QUAI", "QUA": "QUAI", "PAS": "PASSAGE",
    "LOT": "LOTISSEMENT", "RES": "RESIDENCE", "HAM": "HAMEAU", "LD": "LIEU DIT",
    "FG": "FAUBOURG", "FBG": "FAUBOURG", "SEN": "SENTIER", "VC": "VOIE COMMUNALE",
    "PROM": "PROMENADE", "RPT": "ROND POINT", "CITE": "CITE", "CTR": "CENTRE",
    "ESP": "ESPLANADE", "MTE": "MONTEE", "PRV": "PARVIS", "TRA": "TRAVERSE",
    "VLA": "VILLA", "CAR": "CARREFOUR", "R": "RUE",
}
MOTS_VIDES = {"DE", "DU", "DES", "LA", "LE", "LES", "L", "D", "ET", "A", "AU", "AUX", "EN"}
ABREV_MOTS = {"ST": "SAINT", "STE": "SAINTE", "GAL": "GENERAL", "MAL": "MARECHAL",
              "PDT": "PRESIDENT", "DR": "DOCTEUR", "PR": "PROFESSEUR", "CDT": "COMMANDANT"}
SUFFIXES = {"BIS": "B", "B": "B", "TER": "T", "T": "T", "QUATER": "Q", "Q": "Q",
            "QUINQUIES": "C", "C": "C"}


def _sans_accents(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def normaliser_voie(nom) -> str:
    if not isinstance(nom, str) or not nom.strip():
        return ""
    s = _sans_accents(nom.upper())
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    mots = s.split()
    if mots and mots[0] in TYPES_VOIE:
        mots = TYPES_VOIE[mots[0]].split() + mots[1:]
    mots = [ABREV_MOTS.get(m, m) for m in mots]
    return " ".join(m for m in mots if m not in MOTS_VIDES)


def normaliser_numero(numero, suffixe=None) -> str:
    """'12bis' ou (12, 'B') -> '12B'. Chaîne vide si pas de numéro."""
    if numero is None or (isinstance(numero, float) and np.isnan(numero)):
        return ""
    s = str(numero).upper().strip()
    s = re.sub(r"\.0$", "", s)
    m = re.match(r"^0*(\d+)\s*([A-Z]*)", s)
    if not m:
        return ""
    num, suf = m.group(1), m.group(2)
    if not suf and isinstance(suffixe, str):
        suf = suffixe.upper().strip()
    return num + SUFFIXES.get(suf, suf[:1] if suf else "")


def cle_adresse(code_commune: pd.Series, numero: pd.Series, voie: pd.Series) -> pd.Series:
    cle = code_commune.astype(str).str.zfill(5) + "|" + numero + "|" + voie
    return cle.where((numero != "") & (voie != ""))


# ---------------------------------------------------------------------------
# DVF
# ---------------------------------------------------------------------------
DTYPES_DVF = {"code_commune": str, "code_departement": str, "id_parcelle": str,
              "adresse_suffixe": str, "adresse_nom_voie": str, "id_mutation": str,
              "lot1_numero": str, "lot_1_numero": str, "code_postal": str}

COLONNES_DVF_REQUISES = [
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "adresse_numero",
    "adresse_suffixe", "adresse_nom_voie", "code_commune", "code_departement", "id_parcelle",
    "code_type_local", "surface_reelle_bati", "nombre_pieces_principales",
    "code_nature_culture", "surface_terrain", "longitude", "latitude",
    *[f"lot_{i}_{c}" for i in range(1, 6) for c in ("numero", "surface_carrez")],
]


def harmoniser_colonnes_dvf(df: pd.DataFrame) -> pd.DataFrame:
    """Les fichiers Etalab écrivent `lot1_surface_carrez` ; la documentation, `lot_1_...`.
    On ramène tout à `lot_1_...` et on signale clairement toute colonne manquante."""
    df = df.rename(columns=lambda c: re.sub(r"^lot(\d)_", r"lot_\1_", c.strip()))
    manquantes = [c for c in COLONNES_DVF_REQUISES if c not in df.columns]
    if manquantes:
        raise KeyError(f"Colonnes DVF manquantes : {manquantes}. "
                       f"Colonnes présentes : {list(df.columns)}")
    return df


def lire_dvf(chemins) -> pd.DataFrame:
    parts = [pd.read_csv(p, dtype=DTYPES_DVF, low_memory=False) for p in chemins]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def nettoyer_dvf(brut: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par vente d'un unique logement (maison ou appartement).

    On écarte les mutations à plusieurs logements ou comprenant un local d'activité :
    leur valeur foncière est globale et ne peut pas être attribuée à un logement.
    Les dépendances (cave, garage) sont tolérées et comptées.
    """
    if brut.empty:
        return brut
    brut = harmoniser_colonnes_dvf(brut)
    d = brut[brut["nature_mutation"] == "Vente"].copy()
    d["lot_1_numero"] = d["lot_1_numero"].astype("string")
    numeriques = ["code_type_local", "valeur_fonciere", "surface_reelle_bati", "surface_terrain",
                  "nombre_pieces_principales", "longitude", "latitude",
                  *[f"lot_{i}_surface_carrez" for i in range(1, 6)]]
    for col in numeriques:
        d[col] = pd.to_numeric(d[col], errors="coerce")

    # Un même local est répété autant de fois que sa parcelle a de natures de culture.
    locaux = d[d["code_type_local"].notna()].drop_duplicates(
        ["id_mutation", "id_parcelle", "code_type_local", "surface_reelle_bati",
         "lot_1_numero", "adresse_numero", "adresse_nom_voie"])
    comptes = locaux.pivot_table(index="id_mutation", columns="code_type_local",
                                 values="id_parcelle", aggfunc="count", fill_value=0)
    comptes = comptes.reindex(columns=[1, 2, 3, 4], fill_value=0)
    comptes.columns = ["n_maison", "n_appart", "n_dependance", "n_activite"]
    comptes["n_logement"] = comptes["n_maison"] + comptes["n_appart"]
    ok = comptes[(comptes["n_logement"] == 1) & (comptes["n_activite"] == 0)]

    # Une seule valeur foncière par mutation (sinon mutation composite, écartée).
    nb_valeurs = d.groupby("id_mutation")["valeur_fonciere"].nunique()
    ids = ok.index.intersection(nb_valeurs[nb_valeurs == 1].index)

    log = locaux[locaux["id_mutation"].isin(ids) & locaux["code_type_local"].isin([1, 2])]
    carrez = log[[f"lot_{i}_surface_carrez" for i in range(1, 6)]].sum(axis=1, min_count=1)
    terrain = (d[d["id_mutation"].isin(ids)]
               .drop_duplicates(["id_mutation", "id_parcelle", "code_nature_culture", "surface_terrain"])
               .groupby("id_mutation")["surface_terrain"].sum(min_count=1))

    v = pd.DataFrame({
        "id_mutation": log["id_mutation"].values,
        "date_mutation": pd.to_datetime(log["date_mutation"]).values,
        "prix": log["valeur_fonciere"].values,
        "type_bien": np.where(log["code_type_local"].values == 1, "maison", "appartement"),
        "surface_bati": log["surface_reelle_bati"].values,
        "surface_carrez": carrez.values,
        "nb_pieces": log["nombre_pieces_principales"].values,
        "code_commune": log["code_commune"].astype(str).str.zfill(5).values,
        "code_departement": log["code_departement"].values,
        "id_parcelle": log["id_parcelle"].values,
        "lot_numero": log["lot_1_numero"].values,
        "adresse_numero": log["adresse_numero"].values,
        "adresse_suffixe": log["adresse_suffixe"].values,
        "adresse_nom_voie": log["adresse_nom_voie"].values,
        "longitude": log["longitude"].values,
        "latitude": log["latitude"].values,
    })
    v["surface_terrain"] = v["id_mutation"].map(terrain)
    v["n_dependance"] = v["id_mutation"].map(ok["n_dependance"]).fillna(0).astype(int)

    # Surface de référence : Carrez pour un appartement quand elle existe.
    v["surface"] = np.where((v["type_bien"] == "appartement") & v["surface_carrez"].gt(0),
                            v["surface_carrez"], v["surface_bati"])
    v = v[v["surface"].between(C.SURFACE_MIN, C.SURFACE_MAX) & (v["prix"] >= C.PRIX_MIN)].copy()
    v["prix_m2"] = v["prix"] / v["surface"]

    # Écrêtage des prix au m² aberrants, par département et type de bien.
    q_bas, q_haut = C.QUANTILES_PRIX_M2
    bornes = v.groupby(["code_departement", "type_bien"])["prix_m2"].quantile([q_bas, q_haut]).unstack()
    bornes.columns = ["bas", "haut"]
    v = v.join(bornes, on=["code_departement", "type_bien"])
    v = v[v["prix_m2"].between(v["bas"], v["haut"])].drop(columns=["bas", "haut"])

    v["numero_norm"] = [normaliser_numero(n, s) for n, s in zip(v["adresse_numero"], v["adresse_suffixe"])]
    v["voie_norm"] = v["adresse_nom_voie"].map(normaliser_voie)
    v["cle_adresse"] = cle_adresse(v["code_commune"], v["numero_norm"], v["voie_norm"])
    v["id_logement"] = identifiant_logement(v)
    v["vente_rapprochee"] = ventes_rapprochees(v)
    return v.reset_index(drop=True)


def ventes_rapprochees(v: pd.DataFrame, jours: int = C.ECART_MIN_REVENTE_JOURS) -> pd.Series:
    """Vrai si le même logement a une autre vente à moins de `jours` jours.

    Ces ventes très rapprochées (souvent le même jour, à des prix différents)
    correspondent en général à des cessions de droits partiels (parts
    d'indivision, nue-propriété, usufruit) plutôt qu'à des reventes : leur prix
    ne reflète pas la valeur du logement entier. Elles sont signalées pour
    pouvoir être exclues de l'analyse des prix.
    """
    connu = ~v["id_logement"].str.startswith("vente|")
    w = v.loc[connu, ["id_logement", "date_mutation"]].sort_values(["id_logement", "date_mutation"])
    meme = w["id_logement"].eq(w["id_logement"].shift())
    ecart_prec = (w["date_mutation"] - w["date_mutation"].shift()).dt.days.where(meme)
    meme_suiv = w["id_logement"].eq(w["id_logement"].shift(-1))
    ecart_suiv = (w["date_mutation"].shift(-1) - w["date_mutation"]).dt.days.where(meme_suiv)
    proche = (ecart_prec <= jours) | (ecart_suiv <= jours)
    return proche.reindex(v.index, fill_value=False)


def identifiant_logement(v: pd.DataFrame) -> pd.Series:
    """Identifiant d'un même logement d'une vente à l'autre : type + parcelle
    cadastrale + numéro de lot de copropriété.

    Un appartement sans numéro de lot ne peut pas être reconnu d'une vente à
    l'autre : il reçoit un identifiant propre à sa vente (id_mutation).
    """
    lot = v["lot_numero"].astype("string").str.strip().str.lstrip("0").fillna("")
    parcelle = v["id_parcelle"].astype("string").fillna("")
    base = v["type_bien"] + "|" + parcelle + "|" + lot
    inconnu = (parcelle == "") | ((v["type_bien"] == "appartement") & (lot == ""))
    return base.where(~inconnu, "vente|" + v["id_mutation"].astype(str))


# ---------------------------------------------------------------------------
# DPE
# ---------------------------------------------------------------------------
def nettoyer_dpe(brut: pd.DataFrame) -> pd.DataFrame:
    """Garde les DPE de logement individuel encore valides (non remplacés)."""
    if brut.empty:
        return brut
    d = brut.copy()
    d["date_etablissement_dpe"] = pd.to_datetime(d["date_etablissement_dpe"], errors="coerce")
    remplaces = set(d["numero_dpe_remplace"].dropna().astype(str)) - {""}
    d = d[~d["numero_dpe"].astype(str).isin(remplaces)]
    d = d[d["type_batiment"].isin(["maison", "appartement"])]
    d = d[d["etiquette_dpe"].isin(list("ABCDEFG"))]
    d = d[pd.to_numeric(d["score_ban"], errors="coerce").fillna(0) >= C.SCORE_BAN_MIN]
    d = d.drop_duplicates("numero_dpe")

    d["code_insee_ban"] = d["code_insee_ban"].astype(str).str.zfill(5)
    d["numero_norm"] = d["numero_voie_ban"].map(normaliser_numero)
    d["voie_norm"] = d["nom_rue_ban"].map(normaliser_voie)
    d["cle_adresse"] = cle_adresse(d["code_insee_ban"], d["numero_norm"], d["voie_norm"])
    d["dpe_genere_immeuble"] = d["methode_application_dpe"].astype(str).str.contains("immeuble")
    return d.reset_index(drop=True)


def rapport_qualite_donnees(df: pd.DataFrame) -> pd.DataFrame:
    """Résume la qualité des données pour chaque variable."""

    rapport = pd.DataFrame({
        "type_donnee": df.dtypes.astype(str),
        "valeurs_manquantes": df.isna().sum(),
        "pourcentage_manquant": df.isna().mean() * 100,
        "valeurs_distinctes": df.nunique()
    })

    return rapport.sort_values(
        by="pourcentage_manquant",
        ascending=False
    )