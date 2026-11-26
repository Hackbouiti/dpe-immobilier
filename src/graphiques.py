"""Fonctions graphiques pour l'analyse descriptive du projet."""

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure


def boxplots_prix_dpe(echantillon: pd.DataFrame, *, titre: str) -> Figure:
    """Comparer les prix au m² par DPE, séparément selon le type de bien.

    Paramètres
    ----------
    echantillon : pandas.DataFrame
        Ventes retenues pour l'analyse. Colonnes nécessaires :
        type_bien, etiquette_dpe et prix_m2.
    titre : str
        Titre indiquant le périmètre et la période étudiés.

    Retour
    ------
    matplotlib.figure.Figure
        Figure à enregistrer et à afficher depuis le notebook.
    """
    etiquettes = list("ABCDEFG")
    couleurs = [
        "#2A9D68", "#71B66B", "#B5CE68", "#F0D65B",
        "#F4AA55", "#E7754E", "#CB4945",
    ]

    # Vérifier la présence des informations nécessaires
    necessaires = {"type_bien", "etiquette_dpe", "prix_m2"}
    manquantes = necessaires.difference(echantillon.columns)

    if manquantes:
        raise ValueError(f"Colonnes absentes : {', '.join(sorted(manquantes))}")
    if echantillon.empty:
        raise ValueError("L'échantillon d'analyse est vide.")

    # Utiliser la même échelle verticale pour les deux panneaux
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
    types_biens = [
        ("appartement", "Appartements"),
        ("maison", "Maisons"),
    ]
    n_representes = 0

    for ax, (type_bien, nom) in zip(axes, types_biens):
        selection = echantillon.loc[
            echantillon["type_bien"].eq(type_bien)
        ]

        # Rassembler les prix de chaque classe dans l'ordre A à G
        prix = [
            selection.loc[
                selection["etiquette_dpe"].eq(lettre), "prix_m2"
            ].dropna().to_numpy()
            for lettre in etiquettes
        ]
        n_representes += sum(len(valeurs) for valeurs in prix)

        # Masquer les points extrêmes sans les retirer des calculs
        boites = ax.boxplot(
            prix,
            patch_artist=True,
            showfliers=False,
            widths=0.6,
            medianprops={"color": "#172B4D", "linewidth": 2},
        )

        for boite, couleur in zip(boites["boxes"], couleurs):
            boite.set_facecolor(couleur)

        # Indiquer le nombre de prix renseignés sous chaque classe
        libelles = [
            f"{lettre}\nn={len(valeurs):,}".replace(",", " ")
            for lettre, valeurs in zip(etiquettes, prix)
        ]

        ax.set_xticks(range(1, 8), libelles, fontsize=9)
        ax.set_title(nom, fontsize=14)
        ax.set_xlabel("Étiquette DPE et nombre de prix renseignés")
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)

    axes[0].set_ylabel("Prix de vente (€/m²)")
    axes[0].set_ylim(bottom=0)
    fig.suptitle(titre, fontsize=15)

    effectif = f"{n_representes:,}".replace(",", " ")
    fig.text(
        0.5, 0.90,
        f"Échantillon d'analyse : {effectif} prix renseignés représentés",
        ha="center",
        fontsize=10,
    )

    fig.text(
        0.07, 0.03,
        "Boîte : 50 % centraux des prix ; trait : médiane. "
        "Moustaches : règle de 1,5 × écart interquartile.\n"
        "Points au-delà des moustaches masqués ; toutes les valeurs "
        "renseignées participent aux calculs.\n"
        "Source : données DVF–DPE préparées du projet. Analyse descriptive.",
        fontsize=9,
        color="#475569",
    )

    fig.tight_layout(rect=[0, 0.13, 1, 0.89])
    return fig


def matrice_spearman(
    correlations: pd.DataFrame,
    effectifs: pd.DataFrame,
    *,
    titre: str,
) -> Figure:
    """Afficher les coefficients de Spearman et leurs effectifs par paire.

    Les tableaux sont remis dans le même ordre avant le dessin.
    Seul l'affichage des coefficients est arrondi.
    Une corrélation non calculable est indiquée par ND.
    La figure est retournée pour être enregistrée depuis le notebook.
    """
    libelles = {
        "prix_m2": "Prix au m²\n(€/m²)",
        "surface": "Surface\n(m²)",
        "conso_5_usages_par_m2_ep": "Consommation\n(kWhEP/m²/an)",
        "rang_dpe": "Rang DPE\nA = 1 ; G = 7",
        "annee_construction": "Année de\nconstruction",
    }

    # Garantir le même ordre pour les valeurs et les légendes
    ordre = list(libelles)
    matrice = correlations.loc[ordre, ordre]
    nombres = effectifs.loc[ordre, ordre]

    # Fixer l'échelle de couleurs entre -1 et +1
    couleurs = plt.get_cmap("RdBu_r").copy()
    couleurs.set_bad("#E5E7EB")

    fig, ax = plt.subplots(figsize=(10.5, 8.6))
    carte = ax.imshow(
        matrice.to_numpy(dtype=float),
        cmap=couleurs,
        vmin=-1,
        vmax=1,
        interpolation="nearest",
    )

    positions = list(range(len(ordre)))
    ax.set_xticks(positions, list(libelles.values()), fontsize=9)
    ax.set_yticks(positions, list(libelles.values()), fontsize=10)
    ax.tick_params(axis="both", length=0, pad=10)

    for bordure in ax.spines.values():
        bordure.set_visible(False)

    # Écrire le coefficient et l'effectif dans chaque case
    for i in positions:
        for j in positions:
            valeur = matrice.iloc[i, j]

            coefficient = (
                "ND" if pd.isna(valeur)
                else f"{valeur:.3f}".replace(".", ",")
            )
            effectif = f"n = {int(nombres.iloc[i, j]):,}".replace(
                ",", " "
            )

            # Adapter le texte aux cases claires ou foncées
            couleur_texte = (
                "white"
                if pd.notna(valeur) and abs(valeur) >= 0.6
                else "#172B4D"
            )

            ax.text(
                j, i - 0.08, coefficient,
                ha="center", va="center", fontsize=13,
                fontweight="bold", color=couleur_texte,
            )
            ax.text(
                j, i + 0.20, effectif,
                ha="center", va="center", fontsize=8,
                color=couleur_texte,
            )

    barre = fig.colorbar(carte, ax=ax, fraction=0.045, pad=0.04)
    barre.set_label("Coefficient de Spearman")
    barre.set_ticks([-1, -0.5, 0, 0.5, 1])

    fig.suptitle(titre, fontsize=14, y=0.97)
    fig.text(
        0.5, 0.91,
        "Ventes appariées, hors ventes rapprochées — associations brutes",
        ha="center", fontsize=10,
    )
    fig.text(
        0.08, 0.04,
        "n : ventes renseignées pour les deux variables. "
        "Année de construction retenue après contrôles de cohérence.\n"
        "Consommation conventionnelle d'énergie primaire par m² et par an.\n"
        "Source : données DVF–DPE préparées du projet. "
        "Les corrélations ne mesurent pas des effets causaux.",
        fontsize=9, color="#475569",
    )

    fig.subplots_adjust(
        left=0.20, right=0.90, bottom=0.18, top=0.85
    )
    return fig
