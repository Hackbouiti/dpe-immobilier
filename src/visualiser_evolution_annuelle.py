"""Produit le graphique annuel des écarts de prix des classes F et G."""
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


RACINE = Path(__file__).resolve().parents[1]
DOSSIER_TABLEAUX = RACINE / "reports" / "tables"
DOSSIER_FIGURES = RACINE / "reports" / "figures"


def graphique_evolution(df=None, enregistrer=True):
    """Courbe des écarts de F et G par rapport à D, année par année.

    df : tableau produit par produire_evolution_annuelle.calculer_evolution.
    S'il n'est pas fourni, le tableau enregistré dans reports/tables est lu.
    """
    if df is None:
        df = pd.read_csv(DOSSIER_TABLEAUX / "evolution_annuelle_F_G.csv")

    fig, ax = plt.subplots(figsize=(11, 6.5))

    styles = {
        "F": {"marker": "o", "label": "Classe F"},
        "G": {"marker": "s", "label": "Classe G"},
    }

    for etiquette, style in styles.items():
        serie = df[df["etiquette"] == etiquette].sort_values("annee")
        ax.plot(
            serie["annee"],
            serie["ecart_comparable_pct"],
            marker=style["marker"],
            linewidth=2.5,
            markersize=8,
            label=style["label"],
        )

    # Repères réglementaires : mesures applicables aux locations en métropole.
    # 24 août 2022 : gel des augmentations de loyers pour les logements F et G concernés.
    date_gel_loyers = 2022 + 235 / 365
    ax.axvline(date_gel_loyers, color="darkorange", linestyle="-.", linewidth=1.5)
    ax.annotate(
        "24 août 2022 : gel des hausses de loyers\npour les logements F et G",
        xy=(date_gel_loyers, -8.0), xytext=(2022.02, -13.4),
        fontsize=8, color="darkorange",
        arrowprops={"arrowstyle": "->", "color": "darkorange"},
    )

    ax.axvline(2023, color="grey", linestyle=":", linewidth=1.5)
    ax.annotate(
        "2023 : seuil de 450 kWhEF/m²/an\npour les logements G les plus énergivores",
        xy=(2023, -7.5), xytext=(2022.05, -3.0),
        fontsize=8, color="dimgray",
        arrowprops={"arrowstyle": "->", "color": "grey"},
    )

    ax.axvline(2025, color="firebrick", linestyle="--", linewidth=1.5)
    ax.annotate(
        "2025 : classe G non décente\npour la location",
        xy=(2025, -12.5), xytext=(2023.55, -15.5),
        fontsize=8, color="firebrick",
        arrowprops={"arrowstyle": "->", "color": "firebrick"},
    )

    ax.axhline(0, color="black", linewidth=1)
    ax.set_xticks([2022, 2023, 2024, 2025])
    ax.set_xlabel("Année de la vente")
    ax.set_ylabel("Écart de prix comparable par rapport à D (%)")
    ax.set_title(
        "Évolution des écarts de prix des logements F et G\n"
        "par rapport aux logements D (2022–2025)"
    )
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    ax.text(
        0.01, -0.19,
        "Note : écarts descriptifs calculés sur les groupes de logements comparables. "
        "Les repères réglementaires ne démontrent pas un effet causal.",
        transform=ax.transAxes, fontsize=8, color="dimgray",
    )

    fig.tight_layout()
    if enregistrer:
        DOSSIER_FIGURES.mkdir(parents=True, exist_ok=True)
        fig.savefig(DOSSIER_FIGURES / "evolution_annuelle_F_G.png", dpi=300, bbox_inches="tight")
        fig.savefig(DOSSIER_FIGURES / "evolution_annuelle_F_G.pdf", bbox_inches="tight")

    return fig


if __name__ == "__main__":
    plt.close(graphique_evolution())
    print(f"Graphiques enregistrés dans {DOSSIER_FIGURES}")
