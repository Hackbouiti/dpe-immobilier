"""Compare les résultats standard et les résultats en appariement strict."""

from pathlib import Path

import pandas as pd

from . import chargement, ecarts


def main():
    dossier = Path("reports/tables")

    fichier_standard = dossier / "resultats_principaux_bootstrap.csv"
    fichier_strict = dossier / "resultats_appariement_strict.csv"

    if not fichier_strict.exists():
        raise FileNotFoundError(
            "Les résultats stricts sont introuvables. "
            "Il faut d'abord exécuter le bootstrap strict."
        )

    print("Chargement des résultats déjà calculés...")
    standard = pd.read_csv(fichier_standard)
    strict_bootstrap = pd.read_csv(fichier_strict)

    print("Chargement des ventes pour calculer la couverture...")
    ventes = chargement.charger_ventes()

    couvertures = []

    for reference in ["G", "D"]:
        print(f"Calcul de la couverture stricte pour {reference}...")
        resultat = ecarts.calculer_ecarts(
            ventes,
            reference=reference,
            strict=True,
        )
        couvertures.append(resultat)

    couverture_stricte = pd.concat(couvertures, ignore_index=True)

    colonnes_couverture = [
        "reference",
        "etiquette",
        "n_cible_brut",
        "n_cible_support",
        "part_cible_support_pct",
        "nombre_groupes_comparables",
    ]

    strict = strict_bootstrap.merge(
        couverture_stricte[colonnes_couverture],
        on=["reference", "etiquette"],
        how="left",
        validate="one_to_one",
    )

    colonnes = [
        "reference",
        "etiquette",
        "ecart_comparable_pct",
        "ic_comparable_inf",
        "ic_comparable_sup",
        "part_cible_support_pct",
        "nombre_groupes_comparables",
    ]

    standard_selection = standard[colonnes].rename(
        columns={
            col: f"{col}_standard"
            for col in colonnes
            if col not in ["reference", "etiquette"]
        }
    )

    strict_selection = strict[colonnes].rename(
        columns={
            col: f"{col}_strict"
            for col in colonnes
            if col not in ["reference", "etiquette"]
        }
    )

    comparaison = standard_selection.merge(
        strict_selection,
        on=["reference", "etiquette"],
        how="outer",
        validate="one_to_one",
    )

    fichier_comparaison = dossier / "comparaison_standard_strict.csv"
    comparaison.to_csv(
        fichier_comparaison,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nComparaison enregistrée :", fichier_comparaison)
    print("\nTableau comparatif :")

    colonnes_affichage = [
        "reference",
        "etiquette",
        "ecart_comparable_pct_standard",
        "ecart_comparable_pct_strict",
        "part_cible_support_pct_standard",
        "part_cible_support_pct_strict",
    ]

    print(
        comparaison[colonnes_affichage]
        .round(2)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
