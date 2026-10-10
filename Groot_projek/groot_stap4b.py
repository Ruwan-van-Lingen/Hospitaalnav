"""Stap 4b: teken die tydgrafieke uit groot_resultate.json (van groot_stap2.py).

Gebruik:
    python groot_stap4b.py
    python groot_stap4b.py --resultate groot_resultate.json --uitgids grafieke
"""

import argparse
from pathlib import Path

from groot_tydgrafieke import laai, teken_kruskal, teken_roetes, teken_sorteer, teken_vergelykings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resultate", default="groot_resultate.json")
    ap.add_argument("--uitgids", default=".")
    args = ap.parse_args()

    rye = laai(args.resultate)
    gids = Path(args.uitgids)
    gids.mkdir(parents=True, exist_ok=True)
    for naam, teken in (("tyd_1_sorteer.png", teken_sorteer), ("tyd_2_vergelykings.png", teken_vergelykings),
                        ("tyd_3_roetes.png", teken_roetes), ("tyd_4_kruskal.png", teken_kruskal)):
        teken(rye, gids / naam)
        print(f"Gestoor: {gids / naam}")


if __name__ == "__main__":
    main()
