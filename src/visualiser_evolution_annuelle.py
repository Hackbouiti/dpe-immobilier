"""Produit le graphique annuel des écarts de prix des classes F et G."""
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


def main():
    fichier = Path("reports/tables/evolution_annuelle_F_G.csv")
    df = pd.read_csv(fichier)

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
    dossier = Path("reports/figures")
    dossier.mkdir(parents=True, exist_ok=True)
    fig.savefig(dossier / "evolution_annuelle_F_G.png", dpi=300, bbox_inches="tight")
    fig.savefig(dossier / "evolution_annuelle_F_G.pdf", bbox_inches="tight")
    plt.close(fig)
    print("Graphiques enregistrés dans reports/figures/")


if __name__ == "__main__":
    main()
