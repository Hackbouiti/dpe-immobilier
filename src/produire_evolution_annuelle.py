"""Calcule l'évolution annuelle des écarts de prix des classes F et G."""

from pathlib import Path

import pandas as pd

from . import chargement, ecarts


def main():
    dossier = Path("reports/tables")
    dossier.mkdir(parents=True, exist_ok=True)

    print("Chargement des ventes...")
    ventes = chargement.charger_ventes()

    print("\nCalcul des écarts annuels avec D comme référence...")
    resultats = ecarts.calculer_ecarts_annuels(
        ventes,
        reference="D",
        min_effectif=1,
        strict=False,
    )

    if resultats.empty:
        raise ValueError("Aucun résultat annuel n'a été calculé.")

    resultats = resultats.loc[
        resultats["etiquette"].isin(["F", "G"])
    ].copy()

    colonnes = [
        "annee",
        "reference",
        "etiquette",
        "ecart_brut_pct",
        "ecart_comparable_pct",
        "n_cible_brut",
        "n_reference_brut",
        "n_cible_support",
        "n_reference_support",
        "part_cible_support_pct",
        "nombre_groupes_comparables",
    ]

    resultats = resultats[colonnes].sort_values(
        ["etiquette", "annee"]
    )

    fichier = dossier / "evolution_annuelle_F_G.csv"
    resultats.to_csv(fichier, index=False, encoding="utf-8-sig")

    print("\nTableau annuel enregistré :", fichier)
    print("\nRésultats :")
    print(resultats.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
