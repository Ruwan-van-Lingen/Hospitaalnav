"""Stap 4b: tydgrafieke vir sortering, Dijkstra/A* en Kruskal.

Hierdie lêer lees die JSON wat groot_stap2.py stoor (groot_resultate.json) en
teken Matplotlib-grafieke ('Agg', geen skerm nodig). Dit meet self niks nie:
doen 'n nuwe lopie met groot_stap2.py en teken weer om met jou eie syfers.

Grafieke
--------
  tyd_1_sorteer.png      - sorteertyd teenoor n, een paneel per invoerpatroon
  tyd_2_vergelykings.png - presiese aantal vergelykings teenoor n (met n log n en n² as verwysing)
  tyd_3_roetes.png       - Dijkstra/A*: tyd, nodusse uitgebrei en tou-werk
  tyd_4_kruskal.png      - Kruskal: totale tyd en watter deel daarvan sortering is

Beide asse is logaritmies, sodat 'n kwadratiese kurwe steiler as 'n n log n-kurwe
lyk en 'n gaping van 1000x steeds leesbaar is. Die band om 'n lyn is min tot maks.
'x' op 'n lyn is 'n grootte wat oorgeslaan is omdat dit te stadig sou wees.
"""

import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import math

import matplotlib.pyplot as plt

SORTEER_KLEURE = {"Invoegsortering": "#D94B4B", "Saamsmeltsortering": "#1E6FA8",
                  "Python sorted() (verwysing)": "#7C8B99"}
TOU_KLEURE = {"Binêre hoop (heapq)": "#1E6FA8", "Woordeboek + min()-skandering": "#D94B4B",
              "Gesorteerde lys (bisect)": "#2E8B57"}
STYLE = {"Dijkstra": "--", "A*": "-"}


def laai(pad):
    """Lees die JSON van groot_stap2.py; gee die lys rye."""
    with open(pad, encoding="utf-8") as leer:
        return json.load(leer)["rye"]


def _vereis(rye, eksperiment):
    """Gee die rye van een eksperiment, of gooi 'n duidelike fout as die JSON dit nie bevat nie."""
    uit = [r for r in rye if r["eksperiment"] == eksperiment]
    if not uit:
        raise ValueError(f"Geen '{eksperiment}'-resultate in die lêer nie; loop groot_stap2.py eers daarvoor.")
    return uit


def _reekse(rye, sleutel):
    """Groepeer rye volgens sleutel(ry), elk gesorteer op n."""
    groepe = defaultdict(list)
    for ry in rye:
        groepe[sleutel(ry)].append(ry)
    return {k: sorted(v, key=lambda r: r["n"]) for k, v in groepe.items()}


def _teken_lyn(ax, reeks, kleur, etiket, lyn="-", veld="mediaan_s", band=True):
    """Teken die gemete punte (lyn + min/maks-band) en merk oorgeslane groottes met 'x'."""
    ok = [r for r in reeks if r["status"] == "ok"]
    ax.plot([r["n"] for r in ok], [max(r[veld], 1e-7) for r in ok], lyn, color=kleur, marker="o",
            markersize=4, label=etiket)
    if band and veld == "mediaan_s":
        ax.fill_between([r["n"] for r in ok], [max(r["min_s"], 1e-7) for r in ok],
                        [max(r["maks_s"], 1e-7) for r in ok], color=kleur, alpha=0.2, linewidth=0)
    oor = [r for r in reeks if r["status"] != "ok"]
    if oor:
        ax.scatter([r["n"] for r in oor], [r["voorspel_s"] for r in oor], marker="x", color=kleur)


def _as(ax, titel, y="Mediaan tyd (s)"):
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("n (nodusse of items)")
    ax.set_ylabel(y)
    ax.set_title(titel, fontsize=10)
    ax.grid(True, which="both", alpha=0.25)


