"""Tests sur des données synthétiques au format des fichiers réels (DVF géolocalisées, API ADEME)."""
import numpy as np
import pandas as pd
import pytest

from src import chargement, clean, config as C, match, pipeline

COLS_DVF = ["id_mutation", "date_mutation", "numero_disposition", "nature_mutation", "valeur_fonciere",
            "adresse_numero", "adresse_suffixe", "adresse_code_voie", "adresse_nom_voie", "code_postal",
            "code_commune", "nom_commune", "code_departement", "id_parcelle",
            *[f"lot{i}_{c}" for i in range(1, 6) for c in ("numero", "surface_carrez")],  # format réel Etalab
            "nombre_lots", "code_type_local", "type_local", "surface_reelle_bati",
            "nombre_pieces_principales", "code_nature_culture", "nature_culture",
            "surface_terrain", "longitude", "latitude"]


def ligne(mut, date, prix, num, voie, typ, surf, carrez=None, culture=None, terrain=None,
          parcelle="75101000AB0001", nature="Vente", suffixe=None, lot="1"):
    libelles = {1: "Maison", 2: "Appartement", 3: "Dépendance", 4: "Local industriel. commercial ou assimilé"}
    r = dict.fromkeys(COLS_DVF)
    r.update(id_mutation=mut, date_mutation=date, numero_disposition=1, nature_mutation=nature,
             valeur_fonciere=prix, adresse_numero=num, adresse_suffixe=suffixe, adresse_nom_voie=voie,
             code_commune="75101", code_departement="75", id_parcelle=parcelle,
             code_type_local=typ, type_local=libelles.get(typ), surface_reelle_bati=surf,
             lot1_numero=lot, lot1_surface_carrez=carrez, nombre_pieces_principales=3,
             code_nature_culture=culture, surface_terrain=terrain, longitude=2.34, latitude=48.86)
    return r


@pytest.fixture
def dvf_brut():
    L = [
        # M1 : appartement + cave -> gardé, Carrez utilisée
        ligne("M1", "2023-05-10", 500_000, 12, "AV DU GAL DE GAULLE", 2, 52, carrez=50.0),
        ligne("M1", "2023-05-10", 500_000, 12, "AV DU GAL DE GAULLE", 3, None, lot="12"),
        # M2 : maison répétée sur deux natures de culture -> une seule vente
        ligne("M2", "2024-02-01", 300_000, 5, "CHE DES VIGNES", 1, 100, culture="S", terrain=400, parcelle="P2"),
        ligne("M2", "2024-02-01", 300_000, 5, "CHE DES VIGNES", 1, 100, culture="J", terrain=600, parcelle="P2"),
        # M3 : deux appartements -> écartée
        ligne("M3", "2023-03-01", 800_000, 7, "RUE DE LA PAIX", 2, 40, carrez=40.0, lot="1"),
        ligne("M3", "2023-03-01", 800_000, 7, "RUE DE LA PAIX", 2, 45, carrez=45.0, lot="2"),
        # M4 : appartement + local commercial -> écartée
        ligne("M4", "2023-03-01", 900_000, 9, "RUE DE LA PAIX", 2, 60, carrez=60.0),
        ligne("M4", "2023-03-01", 900_000, 9, "RUE DE LA PAIX", 4, 80, lot="3"),
        # M5 : échange -> écartée
        ligne("M5", "2023-03-01", 400_000, 3, "RUE DE LA PAIX", 2, 40, nature="Echange"),
        # M6 : appartement au 4 bis, sans DPE dans la base
        ligne("M6", "2025-01-15", 350_000, 4, "BD SAINT MICHEL", 2, 35, carrez=35.0, suffixe="B"),
    ]
    return pd.DataFrame(L, columns=COLS_DVF)


