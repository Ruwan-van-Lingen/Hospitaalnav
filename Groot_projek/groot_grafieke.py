"""Stap 4a: bottelnekgrafieke (maksimum vloei en minimum snit) vir die groot datastel.

Drie PNG-grafieke, almal met Matplotlib se 'Agg' (geen skerm nodig):
  1. vloere   - maksimum vloei as elke vloer afsonderlik ontruim word, gekleur
                volgens die soort rand wat die bottelnek is (trappe of gange).
  2. sykant   - 'n sy-aansig van die gebou: trappe as vertikale lyne, dikte =
                kapasiteit, rooi = bottelnek vir die gekose vloer; hysbakke
                (uitgesluit by ontruiming) gestippel.
  3. wat_as   - wat as die trappe breër was? Vloei teenoor trapkapasiteit, met
                die bottelnek wat van trappe na gange skuif.

Al die syfers kom uit maks_vloei_na_uitgange() in groot_algoritmes.py (Edmonds-Karp
uit mst_en_vloei.py); hierdie lêer teken net. Die kapasiteite is demonstrasiewaardes
en die data is gegenereer, dus modelleer dit 'n bottelnek, nie 'n werklike gebou nie.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from groot_algoritmes import GrootGrafiek, maks_vloei_na_uitgange

KLEURE = {"TRAPPE": "#D94B4B", "GANG": "#1E6FA8", "HUISBAK": "#D97706"}
DONKER = "#12222E"
MENGSEL = "#6D5DD3"


# ---------------------------------------------------------------------------
# Berekeninge (geen tekenwerk nie, sodat dit maklik toetsbaar is)
# ---------------------------------------------------------------------------

def vloer_bronne(graf, vloer):
    """Alle nodusse op 'n vloer wat self nie nooduitgange is nie."""
    return [n for n, d in graf.nodes.items() if d["vloer"] == vloer and not d["is_nooduitgang"]]


def rand_tipe_van(graf, van, na):
    """Die tipe van die rand van -> na (die goedkoopste as daar parallelle is)."""
    return next(r.rand_tipe for r in graf.adjacency[van] if r.na_node == na)


def bottelnek_per_vloer(graf):
    """Vir elke vloer: vloei, bottelnekrande en hoofsoort rand. Lys woordeboeke, van bo na onder.

    min_tyd_s is 'n ondergrens: aantal mense (een per nodus) gedeel deur die vloei.
    """
    rye = []
    for vloer in sorted({d["vloer"] for d in graf.nodes.values()}, reverse=True):
        bronne = vloer_bronne(graf, vloer)
        uitslag = maks_vloei_na_uitgange(graf, bronne)
        if uitslag is None:
            continue
        tipes = [rand_tipe_van(graf, a, b) for a, b, _ in uitslag.bottelnekke]
        hoof = max(set(tipes), key=tipes.count) if tipes else "GANG"
        rye.append({"vloer": vloer, "mense": len(bronne), "vloei": uitslag.maks_vloei,
                    "bottelnekke": uitslag.bottelnekke, "tipes": tipes, "hoof_tipe": hoof,
                    "min_tyd_s": len(bronne) / uitslag.maks_vloei if uitslag.maks_vloei else float("inf")})
    return rye


def skaleer_tipe(graf, tipe, faktor):
    """Nuwe grafiek waarin alle rande van een tipe se kapasiteit met 'faktor' vermenigvuldig is.

    Die oorspronklike grafiek bly onveranderd; rande word van rande_lys herbou.
    """
    nuut = GrootGrafiek()
    for n in graf.nodes.values():
        nuut.voeg_nodus_by(n["node_id"], n["etiket"], n["vloer"], n["pos"][0], n["pos"][1],
                           n["tipe_kode"], n["is_nooduitgang"])
    for van, na, t, afstand, gewig, kap, bi in graf.rande_lys:
        nuut.voeg_rand_by(van, na, t, afstand, gewig, kap * faktor if t == tipe else kap, bi)
    return nuut


def wat_as_reeks(graf, vloer, faktore=(1, 1.5, 2, 3, 4, 6, 8, 12)):
    """Vloei en bottelnektipe as die trappe 'faktor' keer meer kapasiteit het."""
    rye = []
    for f in faktore:
        g = skaleer_tipe(graf, "TRAPPE", f)
        uit = maks_vloei_na_uitgange(g, vloer_bronne(g, vloer))
        tipes = {rand_tipe_van(g, a, b) for a, b, _ in uit.bottelnekke}
        rye.append({"faktor": f, "vloei": uit.maks_vloei, "tipes": sorted(tipes),
                    "trappe_is_bottelnek": "TRAPPE" in tipes})
    return rye


# ---------------------------------------------------------------------------
# Grafieke
# ---------------------------------------------------------------------------

