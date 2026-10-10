"""Stap 2: tye en tellings vir sortering, Dijkstra/A* (met drie toue) en Kruskal op 'n groot datastel.

Gebruik:
    python groot_stap2.py                              (volle lopie, tot 10 000 nodusse)
    python groot_stap2.py --vinnig                     (klein toets, 'n paar sekondes)
    python groot_stap2.py --groottes 500,2000,8000     (eie grootte-leer)
    python groot_stap2.py --net sorteer,kruskal        (net sommige eksperimente)
    python groot_stap2.py --csv nodusse.csv rande.csv  (egte data; sorteer-leer loop tot die datagrootte)

Die resultate word ook na groot_resultate.json gestoor. Doen een voorbereidingslopie
daarvan voor die aanbieding, sodat jy 'n eerlike rugsteun het as die rekenaar in
die klas stadiger is.

Lees die uitvoer só:
  • Tellings (vergelykings, nodusse uitgebrei, touwerk) is elke keer presies dieselfde.
  • Tye wissel 'n bietjie; die mediaan is die middelste van die herhalings.
  • 'oorgeslaan' beteken die voorspelde tyd was oor die tydgrens: die metode is te stadig vir hierdie grootte.
"""

import argparse
import json
from collections import defaultdict

from groot_data import laai_csv
from groot_meet import (
    STANDAARD_TYDGRENS_S, bou_grawe, kruskal_eksperiment, omgewing, roete_eksperiment,
    sorteer_eksperiment,
)


def lyn(ry):
    """Een leesbare reël vir 'n gemete (of oorgeslane) ry; gedruk terwyl die lopie vorder."""
    kop = f"{ry['algoritme']:<34}"
    if ry.get("tou"):
        kop = f"{ry['algoritme']:<9}{ry['tou']:<30}"
    if ry.get("patroon"):
        kop += f" {ry['patroon']:<15}"
    if ry["status"] != "ok":
        return f"  {kop} n={ry['n']:<7} oorgeslaan (voorspel ~{ry['voorspel_s']:.0f}s, oor die tydgrens)"
    tyd = f"{ry['mediaan_s']:9.4f}s [{ry['min_s']:.4f}-{ry['maks_s']:.4f}] x{ry['herhalings']}"
    ekstra = ""
    if ry.get("vergelykings") is not None:
        ekstra = f"  vergelykings {ry['vergelykings']:,}"
    if "besoek_totaal" in ry:
        ekstra = f"  uitgebrei {ry['besoek_totaal']:,}  touwerk {ry['tou_werk_totaal']:,}"
    if "kante" in ry:
        ekstra = f"  sortering {ry['sorteer_mediaan_s']:.4f}s van die totaal  ({ry['kante']:,} rande)"
    return f"  {kop} n={ry['n']:<7} {tyd}{ekstra}"


def opsomming(titel, rye, groepeer):
    """Wys by elke groep die grootste grootte wat almal voltooi het, met 'n verhouding teenoor die vinnigste."""
    groepe = defaultdict(list)
    for ry in rye:
        groepe[groepeer(ry)].append(ry)
    print(f"\n--- {titel} ---")
    for sleutel, lede in groepe.items():
        per_metode = defaultdict(dict)
        for ry in lede:
            per_metode[ry["algoritme"] + (" / " + ry["tou"] if ry.get("tou") else "")][ry["n"]] = ry
        gedeelde = set.intersection(*[{n for n, r in m.items() if r["status"] == "ok"} for m in per_metode.values()])
        if not gedeelde:
            continue
        n = max(gedeelde)
        vinnigste = min(m[n]["mediaan_s"] for m in per_metode.values())
        print(f"{sleutel} (n={n}):")
        for naam, m in sorted(per_metode.items(), key=lambda kv: kv[1][n]["mediaan_s"]):
            oorgeslaan = sorted(k for k, r in m.items() if r["status"] != "ok")
            verhouding = m[n]["mediaan_s"] / vinnigste if vinnigste else 1.0
            nota = f"  (oorgeslaan vanaf n={oorgeslaan[0]})" if oorgeslaan else ""
            print(f"    {naam:<48} {m[n]['mediaan_s']:9.4f}s  {verhouding:7.1f}x{nota}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groottes", default="500,1000,2000,5000,10000", help="Kommageskeide aantal nodusse.")
    ap.add_argument("--vinnig", action="store_true", help="Klein, vinnige toetslopie.")
    ap.add_argument("--herhalings", type=int, default=5)
    ap.add_argument("--tydgrens", type=float, default=STANDAARD_TYDGRENS_S, help="Sekondes; stadiger voorspellings word oorgeslaan.")
    ap.add_argument("--pare", type=int, default=20, help="Aantal roetepare per meting.")
    ap.add_argument("--saad", type=int, default=42)
    ap.add_argument("--net", default="sorteer,roete,kruskal")
    ap.add_argument("--csv", nargs=2, metavar=("NODUSSE", "RANDE"))
    ap.add_argument("--uit", default="groot_resultate.json")
    args = ap.parse_args()

    groottes = [250, 500, 1000, 2000] if args.vinnig else [int(g) for g in args.groottes.split(",")]
    eksperimente = set(args.net.split(","))

    if args.csv:
        graf = laai_csv(*args.csv)
        volledig = len(graf.nodes)
        grawe = {volledig: graf}
        sorteer_groottes = [g for g in groottes if g < volledig] + [volledig]
        nodusse = list(graf.nodes.values())
    else:
        print(f"Bou grafieke vir n = {groottes} ...")
        grawe = bou_grawe(groottes, args.saad)
        sorteer_groottes = groottes
        nodusse = list(grawe[max(groottes)].nodes.values())

    instellings = {"groottes": sorted(grawe), "sorteer_groottes": sorteer_groottes, "herhalings": args.herhalings,
                   "tydgrens_s": args.tydgrens, "pare": args.pare, "saad": args.saad, "csv": bool(args.csv)}
    resultate = {"omgewing": omgewing(instellings), "rye": []}

    def volg(ry):
        print(lyn(ry), flush=True)

    if "sorteer" in eksperimente:
        print("\n=== SORTERING (nodusse op etiket) ===")
        rye = sorteer_eksperiment(nodusse, sorteer_groottes, args.tydgrens, args.herhalings, volg=volg)
        resultate["rye"] += rye
        opsomming("Sortering", rye, lambda ry: f"patroon: {ry['patroon']}")
    if "roete" in eksperimente:
        print(f"\n=== DIJKSTRA EN A* MET VERSKILLENDE TOUE ({args.pare} pare per meting) ===")
        rye = roete_eksperiment(grawe, args.pare, args.tydgrens, args.herhalings, args.saad, volg=volg)
        resultate["rye"] += rye
        opsomming("Roetes", rye, lambda ry: "alle algoritmes en toue")
    if "kruskal" in eksperimente:
        print("\n=== KRUSKAL MET VERSKILLENDE SORTEERMETODES ===")
        rye = kruskal_eksperiment(grawe, args.tydgrens, args.herhalings, volg=volg)
        resultate["rye"] += rye
        opsomming("Kruskal", rye, lambda ry: "Kruskal")

    with open(args.uit, "w", encoding="utf-8") as leer:
        json.dump(resultate, leer, indent=2, ensure_ascii=False)
    print(f"\nResultate gestoor in {args.uit}")


if __name__ == "__main__":
    main()
