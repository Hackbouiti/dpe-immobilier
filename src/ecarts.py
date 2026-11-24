"""Calcul des écarts de prix au m² selon l'étiquette énergétique."""

import numpy as np
import pandas as pd

from . import chargement


# Tranches de surface utilisées pour comparer des logements similaires.
BORNES_SURFACE = [0, 25, 40, 60, 80, 100, 150, 400]

# Variables définissant un groupe de logements comparables.
VARIABLES_COMPARAISON = [
    "code_commune",
    "type_bien",
    "tranche_surface",
    "periode_construction",
    "trimestre",
]


def preparer_echantillon(ventes, strict=False):
    """
    Prépare l'échantillon d'analyse.

    Par défaut : ventes appariées, hors ventes rapprochées.
    En mode strict : on exclut aussi les appariements ambigus
    et ceux réalisés par la distance.
    """
    df = chargement.preparer(ventes.copy())
    df = chargement.echantillon_analyse(df)

    if strict:
        df = df.loc[chargement.appariement_strict(df)].copy()

    df = df.copy()

    # Vérification et conversion des variables nécessaires.
    df["prix_m2"] = pd.to_numeric(df["prix_m2"], errors="coerce")
    df["surface"] = pd.to_numeric(df["surface"], errors="coerce")

    df = df.loc[
        df["prix_m2"].gt(0)
        & df["surface"].gt(0)
        & df["etiquette_dpe"].notna()
    ].copy()

    # Création des tranches de surface.
    df["tranche_surface"] = pd.cut(
        df["surface"],
        bins=BORNES_SURFACE,
        right=False,
        include_lowest=True,
    )

    # On écarte les observations hors des bornes définies.
    df = df.loc[df["tranche_surface"].notna()].copy()

    return df


def _resumer_groupes(df, reference, cible):
    """Calcule les effectifs et moyennes logarithmiques par groupe."""

    variables = VARIABLES_COMPARAISON + ["etiquette_dpe"]

    resume = (
        df.groupby(
            variables,
            observed=True,
            dropna=False,
        )["prix_m2"]
        .agg(
            effectif="count",
            moyenne_log=lambda x: np.log(x).mean(),
        )
        .reset_index()
    )

    effectifs = resume.pivot(
        index=VARIABLES_COMPARAISON,
        columns="etiquette_dpe",
        values="effectif",
    )

    moyennes = resume.pivot(
        index=VARIABLES_COMPARAISON,
        columns="etiquette_dpe",
        values="moyenne_log",
    )

    if reference not in effectifs.columns:
        return None, None

    return effectifs, moyennes