def teken_sorteer(rye, uit_pad):
    """Grafiek 1: sorteertyd per patroon."""
    rye = _vereis(rye, "sortering")
    reekse = _reekse(rye, lambda r: (r["patroon"], r["algoritme"]))
    patrone = list(dict.fromkeys(r["patroon"] for r in rye))
    fig, axes = plt.subplots(1, len(patrone), figsize=(5 * len(patrone), 4.6), sharey=True)
    axes = [axes] if len(patrone) == 1 else axes
    for ax, patroon in zip(axes, patrone):
        for naam, kleur in SORTEER_KLEURE.items():
            if (patroon, naam) in reekse:
                _teken_lyn(ax, reekse[(patroon, naam)], kleur, naam)
        _as(ax, f"Invoer: {patroon}")
    axes[0].legend(fontsize=8, frameon=False)
    fig.suptitle("Sorteertyd teenoor grootte", fontweight="bold")
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_vergelykings(rye, uit_pad):
    """Grafiek 2: aantal vergelykings (dieselfde elke lopie) met teoretiese verwysingskurwes."""
    rye = [r for r in rye if r["eksperiment"] == "sortering" and r.get("vergelykings") is not None
           and r["patroon"] == "willekeurig"]
    reekse = _reekse(rye, lambda r: r["algoritme"])
    fig, ax = plt.subplots(figsize=(8, 5))
    for naam in ("Invoegsortering", "Saamsmeltsortering"):
        if naam in reekse:
            ax.plot([r["n"] for r in reekse[naam]], [r["vergelykings"] for r in reekse[naam]], "o-",
                    color=SORTEER_KLEURE[naam], label=naam)
    ns = sorted({r["n"] for r in rye})
    if ns:
        ax.plot(ns, [n * n / 4 for n in ns], ":", color="#999", label="n²/4 (verwagting vir ewekansig)")
        ax.plot(ns, [n * math.log2(n) for n in ns], "-.", color="#999", label="n·log₂ n")
    _as(ax, "Presiese vergelykings, ewekansige invoer", "Aantal vergelykings")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_roetes(rye, uit_pad):
    """Grafiek 3: tyd, nodusse uitgebrei en tou-werk vir Dijkstra/A* met drie toue."""
    rye = _vereis(rye, "roete")
    reekse = _reekse(rye, lambda r: (r["algoritme"], r["tou"]))
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(16, 4.8))
    for (alg, tou), reeks in reekse.items():
        _teken_lyn(a1, reeks, TOU_KLEURE[tou], f"{alg} + {tou}", STYLE[alg])
    _as(a1, "Tyd vir al die pare saam")
    a1.legend(fontsize=7, frameon=False)

    # Nodusse uitgebrei hang van die algoritme af, nie van die tou nie: wys die heapq-lyne.
    for alg in ("Dijkstra", "A*"):
        reeks = [r for r in reekse.get((alg, "Binêre hoop (heapq)"), []) if r["status"] == "ok"]
        a2.plot([r["n"] for r in reeks], [r["besoek_totaal"] for r in reeks], STYLE[alg], marker="o",
                color="#1E6FA8" if alg == "A*" else "#7C8B99", label=alg)
    _as(a2, "Nodusse uitgebrei (tellings)", "Nodusse uitgebrei, al die pare")
    a2.legend(frameon=False)

    n_maks = max((r["n"] for r in rye if r["status"] == "ok"), default=None)
    sleutels = [(a, t) for a in ("Dijkstra", "A*") for t in TOU_KLEURE]
    waardes = [next((r["tou_werk_totaal"] for r in reekse.get(s, []) if r["n"] == n_maks and r["status"] == "ok"), 0)
               for s in sleutels]
    a3.bar(range(len(sleutels)), waardes, color=[TOU_KLEURE[t] for _, t in sleutels],
           hatch=None)
    a3.set_xticks(range(len(sleutels)))
    a3.set_xticklabels([f"{a}\n{t.split(' ')[0]}" for a, t in sleutels], fontsize=8)
    a3.set_yscale("log")
    a3.set_ylabel("Tou-werk (tellings)")
    a3.set_title(f"Werk binne die tou, n={n_maks}", fontsize=10)
    a3.grid(True, axis="y", alpha=0.25)
    fig.suptitle("Dijkstra en A* met drie prioriteitstoue", fontweight="bold")
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_kruskal(rye, uit_pad):
    """Grafiek 4: Kruskal se totale tyd teenoor n, en sorteertyd teenoor die res by die grootste n."""
    rye = _vereis(rye, "kruskal")
    reekse = _reekse(rye, lambda r: r["algoritme"].replace("Kruskal + ", ""))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8))
    for naam, kleur in SORTEER_KLEURE.items():
        if naam in reekse:
            _teken_lyn(a1, reekse[naam], kleur, naam)
    _as(a1, "Kruskal: totale tyd")
    a1.legend(fontsize=8, frameon=False)

    n_maks = max((r["n"] for r in rye if r["status"] == "ok"), default=None)
    namme, deel, totale = [], [], []
    for naam in SORTEER_KLEURE:
        r = next((r for r in reekse.get(naam, []) if r["n"] == n_maks and r["status"] == "ok"), None)
        if r:
            namme.append(naam.replace(" (verwysing)", "\n(verwysing)"))
            deel.append(100 * min(r["sorteer_mediaan_s"] / r["mediaan_s"], 1))
            totale.append(r["mediaan_s"])
    a2.bar(namme, deel, color="#D94B4B", label="Sortering")
    a2.bar(namme, [100 - d for d in deel], bottom=deel, color="#1E6FA8", label="Union-Find en res")
    for i, (d, t) in enumerate(zip(deel, totale)):
        a2.text(i, 50, f"{d:.0f}% sortering\n(totaal {t:.3f}s)", ha="center", va="center", color="white",
                fontsize=9, fontweight="bold")
    a2.set_ylabel("Deel van die totale tyd (%)")
    a2.set_ylim(0, 100)
    a2.set_title(f"Waar die tyd heen gaan (n={n_maks})", fontsize=10)
    a2.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    a2.tick_params(axis="x", labelsize=8)
    fig.suptitle("Kruskal met drie sorteermetodes", fontweight="bold")
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)
