"""Création des graphiques des écarts de prix selon le DPE."""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RACINE = Path(__file__).resolve().parents[1]
DOSSIER_TABLEAUX = RACINE / "reports" / "tables"
DOSSIER_FIGURES = RACINE / "reports" / "figures"


def graphique_ecarts(df=None, enregistrer=True):
    """Graphique des écarts brut et comparable, avec G et D comme références.

    df : tableau produit par produire_resultats.calculer_resultats. S'il n'est
    pas fourni, le tableau enregistré dans reports/tables est lu.
    """
    if df is None:
        df = pd.read_csv(DOSSIER_TABLEAUX / "resultats_principaux_bootstrap.csv")

    references = ["G", "D"]

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    configurations = [
        {
            "ecart": "ecart_brut_pct",
            "borne_inf": "ic_brut_inf",
            "borne_sup": "ic_brut_sup",
            "nom": "Écart brut",
            "couleur": "#2878B5",
            "decalage": 0.12,
            "marqueur": "o",
        },
        {
            "ecart": "ecart_comparable_pct",
            "borne_inf": "ic_comparable_inf",
            "borne_sup": "ic_comparable_sup",
            "nom": "Écart comparable",
            "couleur": "#D97732",
            "decalage": -0.12,
            "marqueur": "s",
        },
    ]

    for ax, reference in zip(axes, references):
        donnees = df.loc[df["reference"].eq(reference)].copy()
        donnees = donnees.sort_values("etiquette")

        positions = np.arange(len(donnees))

        for config in configurations:
            valeurs = donnees[config["ecart"]].to_numpy()
            borne_inf = donnees[config["borne_inf"]].to_numpy()
            borne_sup = donnees[config["borne_sup"]].to_numpy()

            erreurs = np.vstack([
                valeurs - borne_inf,
                borne_sup - valeurs,
            ])

            ax.errorbar(
                valeurs,
                positions + config["decalage"],
                xerr=erreurs,
                fmt=config["marqueur"],
                color=config["couleur"],
                ecolor=config["couleur"],
                markersize=7,
                capsize=4,
                linewidth=1.8,
                label=config["nom"],
            )

        ax.axvline(0, color="#444444", linewidth=1, linestyle="--")
        ax.set_yticks(positions)
        ax.set_yticklabels(donnees["etiquette"])
        ax.invert_yaxis()
        ax.set_xlabel("Écart de prix au m² (%)", fontsize=11)
        ax.set_title(
            f"Référence énergétique {reference}",
            fontsize=13,
            fontweight="bold",
        )
        ax.grid(axis="x", alpha=0.25)
        ax.legend(frameon=False, loc="best")

    fig.suptitle(
        "Écarts de prix au m² selon l'étiquette énergétique",
        fontsize=16,
        fontweight="bold",
    )

    fig.text(
        0.5,
        0.015,
        "Intervalles de confiance à 95 % — bootstrap par communes "
        "(1 000 répétitions).",
        ha="center",
        fontsize=10,
    )

    fig.tight_layout(rect=[0, 0.05, 1, 0.93])

    if enregistrer:
        DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
        fig.savefig(DOSSIER_FIGURES / "ecarts_prix_references.png", dpi=300, bbox_inches="tight")
        fig.savefig(DOSSIER_FIGURES / "ecarts_prix_references.pdf", bbox_inches="tight")

    return fig


if __name__ == "__main__":
    plt.close(graphique_ecarts())
    print(f"Graphiques enregistrés dans {DOSSIER_FIGURES}")