@pytest.fixture
def dpe_brut():
    base = dict(version_dpe=2.4, methode_application_dpe="dpe appartement individuel",
                etiquette_ges="C", conso_5_usages_par_m2_ep=200.0, emission_ges_5_usages_par_m2=20.0,
                periode_construction="1948-1974", annee_construction=None, numero_etage_appartement=2,
                zone_climatique="H1a", type_energie_principale_chauffage="Gaz naturel",
                code_postal_ban="75001", code_insee_ban="75101", code_departement_ban="75",
                score_ban=0.95, id_rnb=None, coordonnee_cartographique_x_ban=651000.0,
                coordonnee_cartographique_y_ban=6862000.0, numero_dpe_remplace=None)
    L = [
        # Pour M1 : bon candidat (surface 50.5, avant la vente)
        dict(numero_dpe="D1", date_etablissement_dpe="2023-01-20", etiquette_dpe="D", type_batiment="appartement",
             surface_habitable_logement=50.5, identifiant_ban="75101_x_00012",
             numero_voie_ban="12", nom_rue_ban="Avenue du Général de Gaulle"),
        # Pour M1 : même adresse, surface incompatible (autre logement de l'immeuble)
        dict(numero_dpe="D2", date_etablissement_dpe="2023-02-01", etiquette_dpe="B", type_batiment="appartement",
             surface_habitable_logement=80.0, identifiant_ban="75101_x_00012",
             numero_voie_ban="12", nom_rue_ban="Avenue du Général de Gaulle"),
        # Pour M1 : bonne surface mais établi après la vente
        dict(numero_dpe="D3", date_etablissement_dpe="2023-09-01", etiquette_dpe="C", type_batiment="appartement",
             surface_habitable_logement=50.0, identifiant_ban="75101_x_00012",
             numero_voie_ban="12", nom_rue_ban="Avenue du Général de Gaulle"),
        # Pour M2 : DPE initial remplacé par D5 -> D4 doit disparaître
        dict(numero_dpe="D4", date_etablissement_dpe="2023-06-01", etiquette_dpe="G", type_batiment="maison",
             surface_habitable_logement=92.0, identifiant_ban="75101_y_00005",
             numero_voie_ban="5", nom_rue_ban="Chemin des Vignes"),
        dict(numero_dpe="D5", date_etablissement_dpe="2023-07-01", etiquette_dpe="F", type_batiment="maison",
             surface_habitable_logement=92.0, identifiant_ban="75101_y_00005",
             numero_voie_ban="5", nom_rue_ban="Chemin des Vignes", numero_dpe_remplace="D4"),
        # DPE d'immeuble collectif -> exclu
        dict(numero_dpe="D6", date_etablissement_dpe="2023-07-01", etiquette_dpe="E", type_batiment="immeuble",
             surface_habitable_logement=900.0, identifiant_ban="75101_z_00007",
             numero_voie_ban="7", nom_rue_ban="Rue de la Paix"),
    ]
    return pd.DataFrame([{**base, **r} for r in L]).reindex(columns=C.COLONNES_DPE)


@pytest.fixture(autouse=True)
def sans_ecretage(monkeypatch):
    monkeypatch.setattr(C, "QUANTILES_PRIX_M2", (0.0, 1.0))


def test_normalisation_adresse():
    assert clean.normaliser_voie("AV DU GAL DE GAULLE") == clean.normaliser_voie("Avenue du Général de Gaulle")
    assert clean.normaliser_voie("CHE DES VIGNES") == clean.normaliser_voie("Chemin des Vignes")
    assert clean.normaliser_voie("BD ST MICHEL") == clean.normaliser_voie("Boulevard Saint-Michel")
    assert clean.normaliser_numero("12bis") == clean.normaliser_numero(12.0, "B") == "12B"
    assert clean.normaliser_numero("4 ter") == "4T"
    assert clean.normaliser_numero(None) == ""


def test_nettoyage_dvf(dvf_brut):
    v = clean.nettoyer_dvf(dvf_brut).set_index("id_mutation")
    assert sorted(v.index) == ["M1", "M2", "M6"]
    assert v.loc["M1", "surface"] == 50.0 and v.loc["M1", "n_dependance"] == 1
    assert v.loc["M2", "type_bien"] == "maison" and v.loc["M2", "surface_terrain"] == 1000
    assert v.loc["M2", "prix_m2"] == pytest.approx(3000)
    assert v.loc["M6", "numero_norm"] == "4B"


def test_nettoyage_dpe(dpe_brut):
    d = clean.nettoyer_dpe(dpe_brut)
    assert set(d["numero_dpe"]) == {"D1", "D2", "D3", "D5"}


def test_appariement(dvf_brut, dpe_brut):
    out, s = match.apparier(clean.nettoyer_dvf(dvf_brut), clean.nettoyer_dpe(dpe_brut))
    out = out.set_index("id_mutation")
    assert out.loc["M1", "numero_dpe"] == "D1" and out.loc["M1", "etiquette_dpe"] == "D"
    assert out.loc["M2", "numero_dpe"] == "D5"          # pas le DPE remplacé
    assert not out.loc["M6", "apparie"]
    assert s["n_apparie"] == 2 and s["taux_appariement"] == pytest.approx(2 / 3, abs=1e-3)
    assert not out.loc["M1", "ambigu"]


