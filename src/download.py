"""Téléchargement des données brutes : DVF géolocalisées, DPE ADEME, base Insee.

Chaque fichier déjà présent est ignoré, ce qui permet de relancer après une coupure.
"""
from __future__ import annotations

import time

import pandas as pd
import requests

from . import config as C

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "projet-ensae-dpe-dvf"


def _get(url: str, params: dict | None = None, stream: bool = False, essais: int = 5):
    """GET avec reprises exponentielles (serveurs publics parfois instables)."""
    for i in range(essais):
        try:
            r = SESSION.get(url, params=params, stream=stream, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i == essais - 1:
                raise
            attente = 2 ** i
            print(f"  erreur {e!r}, nouvel essai dans {attente}s")
            time.sleep(attente)


def telecharger_dvf(dep: str, annees=C.ANNEES_DVF) -> list:
    chemins = []
    for annee in annees:
        dest = C.RAW_DVF / str(annee) / f"{dep}.csv.gz"
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            r = _get(C.URL_DVF.format(annee=annee, dep=dep), stream=True)
            if r is None:
                print(f"  DVF {annee} {dep} : indisponible")
                continue
            tmp = dest.with_suffix(".part")
            with open(tmp, "wb") as f:
                for bloc in r.iter_content(1 << 20):
                    f.write(bloc)
            tmp.rename(dest)
        chemins.append(dest)
    return chemins


def telecharger_dpe(dep: str, taille_page: int = 10_000):
    """DPE d'un département via l'API data-fair, pagination par curseur `next`."""
    dest = C.RAW_DPE / f"{dep}.parquet"
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    params = {
        "size": taille_page,
        "select": ",".join(C.COLONNES_DPE),
        "qs": f'code_departement_ban:"{dep}"',
    }
    r = _get(C.URL_DPE_API, params=params)
    page = r.json()
    total, lignes, url = page.get("total", 0), list(page["results"]), page.get("next")
    while url and page["results"]:
        page = _get(url).json()
        lignes.extend(page["results"])
        url = page.get("next")
        print(f"  DPE {dep} : {len(lignes):,}/{total:,}", end="\r")
    print()
    df = pd.DataFrame(lignes).reindex(columns=C.COLONNES_DPE)
    df.to_parquet(dest, index=False)
    return dest


def telecharger_insee():
    dest = C.RAW_INSEE / "comparateur.parquet"
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = _get(C.URL_INSEE_COMPARATEUR)
        dest.write_bytes(r.content)
    return dest
