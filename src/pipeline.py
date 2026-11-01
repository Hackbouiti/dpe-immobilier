"""Pipeline complet, département par département.

Exemples :
    python -m src.pipeline --deps 75 13 48       # essai sur trois départements
    python -m src.pipeline                        # France métropolitaine hors Alsace-Moselle
    python -m src.pipeline --sans-telechargement  # retraiter les fichiers déjà présents
"""
from __future__ import annotations

import argparse
import time
import traceback

import pandas as pd

from . import config as C
from . import clean, download, match, territoires


def traiter_departement(dep: str, telecharger: bool = True) -> dict:
    t0 = time.time()
    if telecharger:
        chemins_dvf = download.telecharger_dvf(dep)
        chemin_dpe = download.telecharger_dpe(dep)
    else:
        chemins_dvf = [p for a in C.ANNEES_DVF if (p := C.RAW_DVF / str(a) / f"{dep}.csv.gz").exists()]
        chemin_dpe = C.RAW_DPE / f"{dep}.parquet"

    ventes = clean.nettoyer_dvf(clean.lire_dvf(chemins_dvf))
    dpe = clean.nettoyer_dpe(pd.read_parquet(chemin_dpe)) if chemin_dpe.exists() else pd.DataFrame()

    apparie, stats = match.apparier(ventes, dpe)
    communes = territoires.agreger_communes(ventes, dpe) if len(ventes) and len(dpe) else pd.DataFrame()

    for sous, df in (("ventes", apparie), ("communes", communes)):
        dest = C.PROCESSED / sous / f"{dep}.parquet"
        dest.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(dest, index=False)

    stats.update(departement=dep, statut="ok", duree_s=round(time.time() - t0, 1))
    return stats


def ecrire_journal(lignes: list[dict]):
    """Met à jour reports/journal_appariement.csv (une ligne par département)."""
    C.REPORTS.mkdir(parents=True, exist_ok=True)
    chemin = C.REPORTS / "journal_appariement.csv"
    nouveau = pd.DataFrame(lignes)
    if chemin.exists():
        ancien = pd.read_csv(chemin, dtype={"departement": str})
        nouveau = pd.concat([ancien[~ancien["departement"].isin(nouveau["departement"])], nouveau])
    debut = ["departement", "statut", "n_ventes", "n_dpe", "n_apparie", "taux_appariement"]
    # reindex : un département en erreur n'a pas les colonnes de comptage.
    nouveau = nouveau.reindex(columns=debut + [c for c in nouveau.columns if c not in debut])
    nouveau.sort_values("departement").to_csv(chemin, index=False)
    return chemin


def assembler():
    """Concatène les résultats départementaux en deux fichiers nationaux."""
    for sous in ("ventes", "communes"):
        fichiers = sorted((C.PROCESSED / sous).glob("*.parquet"))
        if fichiers:
            df = pd.concat([pd.read_parquet(f) for f in fichiers], ignore_index=True)
            df.to_parquet(C.PROCESSED / f"{sous}_france.parquet", index=False)
            print(f"{sous}_france.parquet : {len(df):,} lignes")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--deps", nargs="*", default=C.DEPARTEMENTS, help="codes département")
    p.add_argument("--sans-telechargement", action="store_true")
    p.add_argument("--insee", action="store_true", help="télécharger et mettre en forme la base Insee")
    args = p.parse_args()

    deps = [d.zfill(2) if d.isdigit() else d.upper() for d in args.deps]
    exclus = [d for d in deps if d in C.EXCLUS]
    if exclus:
        print(f"Ignorés (absents de DVF) : {exclus}")
    deps = [d for d in deps if d not in C.EXCLUS]

    journal = []
    for i, dep in enumerate(deps, 1):
        print(f"[{i}/{len(deps)}] département {dep}")
        try:
            s = traiter_departement(dep, telecharger=not args.sans_telechargement)
            print(f"  {s['n_ventes']:,} ventes, {s['n_dpe']:,} DPE, appariement {s['taux_appariement']:.1%}")
        except Exception as e:  # un département en échec ne bloque pas les autres
            traceback.print_exc()
            s = {"departement": dep, "statut": f"erreur: {e!r}"[:200]}
        journal.append(s)
        ecrire_journal(journal)

    assembler()

    if args.insee:
        large, dico = territoires.comparateur_large(download.telecharger_insee())
        large.to_parquet(C.PROCESSED / "insee_communes.parquet", index=False)
        dico.to_csv(C.REPORTS / "insee_dictionnaire.csv", index=False)
        print(f"insee_communes.parquet : {len(large):,} communes, {large.shape[1] - 1} indicateurs")


if __name__ == "__main__":
    main()
