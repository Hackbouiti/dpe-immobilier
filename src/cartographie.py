"""Carte départementale des ventes F/G dans l'échantillon d'analyse."""

from hashlib import sha256
from pathlib import Path
from textwrap import fill

import geopandas as gpd
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd
import requests
from matplotlib.patches import ConnectionPatch, Patch, Rectangle

URL_FOND = (
    "https://etalab-datasets.geo.data.gouv.fr/"
    "contours-administratifs/2025/geojson/departements-100m.geojson"
)
SHA256_FOND = (
    "10f5c6ffc2dc857b4f4fc360297f97f6f01fc3ba3eb3a326ee92b76baefed447"
)


def parts_fg(echantillon):
    """Compter les ventes retenues et les ventes F/G par département.

    Chaque ligne représente une vente retenue par echantillon_analyse.
    Une étiquette ou un département manquant déclenche une erreur.
    """
    donnees = echantillon[["code_departement", "etiquette_dpe"]].copy()
    donnees["code_departement"] = (
        donnees["code_departement"].astype("string").str.strip().str.zfill(2)
    )

    codes_valides = donnees["code_departement"].str.fullmatch(
        r"(?:[0-9]{2}|2A|2B)"
    ).fillna(False)

    if donnees.empty or not codes_valides.all():
        raise ValueError("Échantillon vide ou code département non valide.")

    if not donnees["etiquette_dpe"].isin(list("ABCDEFG")).all():
        raise ValueError("Au moins une étiquette DPE est absente ou invalide.")

    donnees["est_fg"] = donnees["etiquette_dpe"].isin(["F", "G"])

    tableau = donnees.groupby("code_departement", observed=True).agg(
        nombre_ventes=("est_fg", "size"),
        nombre_fg=("est_fg", "sum"),
    )
    tableau["part_fg_pct"] = (
        100 * tableau["nombre_fg"] / tableau["nombre_ventes"]
    )

    return tableau.reset_index()


def fond_departements(dossier):
    """Lire les contours 2025 en cache, après vérification de leur empreinte.

    Source : data.gouv.fr, Contours administratifs, généralisation 100 m.
    Licence du jeu : ODbL. La carte utilise les départements métropolitains.
    """
    chemin = Path(dossier) / "departements_2025_100m.geojson"

    if chemin.exists():
        contenu = chemin.read_bytes()
    else:
        reponse = requests.get(URL_FOND, timeout=60)
        reponse.raise_for_status()
        contenu = reponse.content

    if sha256(contenu).hexdigest() != SHA256_FOND:
        raise ValueError("Fond de carte différent de la version vérifiée.")

    if not chemin.exists():
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)

    fond = gpd.read_file(chemin)
    fond = fond.loc[fond["code"].str.len().eq(2)].copy()
    fond = fond.rename(columns={"code": "code_departement"})

    if len(fond) != 96 or not fond["code_departement"].is_unique:
        raise ValueError("Nombre ou codes de départements inattendus.")

    # Réparer les petits défauts de contour avant leur projection.
    fond["geometry"] = fond.geometry.make_valid()

    return fond.to_crs(2154)