def calculer_ecarts(ventes, reference="G", min_effectif=1, strict=False):
    """
    Calcule les écarts bruts et comparables pour chaque étiquette
    par rapport à une étiquette de référence (G ou D).

    L'écart comparable est calculé dans les groupes contenant
    suffisamment de ventes de la classe étudiée et de la référence.

    Les différences sont calculées sur le logarithme du prix au m².
    Leur transformation en pourcentage est : 100 * (exp(écart) - 1).

    Paramètres
    ----------
    ventes : pandas.DataFrame
        Données de ventes issues du module chargement.
    reference : str
        Étiquette de référence : "G" ou "D".
    min_effectif : int
        Nombre minimal de ventes de chaque étiquette dans un groupe.
    strict : bool
        Active ou non le filtre d'appariement strict.

    Retour
    ------
    pandas.DataFrame
        Une ligne par étiquette comparée à la référence.
    """
    if reference not in list("ABCDEFG"):
        raise ValueError("La référence doit être une étiquette de A à G.")

    if not isinstance(min_effectif, int) or min_effectif < 1:
        raise ValueError("min_effectif doit être un entier supérieur ou égal à 1.")

    df = preparer_echantillon(ventes, strict=strict)

    if df.empty:
        raise ValueError("L'échantillon d'analyse est vide.")

    if reference not in df["etiquette_dpe"].astype(str).unique():
        raise ValueError(
            f"Aucune vente disponible pour l'étiquette de référence {reference}."
        )

    # Écart brut : différence entre les moyennes des logarithmes
    # des prix au m² de toutes les ventes de chaque étiquette.
    moyennes_brutes = (
        df.assign(log_prix_m2=np.log(df["prix_m2"]))
        .groupby("etiquette_dpe", observed=True)["log_prix_m2"]
        .agg(["mean", "count"])
    )

    effectifs, moyennes = _resumer_groupes(
        df,
        reference=reference,
        cible=None,
    )

    resultats = []

    for cible in list("ABCDEFG"):
        if cible == reference or cible not in moyennes_brutes.index:
            continue

        ecart_brut = (
            moyennes_brutes.loc[cible, "mean"]
            - moyennes_brutes.loc[reference, "mean"]
        )

        n_cible_brut = int(moyennes_brutes.loc[cible, "count"])
        n_reference_brut = int(moyennes_brutes.loc[reference, "count"])

        if cible not in effectifs.columns or cible not in moyennes.columns:
            groupes_valides = pd.DataFrame()
        else:
            comparaison = pd.DataFrame({
                "n_cible": effectifs[cible],
                "n_reference": effectifs[reference],
                "moyenne_cible": moyennes[cible],
                "moyenne_reference": moyennes[reference],
            })

            groupes_valides = comparaison.dropna()

            groupes_valides = groupes_valides.loc[
                groupes_valides["n_cible"].ge(min_effectif)
                & groupes_valides["n_reference"].ge(min_effectif)
            ].copy()

        if groupes_valides.empty:
            ecart_comparable = np.nan
            n_cible_support = 0
            n_reference_support = 0
            nombre_groupes = 0
        else:
            # Différence de moyennes logarithmiques au sein de chaque groupe.
            groupes_valides["difference"] = (
                groupes_valides["moyenne_cible"]
                - groupes_valides["moyenne_reference"]
            )

            # Pondération par le nombre de ventes de la classe comparée.
            poids = groupes_valides["n_cible"]

            ecart_comparable = np.average(
                groupes_valides["difference"],
                weights=poids,
            )

            n_cible_support = int(groupes_valides["n_cible"].sum())
            n_reference_support = int(groupes_valides["n_reference"].sum())
            nombre_groupes = len(groupes_valides)

        resultats.append({
            "reference": reference,
            "etiquette": cible,
            "ecart_brut_log": ecart_brut,
            "ecart_brut_pct": 100 * np.expm1(ecart_brut),
            "ecart_comparable_log": ecart_comparable,
            "ecart_comparable_pct": (
                100 * np.expm1(ecart_comparable)
                if pd.notna(ecart_comparable)
                else np.nan
            ),
            "n_cible_brut": n_cible_brut,
            "n_reference_brut": n_reference_brut,
            "n_cible_support": n_cible_support,
            "n_reference_support": n_reference_support,
            "nombre_groupes_comparables": nombre_groupes,
            "part_cible_support_pct": (
                100 * n_cible_support / n_cible_brut
                if n_cible_brut > 0
                else np.nan
            ),
            "min_effectif": min_effectif,
            "appariement_strict": strict,
        })

    return pd.DataFrame(resultats)


def calculer_ecarts_annuels(
    ventes,
    reference="G",
    min_effectif=1,
    strict=False,
):
    """
    Recalcule les écarts séparément pour chaque année disponible.
    """
    df = preparer_echantillon(ventes, strict=strict)

    if "annee" not in df.columns:
        df["annee"] = pd.to_datetime(df["date_mutation"]).dt.year

    resultats = []

    for annee in sorted(df["annee"].dropna().unique()):
        donnees_annee = df.loc[df["annee"].eq(annee)].copy()

        if donnees_annee.empty:
            continue

        resultat = calculer_ecarts(
            donnees_annee,
            reference=reference,
            min_effectif=min_effectif,
            strict=strict,
        )

        resultat.insert(0, "annee", int(annee))
        resultats.append(resultat)

    if not resultats:
        return pd.DataFrame()

    return pd.concat(resultats, ignore_index=True)
