"""Stap 4c: grafieke vir stap 3 (lambda, parallel dekking) en 'n Kruskal-spanboomtekening.

Lees groot_resultate_stap3.json (van groot_stap3.py); meet self niks nie.

  lambda_1_vergelyking.png  - lambda teenoor def teenoor inline: tyd as veelvoud van die vinnigste
  parallel_1_dekking.png    - ontruimingsdekking: sekwensieel teenoor parallel (tyd en versnelling)
  kruskal_1_spanboom.png    - 'n vloer met die minimum spanboom in oranje en die oorblywende rande vaal

LET WEL: parallelle spoed hang van die kerne af. Die kerntal van die lopie word op die
grafiek gewys; met een kern wys 'versnelling' net oorhoofse koste en ruis.
"""

import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from groot_algoritmes import kruskal

VARIANT_KLEURE = ["#1E6FA8", "#2E8B57", "#D97706", "#7C8B99"]


def laai(pad):
    """Gee die hele stap 3-JSON as woordeboek."""
    with open(pad, encoding="utf-8") as leer:
        return json.load(leer)


def teken_lambda(rye, uit_pad):
    """Een paneel per eksperiment: staaf = tyd / vinnigste tyd, by die grootste n."""
    if not rye:
        raise ValueError("Geen lambda-resultate nie; loop groot_stap3.py --net lambda eers.")
    n = max(r["n"] for r in rye)
    groepe = defaultdict(list)
    for r in rye:
        if r["n"] == n:
            groepe[r["eksperiment"]].append(r)
    fig, axes = plt.subplots(1, len(groepe), figsize=(5 * len(groepe), 4.6))
    axes = [axes] if len(groepe) == 1 else axes
    for ax, (naam, lede) in zip(axes, groepe.items()):
        vinnigste = min(r["mediaan_s"] for r in lede)
        verh = [r["mediaan_s"] / vinnigste for r in lede]
        ax.bar(range(len(lede)), verh, color=VARIANT_KLEURE[:len(lede)])
        for i, (v, r) in enumerate(zip(verh, lede)):
            ax.text(i, v, f"{v:.2f}x\n{r['mediaan_s'] * 1000:.1f} ms", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(len(lede)))
        ax.set_xticklabels([r["variant"].replace(" (", "\n(").replace(" + ", "\n+ ") for r in lede], fontsize=7)
        ax.set_ylim(0, max(verh) * 1.25)
        ax.axhline(1, color="#999", linewidth=0.8)
        ax.set_title(naam, fontsize=10)
        ax.set_ylabel("Tyd as veelvoud van die vinnigste")
    fig.suptitle(f"Lambda teenoor def teenoor inline (n={n:,} aanroepe)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_parallel(rye, kerne, uit_pad):
    """Links: tyd per metode en grootte (log-as). Regs: versnelling teenoor sekwensieel."""
    rye = [r for r in rye if r["status"] == "ok"]
    if not rye:
        raise ValueError("Geen dekkingsresultate nie; loop groot_stap3.py --net parallel eers.")
    metodes = [("sekwensieel", "#7C8B99")]
    werkers = sorted({int(w) for r in rye for w in r["parallel"]})
    kleure = ["#1E6FA8", "#2E8B57", "#D97706", "#6D5DD3", "#D94B4B", "#C7A008"]
    for i, w in enumerate(werkers):
        metodes.append((f"{w} werker(s), een taak per nodus", kleure[(2 * i) % 6]))
        metodes.append((f"{w} werker(s), brokke", kleure[(2 * i + 1) % 6]))

    def tyd(r, naam):
        if naam == "sekwensieel":
            return r["sekwensieel"]["mediaan_s"]
        w, soort = naam.split(" werker(s), ")
        return r["parallel"][w][soort]["mediaan_s"]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    breedte = 0.8 / len(metodes)
    for j, (naam, kleur) in enumerate(metodes):
        xs = [i + j * breedte for i in range(len(rye))]
        a1.bar(xs, [tyd(r, naam) for r in rye], breedte, color=kleur, label=naam)
        if naam != "sekwensieel":
            a2.bar(xs, [tyd(r, "sekwensieel") / tyd(r, naam) for r in rye], breedte, color=kleur)
    middel = [i + 0.4 - breedte / 2 for i in range(len(rye))]
    for ax in (a1, a2):
        ax.set_xticks(middel)
        ax.set_xticklabels([f"n={r['n']}\n({r['onbereikbaar']} onbereikbaar)" for r in rye], fontsize=8)
    a1.set_yscale("log")
    a1.set_ylabel("Mediaan tyd (s)")
    a1.set_title("Tyd om elke nodus se ontruimingsroete te kontroleer", fontsize=10)
    a1.legend(fontsize=7, frameon=False)
    a2.axhline(1, color="#999", linewidth=1)
    a2.set_ylabel("Versnelling (sekwensieel / parallel)")
    a2.set_title("Bo 1.0x is parallel vinniger", fontsize=10)
    fig.suptitle(f"Ontruimingsdekking, sekwensieel teenoor parallel (kerne beskikbaar: {kerne})",
                 fontweight="bold")
    if kerne == 1:
        fig.text(0.5, 0.01, "Net een kern tydens hierdie lopie: die versnelling is ruis en oorhoofse koste, nie 'n werklike meting nie.",
                 ha="center", fontsize=8, color="#D94B4B")
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_spanboom(graf, vloer, uit_pad):
    """Teken een vloer: minimum spanboom-rande (Kruskal) in oranje, ander rande vaal.

    Rande tussen vloere word weggelaat; die spanboom word oor die hele grafiek bereken
    en slegs die rande binne die gekose vloer word gewys.
    """
    uitslag = kruskal(graf.nodes, graf.ongerigte_kante())
    boom = {frozenset((a, b)) for a, b, _ in uitslag.kante}
    nodusse = {n for n, d in graf.nodes.items() if d["vloer"] == vloer}
    fig, ax = plt.subplots(figsize=(8, 8))
    ander = in_boom = 0
    for van, na, tipe, *_ in graf.rande_lys:
        if van in nodusse and na in nodusse:
            a, b = graf.nodes[van]["pos"], graf.nodes[na]["pos"]
            if frozenset((van, na)) in boom:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#D97706", linewidth=2.2, zorder=2)
                in_boom += 1
            else:
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#C7D6DD", linewidth=1, linestyle="--", zorder=1)
                ander += 1
    uitgange = [n for n in nodusse if graf.nodes[n]["is_nooduitgang"]]
    gewone = [n for n in nodusse if n not in uitgange]
    ax.scatter([graf.nodes[n]["pos"][0] for n in gewone], [graf.nodes[n]["pos"][1] for n in gewone],
               s=8, color="#1B3446", zorder=3)
    ax.scatter([graf.nodes[n]["pos"][0] for n in uitgange], [graf.nodes[n]["pos"][1] for n in uitgange],
               s=60, marker="^", color="#2E8B57", zorder=4)
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_title(f"Vloer {vloer}: {in_boom} spanboomrande, {ander} oortollige rande\n"
                 f"(hele grafiek: {len(uitslag.kante)} rande, totale gewig {uitslag.totale_gewig:,.0f}s, "
                 f"{uitslag.aantal_komponente} komponent)", fontsize=10)
    legende = [Line2D([0], [0], color="#D97706", lw=3, label="Minimum spanboom (Kruskal)"),
               Line2D([0], [0], color="#C7D6DD", lw=1.5, ls="--", label="Oortollige rand (sou 'n siklus vorm)"),
               Line2D([0], [0], marker="^", color="w", markerfacecolor="#2E8B57", markersize=9, label="Nooduitgang")]
    ax.legend(handles=legende, loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=3, frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)
