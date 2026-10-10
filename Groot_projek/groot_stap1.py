"""Stap 1: voer die kernalgoritmes op die groot datastel uit en wys tellings en bottelnekke.

Gebruik:
    python groot_stap1.py                       (gegenereerde toetsdata, 2000 nodusse)
    python groot_stap1.py --nodusse 5000        (ander grootte)
    python groot_stap1.py --csv nodusse.csv rande.csv     (die egte data, later)

Die tellings (nodusse uitgebrei, vloei, bottelnekke, spanboomgewig) hang net van
die data af en is dus elke keer dieselfde. Tydmetings kom eers in stap 2.
"""

import argparse
import math
import random
import statistics
from collections import Counter

from groot_algoritmes import (
    SORTEER_METODES, astar, bereken_ontruimingskaart, dijkstra, kruskal,
    maks_vloei_na_uitgange,
)
from groot_data import genereer_toetsdata, laai_csv


def beskryf_rand(graf, van, na):
    """Gee 'n mensleesbare beskrywing van 'n bottelnekrand: waar dit is en watter soort verbinding."""
    rand = next(r for r in graf.adjacency[van] if r.na_node == na)
    v1, v2 = graf.nodes[van]["vloer"], graf.nodes[na]["vloer"]
    plek = f"vloer {v1}" if v1 == v2 else f"tussen vloer {v1} en {v2}"
    return f"{van} -> {na}  ({rand.rand_tipe}, {plek}, kapasiteit {rand.kapasiteit:g}/s)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nodusse", type=int, default=2000, help="Aantal nodusse vir die toetsdata.")
    ap.add_argument("--vloere", type=int, default=5)
    ap.add_argument("--saad", type=int, default=42, help="Dieselfde saad = dieselfde grafiek.")
    ap.add_argument("--csv", nargs=2, metavar=("NODUSSE", "RANDE"), help="Laai egte data in plaas van toetsdata.")
    args = ap.parse_args()

    graf = laai_csv(*args.csv) if args.csv else genereer_toetsdata(args.nodusse, args.vloere, args.saad)
    rande_per_tipe = Counter(r[2] for r in graf.rande_lys)
    print(f"Grafiek: {len(graf.nodes)} nodusse, {len(graf.rande_lys)} rande {dict(rande_per_tipe)}")
    print(f"Nooduitgange: {len(graf.nooduitgange())}\n")

    # --- 1. A* teenoor Dijkstra: dieselfde tyd, verskillende werk ---
    rng = random.Random(7)
    ids = list(graf.nodes)
    dijk = ster = 0
    pare = 0
    pogings = 0
    while len(ids) >= 2 and pare < 100 and pogings < 5000:
        pogings += 1
        a, b = rng.sample(ids, 2)
        d, s = dijkstra(graf, a, b), astar(graf, a, b)
        if d is None:
            continue
        assert math.isclose(d.tyd_s, s.tyd_s, rel_tol=1e-9), "A* en Dijkstra moet dieselfde tyd vind"
        dijk += d.besoek_telling
        ster += s.besoek_telling
        pare += 1
    if pare:
        print(f"Roetes ({pare} ewekansige pare): gemiddeld nodusse uitgebrei")
        print(f"  Dijkstra {dijk / pare:8.1f}")
        print(f"  A*       {ster / pare:8.1f}   ({ster / dijk:.0%} van Dijkstra se werk)\n")
    else:
        print("Roetes: geen bereikbare pare gevind nie.\n")

    # --- 2. Ontruiming: een deurloop vir alle nodusse ---
    kaart = bereken_ontruimingskaart(graf)
    tye = sorted(kaart.tyd_s.values())
    if tye:
        print(f"Ontruiming: {len(tye)} van {len(graf.nodes)} nodusse bereikbaar; "
              f"mediaan {statistics.median(tye):.0f}s, langste {tye[-1]:.0f}s\n")
    else:
        print("Ontruiming: geen bereikbare nooduitgang nie.\n")

    # --- 3. Kruskal: dieselfde spanboom, verskillende sorteerwerk ---
    kante = graf.ongerigte_kante()
    print(f"Kruskal ({len(kante)} rande):")
    for naam, metode in SORTEER_METODES.items():
        u = kruskal(graf.nodes, kante, metode)
        print(f"  {naam:30s} gewig {u.totale_gewig:10.1f}  komponente {u.aantal_komponente}")
    print()

    # --- 4. Vloei en bottelnekke: ontruim die boonste vloer ---
    bo = max(d["vloer"] for d in graf.nodes.values())
    bronne = [n for n, d in graf.nodes.items() if d["vloer"] == bo]
    vloei = maks_vloei_na_uitgange(graf, bronne)
    if vloei is None or vloei.maks_vloei == 0:
        print(f"Maksimum vloei as vloer {bo} ontruim: geen positiewe deurvloei na 'n uitgang nie.")
        return
    print(f"Maksimum vloei as vloer {bo} ({len(bronne)} nodusse) ontruim: {vloei.maks_vloei:g} persone/s")
    print(f"Bottelnekke (min-snit), kapasiteite tel op tot {sum(k for _, _, k in vloei.bottelnekke):g}:")
    for van, na, _ in vloei.bottelnekke:
        print("  ", beskryf_rand(graf, van, na))
    print(f"Ter vergelyking: {len(bronne)} mense moet deur {vloei.maks_vloei:g}/s, "
          f"dus ten minste {len(bronne) / vloei.maks_vloei:.0f}s as almal een per nodus is.")


if __name__ == "__main__":
    main()
