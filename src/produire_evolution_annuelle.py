"""Calcule l'évolution annuelle des écarts de prix des classes F et G.

    python -m src.produire_evolution_annuelle
"""

from . import chargement, ecarts
from .produire_resultats import DOSSIER_TABLEAUX

COLONNES = [
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


def calculer_evolution(ventes):
    """Écarts de F et G par rapport à D, année par année."""
    resultats = ecarts.calculer_ecarts_annuels(
        ventes,
        reference="D",
        min_effectif=1,
        strict=False,
    )

    if resultats.empty:
        raise ValueError("Aucun résultat annuel n'a été calculé.")

    resultats = resultats.loc[resultats["etiquette"].isin(["F", "G"])]
    return resultats[COLONNES].sort_values(["etiquette", "annee"]).reset_index(drop=True)


def main():
    print("Chargement des ventes...")
    ventes = chargement.charger_ventes()

    resultats = calculer_evolution(ventes)

    DOSSIER_TABLEAUX.mkdir(parents=True, exist_ok=True)
    fichier = DOSSIER_TABLEAUX / "evolution_annuelle_F_G.csv"
    resultats.to_csv(fichier, index=False, encoding="utf-8-sig")

    print("\nTableau annuel enregistré :", fichier)
    print(resultats.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