def carte_fg(tableau, fond, *, titre):
    """Afficher les noms et les parts F/G, avec un zoom francilien repéré.

    Les étiquettes arrondissent l'affichage à deux décimales seulement.
    Le fond et le tableau d'entrée ne sont pas modifiés.
    """
    inconnus = set(tableau["code_departement"]) - set(fond["code_departement"])
    if inconnus:
        raise ValueError(f"Départements sans contour : {sorted(inconnus)}")

    if tableau.empty or not tableau["part_fg_pct"].between(0, 50).all():
        raise ValueError("Parts hors de l'échelle 0–50 % : adapter la carte.")

    colonnes = [
        "code_departement", "nombre_ventes", "nombre_fg", "part_fg_pct"
    ]
    carte = fond.merge(
        tableau[colonnes],
        on="code_departement",
        how="left",
        validate="one_to_one",
    )

    # Disposer la carte principale, le zoom et la légende.
    fig = plt.figure(figsize=(18, 14))
    ax = fig.add_axes([0.01, 0.15, 0.73, 0.76])
    ax_zoom = fig.add_axes([0.76, 0.49, 0.23, 0.33])
    barre = fig.add_axes([0.18, 0.105, 0.46, 0.015])

    style = {
        "column": "part_fg_pct",
        "cmap": "YlOrRd",
        "vmin": 0,
        "vmax": 50,
        "edgecolor": "white",
        "linewidth": 0.7,
        "missing_kwds": {
            "color": "#D7DCE3",
            "edgecolor": "#8793A3",
            "hatch": "///",
        },
    }

    carte.plot(
        ax=ax,
        cax=barre,
        legend=True,
        **style,
        legend_kwds={
            "orientation": "horizontal",
            "label": "Ventes F/G parmi les ventes retenues (%)",
        },
    )

    ile_de_france = carte.loc[carte["region"].eq("11")]
    ile_de_france.plot(ax=ax_zoom, **style)
    ax_zoom.set_title("ZOOM — Île-de-France", fontsize=13, pad=16)

    # Repérer la position réelle de l'Île-de-France.
    xmin, ymin, xmax, ymax = ile_de_france.total_bounds
    marge = 5000

    ax.add_patch(Rectangle(
        (xmin - marge, ymin - marge),
        xmax - xmin + 2 * marge,
        ymax - ymin + 2 * marge,
        fill=False,
        edgecolor="#243447",
        linewidth=1.2,
        linestyle="--",
    ))

    ax.add_artist(ConnectionPatch(
        xyA=(xmax + marge, (ymin + ymax) / 2),
        coordsA=ax.transData,
        xyB=(0, 0.5),
        coordsB=ax_zoom.transAxes,
        arrowstyle="->",
        color="#64748B",
        linewidth=1,
        linestyle="--",
        zorder=2,
        clip_on=False,
    ))

    ax.text(
        (xmin + xmax) / 2,
        (ymin + ymax) / 2,
        "Île-de-France\n(voir zoom)",
        ha="center",
        va="center",
        fontsize=8,
        color="#172B4D",
        bbox={
            "facecolor": "white",
            "edgecolor": "none",
            "alpha": 0.85,
        },
    )

    # Décaler certains noms pour éviter les chevauchements.
    decalages = {
        "01": (0, 18),
        "04": (0, 12),
        "37": (7, -6),
        "54": (50, 55),
        "59": (8, -7),
        "65": (0, -18),
        "69": (8, 8),
        "79": (-8, -9),
        "87": (2, -18),
        "90": (40, -15),
    }

    decalages_zoom = {
        "75": (0, -40),
        "92": (-45, 15),
        "93": (45, 28),
        "94": (50, 0),
    }

    # Afficher le nom et le pourcentage de chaque département.
    for axe, zone in ((ax, carte), (ax_zoom, ile_de_france)):
        for _, ligne in zone.iterrows():
            if axe is ax and ligne["region"] == "11":
                continue

            point = ligne.geometry.representative_point()
            part = ligne["part_fg_pct"]
            valeur = "ND" if pd.isna(part) else f"{part:.2f} %"
            nom = fill(ligne["nom"], width=15, break_long_words=False)
            etiquette = nom + "\n" + valeur.replace(".", ",")

            positions = decalages if axe is ax else decalages_zoom
            deplacement = positions.get(ligne["code_departement"], (0, 0))

            fleche = (
                {"arrowstyle": "-", "color": "#475569", "lw": 0.7}
                if deplacement != (0, 0) else None
            )

            texte = axe.annotate(
                etiquette,
                xy=(point.x, point.y),
                xytext=deplacement,
                textcoords="offset points",
                ha="center",
                va="center",
                fontsize=8 if axe is ax else 9,
                color="#172B4D",
                linespacing=1.15,
                arrowprops=fleche,
                annotation_clip=False,
            )
            texte.set_gid("departement-" + ligne["code_departement"])
            texte.set_path_effects([
                pe.withStroke(linewidth=2, foreground="white")
            ])

        axe.set_axis_off()

    ax.legend(
        handles=[
            Patch(
                facecolor="#D7DCE3",
                edgecolor="#8793A3",
                hatch="///",
                label="ND : aucune vente retenue",
            )
        ],
        loc="lower left",
        frameon=False,
        fontsize=10,
    )

    # Résumé calculé à partir des effectifs.
    total = int(tableau["nombre_ventes"].sum())
    part_totale = 100 * tableau["nombre_fg"].sum() / total
    effectif = f"{total:,}".replace(",", " ")
    part_texte = f"{part_totale:.2f}".replace(".", ",")

    fig.suptitle(titre, fontsize=18, y=0.975)
    fig.text(
        0.5,
        0.925,
        f"{effectif} ventes · {len(tableau)} départements · "
        f"Part F/G dans l'échantillon : {part_texte} %",
        ha="center",
        fontsize=12,
    )

    fig.text(
        0.87,
        0.42,
        "Le cadre en pointillés repère\nl'Île-de-France sur la carte.\n\n"
        "Chaque étiquette indique\nle département et sa part F/G.\n\n"
        "Même échelle de couleurs\npour la carte et le zoom.",
        ha="center",
        va="top",
        fontsize=11,
        color="#475569",
    )

    fig.text(
        0.07,
        0.035,
        "Ventes appariées à un DPE, hors ventes rapprochées. "
        "Cette part décrit les ventes retenues dans l'analyse.\n"
        "Elle ne mesure pas la part F/G de l'ensemble du parc de logements.\n"
        "Sources : DVF–DPE du projet ; contours data.gouv.fr 2025 (ODbL). "
        "Projection : Lambert-93.",
        fontsize=10,
        color="#475569",
    )

    return fig
