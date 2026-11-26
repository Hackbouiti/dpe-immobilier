"""Compare les résultats standard et les résultats en appariement strict.

    python -m src.produire_robustesse
"""

import pandas as pd

from . import chargement
from .produire_resultats import DOSSIER_TABLEAUX, calculer_resultats

COLONNES = [
    "reference",
    "etiquette",
    "ecart_comparable_pct",
    "ic_comparable_inf",
    "ic_comparable_sup",
    "part_cible_support_pct",
    "nombre_groupes_comparables",
]


def comparer_standard_strict(standard, strict):
    """Met côte à côte les résultats standard et stricts
    (tableaux produits par produire_resultats.calculer_resultats)."""
    tableaux = []
    for tableau, suffixe in [(standard, "standard"), (strict, "strict")]:
        tableaux.append(
            tableau[COLONNES].rename(columns={
                col: f"{col}_{suffixe}"
                for col in COLONNES
                if col not in ["reference", "etiquette"]
            })
        )

    return tableaux[0].merge(
        tableaux[1],
        on=["reference", "etiquette"],
        how="outer",
        validate="one_to_one",
    )


def main():
    print("Chargement des ventes...")
    ventes = chargement.charger_ventes()

    standard = calculer_resultats(ventes, strict=False)
    strict = calculer_resultats(ventes, strict=True)
    comparaison = comparer_standard_strict(standard, strict)

    DOSSIER_TABLEAUX.mkdir(parents=True, exist_ok=True)
    fichier = DOSSIER_TABLEAUX / "comparaison_standard_strict.csv"
    comparaison.to_csv(fichier, index=False, encoding="utf-8-sig")

    print("\nComparaison enregistrée :", fichier)
    print(
        comparaison[["reference", "etiquette", "ecart_comparable_pct_standard",
                     "ecart_comparable_pct_strict", "part_cible_support_pct_standard",
                     "part_cible_support_pct_strict"]]
        .round(2)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
