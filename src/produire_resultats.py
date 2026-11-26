"""Production des résultats principaux et de leurs intervalles de confiance.

Les fonctions sont appelées par le notebook du rapport. Le script peut aussi
être lancé seul pour écrire les tableaux dans reports/tables :

    python -m src.produire_resultats
"""

from pathlib import Path

import pandas as pd

from . import bootstrap, chargement, ecarts

NOMBRE_REPETITIONS = 1000
GRAINE = 42
DOSSIER_TABLEAUX = Path(__file__).resolve().parents[1] / "reports" / "tables"

COLONNES_SUPPORT = [
    "reference",
    "etiquette",
    "n_cible_brut",
    "n_reference_brut",
    "n_cible_support",
    "n_reference_support",
    "nombre_groupes_comparables",
    "part_cible_support_pct",
]

COLONNES = [
    "reference",
    "etiquette",
    "ecart_brut_pct",
    "ic_brut_inf",
    "ic_brut_sup",
    "ecart_comparable_pct",
    "ic_comparable_inf",
    "ic_comparable_sup",
    "n_cible_brut",
    "n_reference_brut",
    "n_cible_support",
    "n_reference_support",
    "part_cible_support_pct",
    "nombre_groupes_comparables",
    "nombre_communes",
    "nombre_repetitions",
    "repetitions_brutes_valides",
    "repetitions_comparables_valides",
    "appariement_strict",
    "min_effectif",
    "methode_intervalle",
    "graine",
]


def calculer_resultats(ventes, strict=False, n_boot=NOMBRE_REPETITIONS, graine=GRAINE):
    """Écarts bruts et comparables, avec G puis D comme référence,
    et intervalles de confiance par bootstrap en grappes de communes."""
    resultats = []

    for reference in ["G", "D"]:
        support = ecarts.calculer_ecarts(
            ventes,
            reference=reference,
            min_effectif=1,
            strict=strict,
        )

        intervalles = bootstrap.bootstrap_ecarts(
            ventes,
            reference=reference,
            min_effectif=1,
            strict=strict,
            n_boot=n_boot,
            seed=graine,
        )

        tableau = intervalles.merge(
            support[COLONNES_SUPPORT],
            on=["reference", "etiquette"],
            how="left",
            validate="one_to_one",
        )
        resultats.append(tableau)

    final = pd.concat(resultats, ignore_index=True)
    final["methode_intervalle"] = "Bootstrap par communes, percentile à 95 %"
    final["graine"] = graine
    final["min_effectif"] = 1

    return final[COLONNES].sort_values(["reference", "etiquette"]).reset_index(drop=True)


def main():
    print("Chargement des ventes...")
    ventes = chargement.charger_ventes()
    DOSSIER_TABLEAUX.mkdir(parents=True, exist_ok=True)

    for strict, nom in [(False, "resultats_principaux_bootstrap.csv"),
                        (True, "resultats_appariement_strict.csv")]:
        print(f"\nCalcul des résultats (appariement strict : {strict})...")
        final = calculer_resultats(ventes, strict=strict)
        sortie = DOSSIER_TABLEAUX / nom
        final.to_csv(sortie, index=False, encoding="utf-8-sig")
        print("Tableau enregistré :", sortie)
        print(
            final[["reference", "etiquette", "ecart_brut_pct", "ecart_comparable_pct",
                   "ic_comparable_inf", "ic_comparable_sup", "part_cible_support_pct"]]
            .round(2)
            .to_string(index=False)
        )


if __name__ == "__main__":
    main()
