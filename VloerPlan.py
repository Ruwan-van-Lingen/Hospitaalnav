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


def teken_vloer_plan(db_pad: str, uit_pad: str, verlig_pad: list[str] | None = None):
    # Teken die hospitaal se vloere en stoor die resultaat as 'n prent.
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

    n_vloere = len(vloere)
    fig, axes = plt.subplots(1, n_vloere, figsize=(6 * n_vloere, 6))
    if n_vloere == 1:
        axes = [axes]

    for ax, vloer in zip(axes, vloere):
        vloer_id = vloer["vloer_id"]
        vloer_nodes = {nid: n for nid, n in nodes.items() if n["vloer_id"] == vloer_id}

        # Slegs rande waarvan albei nodusse op hierdie vloer is, word geteken.
        for e in rande:
            if e["van_node"] in vloer_nodes and e["na_node"] in vloer_nodes:
                a, b = nodes[e["van_node"]], nodes[e["na_node"]]
                is_hl = (e["van_node"], e["na_node"]) in verlig_rande
                ax.plot(
                    [a["pos_x"], b["pos_x"]], [a["pos_y"], b["pos_y"]],
                    color="#e74c3c" if is_hl else RAND_KLEURE.get(e["rand_tipe"], "#ccc"),
                    linewidth=3.5 if is_hl else 1.5,
                    zorder=2 if is_hl else 1,
                )

        for nid, n in vloer_nodes.items():
            color = NODE_KLEURE.get(n["tipe_kode"], "#333")
            is_hl = verlig_pad is not None and nid in verlig_pad
            ax.scatter(
                n["pos_x"], n["pos_y"],
                s=180 if is_hl else 90,
                c=color,
                edgecolors="#e74c3c" if is_hl else "white",
                linewidths=2 if is_hl else 1,
                zorder=3,
            )
            etiket = n["etiket"]
            if n["beperkte_groep"]:
                etiket += f"\n[{n['beperkte_groep']}]"
            ax.annotate(
                etiket, (n["pos_x"], n["pos_y"]),
                textcoords="offset points", xytext=(6, 6),
                fontsize=7.5, color="#333",
            )

        ax.set_title(f"{vloer['gebou_id']} — {vloer['naam']}", fontsize=12, fontweight="bold")
        ax.set_aspect("equal")
        # Keer die y-as om sodat skerm-op met die vloerplan se noordrigting ooreenstem.
        ax.invert_yaxis()
        ax.axis("off")

    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=t,
               markerfacecolor=c, markersize=9)
        for t, c in NODE_KLEURE.items()
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=len(legend_elements), fontsize=8, frameon=False)

    fig.suptitle("Hospitaal Wayfinding — Topologiese Vloer Plan Grafiek", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
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
