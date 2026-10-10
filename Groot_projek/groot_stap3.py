"""Stap 3: lambda-vergelyking en parallel teenoor sekwensiële ontruimingsdekking.

Gebruik:
    python groot_stap3.py --vinnig                    (klein toets, 'n paar sekondes)
    python groot_stap3.py                             (volle lopie)
    python groot_stap3.py --net lambda                (net die lambda-deel)
    python groot_stap3.py --net parallel --werkers 1,2,4 --groottes 500,1000,2000
    python groot_stap3.py --dekking-groottes 2000     (net die dekking op die egte grootte)

Lees die uitvoer só:
  • 'aanroepe' en 'onbereikbaar' is tellings: dieselfde elke keer.
  • Tye wissel; die mediaan is die middelste herhaling.
  • versnelling = sekwensiële mediaan / parallelle mediaan. Onder 1.0x beteken
    parallel is stadiger (oorhoofse koste: prosesse, piekel, terugstuur).
  • opstart = die eerste lopie, met poelbegin en elke werker se grafieklaai. Main.py
    betaal dit net een keer, want die poel word hergebruik.
"""

import argparse
import json
import os

from groot_lambda import lambda_eksperiment
from groot_meet import STANDAARD_TYDGRENS_S, bou_grawe, loop_leer, omgewing
from groot_parallel import dekking_een, standaard_werkers


def lambda_lyn(ry):
    return (f"  {ry['eksperiment']:<30}{ry['variant']:<32} n={ry['n']:<8}"
            f"{ry['mediaan_s']:9.5f}s [{ry['min_s']:.5f}-{ry['maks_s']:.5f}] x{ry['herhalings']}")


def lambda_opsomming(rye):
    """By die grootste grootte: elke variant se tyd as veelvoud van die vinnigste in sy eksperiment."""
    n = max(r["n"] for r in rye)
    print(f"\n--- Lambda teenoor def teenoor inline (n={n}, verhouding teenoor vinnigste) ---")
    for eksperiment in dict.fromkeys(r["eksperiment"] for r in rye):
        lede = [r for r in rye if r["eksperiment"] == eksperiment and r["n"] == n]
        vinnigste = min(r["mediaan_s"] for r in lede)
        print(f"{eksperiment}:")
        for r in sorted(lede, key=lambda r: r["mediaan_s"]):
            print(f"    {r['variant']:<34}{r['mediaan_s']:9.5f}s  {r['mediaan_s'] / vinnigste:5.2f}x")


def dekking_lyne(ry):
    if ry["status"] != "ok":
        return [f"  n={ry['n']:<7} oorgeslaan (voorspel ~{ry['voorspel_s']:.0f}s, oor die tydgrens)"]
    s = ry["sekwensieel"]
    lyne = [f"  n={ry['n']:<7} {ry['rande']:,} rande, {ry['geblokkeer']} gesluit, "
            f"{ry['onbereikbaar']} onbereikbaar, grafieklaai {ry['grafiek_laai_s']:.2f}s",
            f"      {'sekwensieel':<34}{s['mediaan_s']:9.4f}s [{s['min_s']:.4f}-{s['maks_s']:.4f}] x{s['herhalings']}"]
    for w, pak in ry["parallel"].items():
        for naam, p in pak.items():
            lyne.append(f"      {w} werker(s), {naam:<22}{p['mediaan_s']:9.4f}s "
                        f"{p['versnelling']:5.2f}x   opstart {p['opstart_s']:.2f}s")
    return lyne


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--net", default="lambda,parallel")
    ap.add_argument("--vinnig", action="store_true")
    ap.add_argument("--lambda-groottes", default="10000,100000,500000")
    ap.add_argument("--groottes", "--dekking-groottes", dest="dekking_groottes", default="500,1000,2000",
                    help="Aantal nodusse vir die dekkingseksperiment.")
    ap.add_argument("--werkers", default=None, help="Kommageskeide werkertalle; verstek hang van die kerne af.")
    ap.add_argument("--sluit-deel", type=float, default=0.05, help="Deel van die nodusse wat gesluit word.")
    ap.add_argument("--herhalings", type=int, default=5)
    ap.add_argument("--tydgrens", type=float, default=STANDAARD_TYDGRENS_S)
    ap.add_argument("--saad", type=int, default=42)
    ap.add_argument("--uit", default="groot_resultate_stap3.json")
    args = ap.parse_args()

    eksperimente = set(args.net.split(","))
    lambda_groottes = [2000, 20000] if args.vinnig else [int(g) for g in args.lambda_groottes.split(",")]
    dekking_groottes = [200, 400] if args.vinnig else [int(g) for g in args.dekking_groottes.split(",")]
    werkers = [int(w) for w in args.werkers.split(",")] if args.werkers else standaard_werkers()
    herhalings = 2 if args.vinnig else args.herhalings

    instellings = {"lambda_groottes": lambda_groottes, "dekking_groottes": dekking_groottes,
                   "werkers": werkers, "sluit_deel": args.sluit_deel, "herhalings": herhalings,
                   "tydgrens_s": args.tydgrens, "saad": args.saad}
    resultate = {"omgewing": omgewing(instellings), "lambda": [], "dekking": []}
    print(f"Kerne beskikbaar: {os.cpu_count()}; werkertalle wat getoets word: {werkers}")

    if "lambda" in eksperimente:
        print("\n=== LAMBDA TEENOOR DEF TEENOOR INLINE ===")
        rye = lambda_eksperiment(lambda_groottes, herhalings, volg=lambda ry: print(lambda_lyn(ry), flush=True))
        resultate["lambda"] = rye
        lambda_opsomming(rye)

    if "parallel" in eksperimente:
        print("\n=== ONTRUIMINGSDEKKING: SEKWENSIEEL TEENOOR PARALLEL ===")
        grawe = bou_grawe(dekking_groottes, args.saad)
        rye = loop_leer(
            dekking_groottes,
            lambda n: dekking_een(grawe[n], werkers, args.sluit_deel, herhalings),
            args.tydgrens,
        )
        for ry in rye:
            for lyn in dekking_lyne(ry):
                print(lyn)
            resultate["dekking"].append({"eksperiment": "dekking", **ry})
        if (os.cpu_count() or 1) == 1:
            print("\nLET WEL: hierdie rekenaar het net een kern; parallel kan nie vinniger wees nie.")

    with open(args.uit, "w", encoding="utf-8") as leer:
        json.dump(resultate, leer, indent=2, ensure_ascii=False)
    print(f"\nResultate gestoor in {args.uit}")


if __name__ == "__main__":
    main()
