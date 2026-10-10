"""Stap 4c: teken die lambda-, parallel- en Kruskal-spanboomgrafieke.

Gebruik:
    python groot_stap4c.py
    python groot_stap4c.py --resultate groot_resultate_stap3.json --uitgids grafieke
    python groot_stap4c.py --csv nodusse.csv rande.csv        (spanboom vir die egte data)
"""

import argparse
from pathlib import Path

from groot_data import genereer_toetsdata, laai_csv
from groot_grafieke_stap3 import laai, teken_lambda, teken_parallel, teken_spanboom


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resultate", default="groot_resultate_stap3.json")
    ap.add_argument("--uitgids", default=".")
    ap.add_argument("--nodusse", type=int, default=2000)
    ap.add_argument("--vloere", type=int, default=5)
    ap.add_argument("--saad", type=int, default=42)
    ap.add_argument("--spanboom-vloer", type=int, default=0)
    ap.add_argument("--csv", nargs=2, metavar=("NODUSSE", "RANDE"))
    args = ap.parse_args()

    gids = Path(args.uitgids)
    gids.mkdir(parents=True, exist_ok=True)
    data = laai(args.resultate)
    kerne = data["omgewing"].get("kerne") or 1

    teken_lambda(data["lambda"], gids / "lambda_1_vergelyking.png")
    teken_parallel(data["dekking"], kerne, gids / "parallel_1_dekking.png")
    graf = laai_csv(*args.csv) if args.csv else genereer_toetsdata(args.nodusse, args.vloere, args.saad)
    teken_spanboom(graf, args.spanboom_vloer, gids / "kruskal_1_spanboom.png")
    for naam in ("lambda_1_vergelyking.png", "parallel_1_dekking.png", "kruskal_1_spanboom.png"):
        print(f"Gestoor: {gids / naam}")


if __name__ == "__main__":
    main()
