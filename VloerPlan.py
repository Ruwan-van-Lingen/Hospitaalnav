"""
Lewer die topologiese grafiek as 'n vloerplandiagram met een paneel per
vloer. Nodusse word volgens hulle plaaslike (pos_x, pos_y)-koördinate geplaas
en rande word tussen hulle geteken. Vertikale verbindings, soos hysbakke en
trappe, en verbindings tussen geboue word duidelik aangedui.

'n Pad wat deur HospitaalGrafiek.astar() of 'n ander roete-algoritme
teruggestuur is, kan opsioneel uitgelig word.
"""

import sqlite3
import matplotlib

# Gebruik 'n bedienerveilige agterkant wat nie 'n GUI of Tk-hoofdraad benodig nie.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

NODE_KLEURE = {
    "AANSLUITING": "#8899a6",
    "HUISBAK_GROEP": "#e67e22",
    "TRAPHUIS": "#e67e22",
    "DEUR": "#8899a6",
    "INGANG": "#27ae60",
    "LUGBRUG": "#8e44ad",
    "TONNEL": "#8e44ad",
    "DEPARTEMENT": "#2980b9",
}

RAND_KLEURE = {
    "GANG": "#b0b8bf",
    "HUISBAK": "#e67e22",
    "TRAPPE": "#e67e22",
    "LUGBRUG": "#8e44ad",
    "TONNEL": "#8e44ad",
}


# Elke vloer kry 'n eie kleur sodat lae wat oorvleuel (bv. hysbakke/trappe wat
# presies op dieselfde plaaslike koördinate op elke vloer van 'n gebou sit)
# steeds van mekaar onderskei kan word wanneer alles saam op een plan lê.
VLOER_KLEURE_PALET = ["#2E8B57", "#1E6FA8", "#E14B4B", "#6D5DD3", "#FFB100", "#D97706", "#7C8B99"]


def teken_vloer_plan(db_pad: str, uit_pad: str, verlig_pad: list[str] | None = None):
    """Teken 'n enkele saamgevoegde plan met alle vloere van albei geboue
    laag-vir-laag bo-op mekaar (elke vloer in sy eie deurskynende kleur),
    en stoor die resultaat as 'n prent. 'n Roete kan opsioneel uitgelig word.
    """
    conn = sqlite3.connect(db_pad)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT vloer_id, gebou_id, level_nommer, naam FROM vloere ORDER BY gebou_id, level_nommer")
    vloere = cur.fetchall()

    cur.execute("SELECT node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, beperkte_groep FROM nodes")
    nodes = {r["node_id"]: dict(r) for r in cur.fetchall()}

    cur.execute("SELECT van_node, na_node, rand_tipe FROM rande")
    rande = cur.fetchall()
    conn.close()

    verlig_rande = set()
    if verlig_pad:
        for a, b in zip(verlig_pad, verlig_pad[1:]):
            verlig_rande.add((a, b))
            verlig_rande.add((b, a))

    vloer_kleur = {
        v["vloer_id"]: VLOER_KLEURE_PALET[i % len(VLOER_KLEURE_PALET)]
        for i, v in enumerate(vloere)
    }

    fig, ax = plt.subplots(figsize=(11, 9))

    # Hou tel van hoeveel roete-etikette reeds by elke plaaslike koördinaat
    # geplaas is, sodat oorvleuelende vloere (bv. 'n hysbak wat op dieselfde
    # (x, y) op elke vloer sit) se etikette nie bo-op mekaar val nie.
    etiket_telling: dict[tuple[float, float], int] = {}

    # Teken elke vloer se rande en nodusse laag-vir-laag bo-op mekaar sodat 
    # die volledige gebou — albei geboue saam — as een saamgevoegde plan
    # sigbaar is, met roete-nodusse/-rande in rooi bo-op alles uitgelig.
    for vloer in vloere:
        vloer_id = vloer["vloer_id"]
        kleur = vloer_kleur[vloer_id]
        vloer_nodes = {nid: n for nid, n in nodes.items() if n["vloer_id"] == vloer_id}

        for e in rande:
            if e["van_node"] in vloer_nodes and e["na_node"] in vloer_nodes:
                a, b = nodes[e["van_node"]], nodes[e["na_node"]]
                is_hl = (e["van_node"], e["na_node"]) in verlig_rande
                ax.plot(
                    [a["pos_x"], b["pos_x"]], [a["pos_y"], b["pos_y"]],
                    color="#e74c3c" if is_hl else kleur,
                    linewidth=3.5 if is_hl else 1.4,
                    alpha=1.0 if is_hl else 0.5,
                    zorder=3 if is_hl else 1,
                )

        for nid, n in vloer_nodes.items():
            is_hl = verlig_pad is not None and nid in verlig_pad
            ax.scatter(
                n["pos_x"], n["pos_y"],
                s=200 if is_hl else 70,
                c="#e74c3c" if is_hl else kleur,
                edgecolors="white",
                linewidths=1.3,
                alpha=1.0 if is_hl else 0.75,
                zorder=4 if is_hl else 2,
            )
            if is_hl:
                etiket = n["etiket"]
                if n["beperkte_groep"]:
                    etiket += f"\n[{n['beperkte_groep']}]"
                posisie = (n["pos_x"], n["pos_y"])
                herhaling = etiket_telling.get(posisie, 0)
                etiket_telling[posisie] = herhaling + 1
                ax.annotate(
                    etiket, posisie,
                    textcoords="offset points", xytext=(6, 6 + herhaling * 14),
                    fontsize=7.5, color="#12222E", fontweight="bold",
                    zorder=5,
                )

    ax.set_aspect("equal")
    # Keer die y-as om sodat skerm-op met die vloerplan se noordrigting ooreenstem.
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_title(
        "Hospitaal Navigasie — Alle Vloere Saamgevoeg (Albei Geboue)",
        fontsize=13, fontweight="bold",
    )

    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=f"{v['gebou_id']} · {v['naam']}",
               markerfacecolor=vloer_kleur[v["vloer_id"]], markersize=9)
        for v in vloere
    ]
    if verlig_pad:
        legend_elements.append(
            Line2D([0], [0], marker='o', color='w', label="Roete",
                   markerfacecolor="#e74c3c", markersize=9)
        )
    fig.legend(
        handles=legend_elements, loc="lower center",
        ncol=min(len(legend_elements), 4), fontsize=8, frameon=False,
    )

    plt.tight_layout(rect=[0, 0.08, 1, 0.95])
    plt.savefig(uit_pad, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved diagram to {uit_pad}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db

    bou_demo_db("hospitaal.db", "Skema.sql", "SeedData.sql")
    g = HospitaalGrafiek("hospitaal.db")

    # Genereer eers 'n basiese diagram sonder 'n uitgeligte roete.
    teken_vloer_plan("hospitaal.db", "vloer_plan.png")

    # diagram met n PUBLIEK roete verlig
    result = g.astar("MAIN-G-ENT", "SYGEBOU-1-RAD", gebruiker_tipe="PUBLIEK")
    if result:
        pad, _ = result
        teken_vloer_plan("hospitaal.db", "vloer_plan_met_roete.png", verlig_pad=pad)