def test_ambiguite(dvf_brut, dpe_brut):
    autre = dpe_brut.iloc[[0]].assign(numero_dpe="D7", etiquette_dpe="A", surface_habitable_logement=50.2)
    out, _ = match.apparier(clean.nettoyer_dvf(dvf_brut), clean.nettoyer_dpe(pd.concat([dpe_brut, autre])))
    m1 = out.set_index("id_mutation").loc["M1"]
    assert m1["numero_dpe"] == "D7" and m1["ambigu"] and m1["n_candidats"] == 2


def test_pipeline_bout_en_bout(tmp_path, monkeypatch, dvf_brut, dpe_brut):
    for nom in ("RAW_DVF", "RAW_DPE", "PROCESSED", "REPORTS"):
        monkeypatch.setattr(C, nom, tmp_path / nom.lower())
    for annee in C.ANNEES_DVF:
        sous = dvf_brut[dvf_brut["date_mutation"].str.startswith(str(annee))]
        p = C.RAW_DVF / str(annee) / "75.csv.gz"
        p.parent.mkdir(parents=True)
        sous.to_csv(p, index=False)
    C.RAW_DPE.mkdir(parents=True)
    dpe_brut.to_parquet(C.RAW_DPE / "75.parquet")

    s = pipeline.traiter_departement("75", telecharger=False)
    journal = pd.read_csv(pipeline.ecrire_journal([s]), dtype={"departement": str})
    pipeline.assembler()

    assert journal.loc[0, "departement"] == "75" and journal.loc[0, "n_apparie"] == 2
    ventes = pd.read_parquet(C.PROCESSED / "ventes_france.parquet")
    assert len(ventes) == 3 and ventes["apparie"].sum() == 2
    communes = pd.read_parquet(C.PROCESSED / "communes_france.parquet")
    assert {"prix_m2_median", "part_FG"} <= set(communes.columns)


def test_journal_departement_en_erreur(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "REPORTS", tmp_path)
    ok = {"departement": "75", "statut": "ok", "n_ventes": 3, "n_dpe": 4, "n_apparie": 2, "taux_appariement": 0.67}
    ko = {"departement": "13", "statut": "erreur: KeyError('x')"}
    j = pd.read_csv(pipeline.ecrire_journal([ok, ko]), dtype={"departement": str}).set_index("departement")
    assert j.loc["13", "statut"].startswith("erreur") and pd.isna(j.loc["13", "n_ventes"])
    assert j.loc["75", "n_apparie"] == 2


def test_colonne_dvf_manquante_message_clair(dvf_brut):
    with pytest.raises(KeyError, match="Colonnes DVF manquantes"):
        clean.nettoyer_dvf(dvf_brut.drop(columns="valeur_fonciere"))


def test_lambert93_reference():
    # Points de référence calculés avec pyproj (EPSG:4326 -> EPSG:2154)
    pts = [((2.3522, 48.8566), (652469.02, 6862035.26)),
           ((-0.5792, 44.8378), (417241.54, 6421813.35)),
           ((3.4997, 44.5181), (739714.51, 6380018.27)),
           ((9.4500, 42.7000), (1228546.05, 6199420.64))]
    for (lon, lat), (x, y) in pts:
        xc, yc = match.lambert93(lon, lat)
        assert abs(xc - x) < 0.05 and abs(yc - y) < 0.05


def test_un_dpe_pour_un_seul_logement(dvf_brut, dpe_brut):
    # Deuxième vente d'un appartement de surface voisine dans le même immeuble
    # (52,5 m², compatible avec D1 à 10 % près mais moins proche que M1) :
    # elle ne doit pas recevoir le DPE D1 déjà attribué à M1.
    bis = dvf_brut[dvf_brut["id_mutation"] == "M1"].assign(
        id_mutation="M7", date_mutation="2023-06-20", valeur_fonciere=510_000)
    bis["lot1_surface_carrez"] = bis["lot1_surface_carrez"].where(bis["code_type_local"] != 2, 52.5)
    col_lot = "lot1_numero" if "lot1_numero" in bis.columns else "lot_1_numero"
    bis[col_lot] = bis[col_lot].where(bis["code_type_local"] != 2, "7")   # autre appartement
    out, _ = match.apparier(clean.nettoyer_dvf(pd.concat([dvf_brut, bis])), clean.nettoyer_dpe(dpe_brut))
    out = out.set_index("id_mutation")
    assert out.loc["M1", "numero_dpe"] == "D1"
    assert not out.loc["M7", "apparie"]
    assert out.loc[out["apparie"], "numero_dpe"].is_unique


