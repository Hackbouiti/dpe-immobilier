
"""Bootstrap par communes pour les écarts de prix selon le DPE."""

import numpy as np
import pandas as pd

from . import ecarts


def bootstrap_ecarts(
    ventes,
    reference="G",
    min_effectif=1,
    strict=False,
    n_boot=1000,
    seed=42,
):
    """
    Calcule les écarts de prix et leurs intervalles de confiance
    par bootstrap en grappes de communes.

    Chaque réplication tire les communes avec remise.
    Toutes les ventes d'une commune tirée sont conservées.

    Cette première version exige min_effectif=1.
    """

    if reference not in list("ABCDEFG"):
        raise ValueError("La référence doit être une étiquette de A à G.")

    if min_effectif != 1:
        raise ValueError(
            "Cette version du bootstrap exige min_effectif=1."
        )

    if not isinstance(n_boot, int) or n_boot < 1:
        raise ValueError("n_boot doit être un entier positif.")

    # Préparation des données une seule fois.
    df = ecarts.preparer_echantillon(ventes, strict=strict)

    if df.empty:
        raise ValueError("L'échantillon d'analyse est vide.")

    etiquettes = list("ABCDEFG")

    if reference not in df["etiquette_dpe"].astype(str).unique():
        raise ValueError(
            f"Aucune vente disponible pour la référence {reference}."
        )

    df = df.copy()
    df["log_prix_m2"] = np.log(df["prix_m2"])

    # Liste des communes de l'échantillon.
    communes = pd.Index(df["code_commune"].drop_duplicates())
    nombre_communes = len(communes)

    # ---------------------------------------------------------
    # 1. Statistiques nécessaires aux écarts bruts
    # ---------------------------------------------------------

    resume_brut = (
        df.groupby(
            ["code_commune", "etiquette_dpe"],
            observed=True,
        )["log_prix_m2"]
        .agg(
            somme_log="sum",
            effectif="count",
        )
        .unstack("etiquette_dpe")
    )

    sommes_brutes = (
        resume_brut["somme_log"]
        .reindex(index=communes, columns=etiquettes)
        .fillna(0)
        .to_numpy()
    )

    effectifs_bruts = (
        resume_brut["effectif"]
        .reindex(index=communes, columns=etiquettes)
        .fillna(0)
        .to_numpy()
    )

    # ---------------------------------------------------------
    # 2. Statistiques nécessaires aux écarts comparables
    # ---------------------------------------------------------

    resume_groupes = (
        df.groupby(
            ecarts.VARIABLES_COMPARAISON + ["etiquette_dpe"],
            observed=True,
            dropna=False,
        )["log_prix_m2"]
        .agg(
            effectif="count",
            moyenne_log="mean",
        )
        .reset_index()
    )

    effectifs = resume_groupes.pivot(
        index=ecarts.VARIABLES_COMPARAISON,
        columns="etiquette_dpe",
        values="effectif",
    )

    moyennes = resume_groupes.pivot(
        index=ecarts.VARIABLES_COMPARAISON,
        columns="etiquette_dpe",
        values="moyenne_log",
    )

    position_commune = {
        commune: i for i, commune in enumerate(communes)
    }

    contributions = {}

    for cible in etiquettes:
        if cible == reference:
            continue

        if cible not in effectifs.columns or reference not in effectifs.columns:
            continue

        comparaison = pd.DataFrame({
            "n_cible": effectifs[cible],
            "n_reference": effectifs[reference],
            "moyenne_cible": moyennes[cible],
            "moyenne_reference": moyennes[reference],
        })

        groupes_valides = comparaison.dropna()

        groupes_valides = groupes_valides.loc[
            groupes_valides["n_cible"].ge(1)
            & groupes_valides["n_reference"].ge(1)
        ].copy()

        # Contributions propres à chaque commune.
        numerateur = (
            groupes_valides["n_cible"]
            * (
                groupes_valides["moyenne_cible"]
                - groupes_valides["moyenne_reference"]
            )
        )

        denominateur = groupes_valides["n_cible"]

        communes_groupes = (
            groupes_valides.index.get_level_values("code_commune")
        )

        numerateur_commune = numerateur.groupby(
            communes_groupes,
            observed=True,
        ).sum()

        denominateur_commune = denominateur.groupby(
            communes_groupes,
            observed=True,
        ).sum()

        tableau = np.zeros((nombre_communes, 2))

        for commune, valeur in numerateur_commune.items():
            tableau[position_commune[commune], 0] = valeur

        for commune, valeur in denominateur_commune.items():
            tableau[position_commune[commune], 1] = valeur

        contributions[cible] = tableau

    # ---------------------------------------------------------
    # 3. Estimations ponctuelles et bootstrap
    # ---------------------------------------------------------

    rng = np.random.default_rng(seed)
    resultats = []

    indice_reference = etiquettes.index(reference)

    for cible in etiquettes:
        if cible == reference:
            continue

        indice_cible = etiquettes.index(cible)

        n_cible = effectifs_bruts[:, indice_cible].sum()
        n_reference = effectifs_bruts[:, indice_reference].sum()

        if n_cible == 0 or n_reference == 0:
            continue

        ecart_brut = (
            sommes_brutes[:, indice_cible].sum() / n_cible
            - sommes_brutes[:, indice_reference].sum() / n_reference
        )

        # Estimation comparable ponctuelle.
        if cible in contributions:
            numerateur = contributions[cible][:, 0].sum()
            denominateur = contributions[cible][:, 1].sum()
        else:
            numerateur = 0
            denominateur = 0

        ecart_comparable = (
            numerateur / denominateur
            if denominateur > 0
            else np.nan
        )

        repetitions_brutes = []
        repetitions_comparables = []

        for _ in range(n_boot):

            # Tirage de communes avec remise.
            tirages = rng.integers(
                0,
                nombre_communes,
                size=nombre_communes,
            )

            multiplicites = np.bincount(
                tirages,
                minlength=nombre_communes,
            )

            # Écart brut de cette réplication.
            somme_cible = multiplicites @ sommes_brutes[:, indice_cible]
            somme_reference = multiplicites @ sommes_brutes[:, indice_reference]

            compte_cible = multiplicites @ effectifs_bruts[:, indice_cible]
            compte_reference = multiplicites @ effectifs_bruts[:, indice_reference]

            if compte_cible > 0 and compte_reference > 0:
                ecart = (
                    somme_cible / compte_cible
                    - somme_reference / compte_reference
                )
                repetitions_brutes.append(100 * np.expm1(ecart))

            # Écart comparable de cette réplication.
            if cible in contributions:
                numerateur_rep = (
                    multiplicites @ contributions[cible][:, 0]
                )
                denominateur_rep = (
                    multiplicites @ contributions[cible][:, 1]
                )

                if denominateur_rep > 0:
                    repetitions_comparables.append(
                        100 * np.expm1(
                            numerateur_rep / denominateur_rep
                        )
                    )

        # Intervalles de confiance percentile à 95 %.
        ic_brut = (
            np.quantile(repetitions_brutes, [0.025, 0.975])
            if repetitions_brutes
            else [np.nan, np.nan]
        )

        ic_comparable = (
            np.quantile(repetitions_comparables, [0.025, 0.975])
            if repetitions_comparables
            else [np.nan, np.nan]
        )

        resultats.append({
            "reference": reference,
            "etiquette": cible,
            "ecart_brut_pct": 100 * np.expm1(ecart_brut),
            "ic_brut_inf": ic_brut[0],
            "ic_brut_sup": ic_brut[1],
            "repetitions_brutes_valides": len(repetitions_brutes),
            "ecart_comparable_pct": (
                100 * np.expm1(ecart_comparable)
                if pd.notna(ecart_comparable)
                else np.nan
            ),
            "ic_comparable_inf": ic_comparable[0],
            "ic_comparable_sup": ic_comparable[1],
            "repetitions_comparables_valides": len(
                repetitions_comparables
            ),
            "nombre_communes": nombre_communes,
            "nombre_repetitions": n_boot,
            "appariement_strict": strict,
        })

    return pd.DataFrame(resultats)
