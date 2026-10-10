"""Stap 4a: teken die bottelnekgrafieke.

Gebruik:
    python groot_stap4a.py                          (gegenereerde toetsdata, 2000 nodusse)
    python groot_stap4a.py --nodusse 5000
    python groot_stap4a.py --csv nodusse.csv rande.csv     (die egte data, later)
    python groot_stap4a.py --uitgids grafieke
"""

import argparse
from pathlib import Path

from groot_data import genereer_toetsdata, laai_csv
from groot_grafieke import bottelnek_per_vloer, teken_sykant, teken_vloere, teken_wat_as, wat_as_reeks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nodusse", type=int, default=2000)
    ap.add_argument("--vloere", type=int, default=5)
    ap.add_argument("--saad", type=int, default=42)
    ap.add_argument("--csv", nargs=2, metavar=("NODUSSE", "RANDE"))
    ap.add_argument("--uitgids", default=".")
    args = ap.parse_args()

    graf = laai_csv(*args.csv) if args.csv else genereer_toetsdata(args.nodusse, args.vloere, args.saad)
    gids = Path(args.uitgids)
    gids.mkdir(parents=True, exist_ok=True)

    rye = bottelnek_per_vloer(graf)
    print(f"{'Vloer':<7}{'Mense':>7}{'Vloei/s':>9}{'Min tyd':>9}  Bottelnek")
    for r in rye:
        print(f"{r['vloer']:<7}{r['mense']:>7}{r['vloei']:>9g}{r['min_tyd_s']:>8.0f}s  "
              f"{len(r['bottelnekke'])} x {r['hoof_tipe'].lower()}")
    teken_vloere(rye, gids / "bottelnek_1_vloere.png")

    boonste = rye[0]            # Boonste vloer: al sy mense moet deur al die trappe.
    teken_sykant(graf, boonste, gids / "bottelnek_2_sykant.png")

    reeks = wat_as_reeks(graf, boonste["vloer"])
    print(f"\nWat as die trappe breër was (vloer {boonste['vloer']}):")
    for r in reeks:
        print(f"  x{r['faktor']:<5g} vloei {r['vloei']:>6g}/s   bottelnek: {', '.join(t.lower() for t in r['tipes'])}")
    teken_wat_as(reeks, boonste["vloer"], gids / "bottelnek_3_wat_as.png")
    print(f"\nGrafieke gestoor in {gids.resolve()}")


if __name__ == "__main__":
    main()
