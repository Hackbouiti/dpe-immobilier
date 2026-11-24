import numpy as np
import pandas as pd
import pytest

from src import chargement, ecarts


def creer_donnees_test():
    lignes = []

    # Groupe 1 : deux logements G à 1 000 €/m²,
    # un logement D à 2 000 €/m².
    for etiquette, prix, nombre in [
        ("G", 1000, 2),
        ("D", 2000, 1),
    ]:
        for _ in range(nombre):
            lignes.append({
                "code_commune": "35238",
                "type_bien": "appartement",
                "surface": 50,
                "periode_construction": "avant 1948",
                "trimestre": "2022T1",
                "etiquette_dpe": etiquette,
                "prix_m2": prix,
            })

    # Groupe 2 : un logement G et un logement D,
    # tous deux à 1 000 €/m².
    for etiquette in ["G", "D"]:
        lignes.append({
            "code_commune": "35238",
            "type_bien": "maison",
            "surface": 100,
            "periode_construction": "1948-1974",
            "trimestre": "2022T2",
            "etiquette_dpe": etiquette,
            "prix_m2": 1000,
        })

    return pd.DataFrame(lignes)


def test_ecart_comparable_pondere(monkeypatch):
    donnees = creer_donnees_test()

    # On neutralise les filtres du chargement pour isoler
    # le calcul statistique testé.
    monkeypatch.setattr(
        chargement, "preparer", lambda df: df
    )
    monkeypatch.setattr(
        chargement, "echantillon_analyse", lambda df: df
    )

    resultat = ecarts.calculer_ecarts(
        donnees,
        reference="D",
        min_effectif=1,
    )

    ligne_g = resultat.loc[
        resultat["etiquette"].eq("G")
    ].iloc[0]

    attendu = 100 * (
        np.exp((2 * np.log(1000 / 2000) + np.log(1000 / 1000)) / 3)
        - 1
    )

    assert ligne_g["ecart_comparable_pct"] == pytest.approx(attendu)
    assert ligne_g["n_cible_support"] == 3
    assert ligne_g["nombre_groupes_comparables"] == 2


def test_reference_invalide():
    with pytest.raises(ValueError):
        ecarts.calculer_ecarts(
            pd.DataFrame(),
            reference="Z",
        )


def test_min_effectif_invalide():
    with pytest.raises(ValueError):
        ecarts.calculer_ecarts(
            pd.DataFrame(),
            reference="D",
            min_effectif=0,
        )
