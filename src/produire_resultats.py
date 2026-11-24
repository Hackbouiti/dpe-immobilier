"""Production des résultats principaux et de leurs intervalles de confiance."""

from pathlib import Path

import pandas as pd

from . import bootstrap, chargement, ecarts


def main():
    nombre_repetitions = 1000
    graine = 42

    print("Chargement des ventes...")
    ventes = chargement.charger_ventes()

    resultats = []

    colonnes_support = [
        "reference",
        "etiquette",
        "n_cible_brut",
        "n_reference_brut",
        "n_cible_support",
        "n_reference_support",
        "nombre_groupes_comparables",
        "part_cible_support_pct",
    ]

    for reference in ["G", "D"]:
        print(f"\nCalcul avec la référence {reference}...")

        support = ecarts.calculer_ecarts(
            ventes,
            reference=reference,
            min_effectif=1,
            strict=False,
        )

        intervalles = bootstrap.bootstrap_ecarts(
            ventes,
            reference=reference,
            min_effectif=1,
            strict=False,
            n_boot=nombre_repetitions,
            seed=graine,
        )

        tableau = intervalles.merge(
            support[colonnes_support],
            on=["reference", "etiquette"],
            how="left",
            validate="one_to_one",
        )

        resultats.append(tableau)

        print(f"Résultats calculés pour la référence {reference}.")

    final = pd.concat(resultats, ignore_index=True)

    final["methode_intervalle"] = "Bootstrap par communes, percentile à 95 %"
    final["graine"] = graine
    final["min_effectif"] = 1

    colonnes = [
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

    final = final[colonnes].sort_values(
        ["reference", "etiquette"]
    )

    dossier = Path(__file__).resolve().parents[1] / "reports" / "tables"
    dossier.mkdir(parents=True, exist_ok=True)

    sortie = dossier / "resultats_principaux_bootstrap.csv"
    final.to_csv(sortie, index=False, encoding="utf-8-sig")

    print("\nTableau enregistré :", sortie)
    print("\nRésultats :")
    print(
        final[
            [
                "reference",
                "etiquette",
                "ecart_brut_pct",
                "ecart_comparable_pct",
                "ic_comparable_inf",
                "ic_comparable_sup",
                "part_cible_support_pct",
            ]
        ].round(2).to_string(index=False)
    )


if __name__ == "__main__":
    main()