def test_revente_meme_logement_partage_le_dpe(dvf_brut, dpe_brut):
    # Le même appartement (même parcelle, même lot) revendu quelques mois plus
    # tard, avant le DPE suivant (D3) : les deux ventes reçoivent D1.
    bis = dvf_brut[dvf_brut["id_mutation"] == "M1"].assign(
        id_mutation="M8", date_mutation="2023-08-15", valeur_fonciere=520_000)
    out, s = match.apparier(clean.nettoyer_dvf(pd.concat([dvf_brut, bis])), clean.nettoyer_dpe(dpe_brut))
    out = out.set_index("id_mutation")
    assert out.loc["M1", "numero_dpe"] == "D1"
    assert out.loc["M8", "numero_dpe"] == "D1"
    assert s["n_ventes_dpe_partage"] == 2
    assert not out.loc["M1", "vente_rapprochee"] and not out.loc["M8", "vente_rapprochee"]


def test_ventes_rapprochees_signalees(dvf_brut):
    # Le même appartement cédé deux fois à cinq jours d'écart : cession de droits partiels.
    bis = dvf_brut[dvf_brut["id_mutation"] == "M1"].assign(
        id_mutation="M9", date_mutation="2023-05-15", valeur_fonciere=250_000)
    v = clean.nettoyer_dvf(pd.concat([dvf_brut, bis])).set_index("id_mutation")
    assert v.loc["M1", "vente_rapprochee"] and v.loc["M9", "vente_rapprochee"]
    assert not v.loc["M2", "vente_rapprochee"]


def test_repli_spatial(dvf_brut, dpe_brut):
    # M6 (4 bis bd Saint-Michel) n'a pas de DPE à son adresse. On ajoute un DPE de même
    # surface, nommé autrement côté BAN, à 10 m de la parcelle : apparié par proximité.
    x, y = match.lambert93(2.34, 48.86)
    proche = dpe_brut.iloc[[0]].assign(
        numero_dpe="D8", date_etablissement_dpe="2024-11-01", surface_habitable_logement=35.5,
        numero_voie_ban="1", nom_rue_ban="Place Saint-Michel", etiquette_dpe="E",
        coordonnee_cartographique_x_ban=x + 6, coordonnee_cartographique_y_ban=y + 8)
    loin = proche.assign(numero_dpe="D9", coordonnee_cartographique_x_ban=x + 300)
    out, s = match.apparier(clean.nettoyer_dvf(dvf_brut),
                            clean.nettoyer_dpe(pd.concat([dpe_brut, proche, loin])))
    m6 = out.set_index("id_mutation").loc["M6"]
    assert m6["numero_dpe"] == "D8" and m6["methode_appariement"] == "spatial"
    assert m6["distance_m"] == pytest.approx(10, abs=0.01)
    assert s["n_apparie_spatial"] == 1 and s["n_apparie_adresse"] == 2


def test_perimetre():
    assert len(C.DEPARTEMENTS) == 93
    assert not {"57", "67", "68", "20"} & set(C.DEPARTEMENTS) and {"2A", "2B"} <= set(C.DEPARTEMENTS)


def test_echantillon_analyse():
    v = chargement.preparer(pd.DataFrame({
        "date_mutation": pd.to_datetime(["2022-03-01", "2023-07-15", "2024-01-02", "2025-11-30"]),
        "apparie": [True, True, False, True],
        "vente_rapprochee": [False, True, False, None],
        "ambigu": [False, False, None, True],
        "methode_appariement": ["adresse", "adresse", None, "spatial"],
        "etiquette_dpe": ["D", "G", None, "A"],
    }))
    assert list(v["trimestre"]) == ["2022Q1", "2023Q3", "2024Q1", "2025Q4"]
    ech = chargement.echantillon_analyse(v)
    assert len(ech) == 2                       # non appariée et rapprochée écartées
    assert len(chargement.appariement_strict(ech)) == 1   # la vente ambiguë et spatiale part