def teken_vloere(rye, uit_pad):
    """Grafiek 1: vloei per vloer as staafgrafiek, gekleur volgens bottelneksoort."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6))
    byskrifte = [f"Vloer {r['vloer']}\n({r['mense']} mense)" for r in rye]
    kleure = [KLEURE.get(r["hoof_tipe"], "#777") for r in rye]

    a1.bar(byskrifte, [r["vloei"] for r in rye], color=kleure)
    for i, r in enumerate(rye):
        a1.text(i, r["vloei"], f"{r['vloei']:g}", ha="center", va="bottom", fontsize=9)
    a1.set_ylabel("Maksimum vloei (persone/s)")
    a1.set_title("Hoeveel kan per sekonde by die uitgange uitkom?", fontsize=11)

    a2.bar(byskrifte, [r["min_tyd_s"] for r in rye], color=kleure)
    for i, r in enumerate(rye):
        a2.text(i, r["min_tyd_s"], f"{r['min_tyd_s']:.0f}s", ha="center", va="bottom", fontsize=9)
    a2.set_ylabel("Ondergrens op ontruimingstyd (s)")
    a2.set_title("Minstens so lank as een persoon per nodus ontruim", fontsize=11)

    legende = [Line2D([0], [0], marker="s", color="w", markerfacecolor=KLEURE[t], markersize=11,
                      label=f"Bottelnek = {t.lower()}") for t in ("TRAPPE", "GANG")]
    fig.legend(handles=legende, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Bottelnekke per vloer (maksimum vloei = minimum snit)", fontweight="bold")
    fig.tight_layout(rect=[0, 0.07, 1, 0.95])
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_sykant(graf, ry, uit_pad):
    """Grafiek 2: sy-aansig. Trappe = vertikale lyne (dikte = kapasiteit); bottelnekke vir 'ry' in rooi."""
    snit = {(a, b) for a, b, _ in ry["bottelnekke"]} | {(b, a) for a, b, _ in ry["bottelnekke"]}
    fig, ax = plt.subplots(figsize=(11, 5.4))
    vlakke = sorted({d["vloer"] for d in graf.nodes.values()})
    xs = [d["pos"][0] for d in graf.nodes.values()]
    for v in vlakke:
        ax.hlines(v, min(xs), max(xs), color="#AFC2CB", linewidth=6, zorder=1)
        ax.text(min(xs) - 2, v, f"Vloer {v}", ha="right", va="center", fontsize=9)

    for van, na, tipe, _, _, kap, _ in graf.rande_lys:
        a, b = graf.nodes[van], graf.nodes[na]
        if a["vloer"] == b["vloer"]:
            continue
        is_snit = (van, na) in snit
        if tipe == "HUISBAK":
            ax.plot([a["pos"][0]] * 2, [a["vloer"], b["vloer"]], color="#999", linestyle=":", linewidth=2, zorder=2)
        else:
            ax.plot([a["pos"][0]] * 2, [a["vloer"], b["vloer"]], zorder=3,
                    color=KLEURE["TRAPPE"] if is_snit else "#1B3446",
                    linewidth=1.5 + kap * 2.2, solid_capstyle="round")
            ax.text(a["pos"][0] + 1.2, (a["vloer"] + b["vloer"]) / 2, f"{kap:g}/s", fontsize=7, va="center")

    uitgange = [d for d in graf.nodes.values() if d["is_nooduitgang"]]
    ax.scatter([d["pos"][0] for d in uitgange], [0.0] * len(uitgange), marker="^", s=70,
               color="#2E8B57", zorder=4)
    ax.set_yticks([])
    ax.set_xlabel("Posisie langs die gebou (m)")
    ax.set_ylim(min(vlakke) - 0.6, max(vlakke) + 0.6)
    ax.set_title(f"Sy-aansig: ontruim vloer {ry['vloer']} ({ry['mense']} mense) - "
                 f"{len(ry['bottelnekke'])} bottelnekrande, vloei {ry['vloei']:g}/s", fontsize=11)
    legende = [Line2D([0], [0], color=KLEURE["TRAPPE"], lw=4, label="Trap in die minimum snit (bottelnek)"),
               Line2D([0], [0], color="#1B3446", lw=4, label="Ander trap (dikte = kapasiteit)"),
               Line2D([0], [0], color="#999", lw=2, ls=":", label="Hysbak (uitgesluit by ontruiming)"),
               Line2D([0], [0], marker="^", color="w", markerfacecolor="#2E8B57", markersize=9, label="Nooduitgang")]
    ax.legend(handles=legende, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4, frameon=False, fontsize=8)
    for kant in ("top", "right", "left"):
        ax.spines[kant].set_visible(False)
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)


def teken_wat_as(reeks, vloer, uit_pad):
    """Grafiek 3: vloei teenoor trapkapasiteit; punt se kleur wys of trappe, gange of albei die bottelnek is."""
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    fs = [r["faktor"] for r in reeks]
    ax.plot(fs, [r["vloei"] for r in reeks], color="#999", zorder=1)
    for r in reeks:
        kleur = MENGSEL if r["tipes"] == ["GANG", "TRAPPE"] else (
            KLEURE["TRAPPE"] if r["trappe_is_bottelnek"] else KLEURE["GANG"])
        ax.scatter(r["faktor"], r["vloei"], color=kleur, s=60, zorder=2)
        ax.text(r["faktor"], r["vloei"], f" {r['vloei']:g}", va="bottom", fontsize=8)
    ax.set_xlabel("Trapkapasiteit as veelvoud van die oorspronklike")
    ax.set_ylabel("Maksimum vloei (persone/s)")
    ax.set_title(f"Wat as die trappe breër was? (ontruim vloer {vloer})", fontweight="bold", fontsize=11)
    legende = [Line2D([0], [0], marker="o", color="w", markerfacecolor=KLEURE["TRAPPE"], markersize=9,
                      label="Slegs trappe is die bottelnek"),
               Line2D([0], [0], marker="o", color="w", markerfacecolor=MENGSEL, markersize=9,
                      label="Trappe en gange saam (die bottelnek skuif)")]
    ax.legend(handles=legende, frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(uit_pad, dpi=150)
    plt.close(fig)
