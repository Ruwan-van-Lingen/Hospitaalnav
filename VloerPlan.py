"""================================================================================================================
VloerPlan.py
=============
Matplotlib-gebaseerde vloerplanvisualiseerder vir die Hospitaal Navigasiestelsel.

Hierdie module lewer 'n topologiese grafiekskets as 'n PNG-prent met
een paneel per vloer. Dit word gebruik deur die /route/image-eindpunt in
main.py om 'n aflaaibare roetekaart te genereer.

Waarom Matplotlib (en nie SVG of die webkoppelvlak nie)?
---------------------------------------------------------
Die webkoppelvlak (hospitaal_wayfinder.js) teken die interaktiewe SVG-kaart
kliëntkant. Hierdie module dien 'n ander doel: dit genereer 'n statiese
PNG-lêer op die bediener, geskik vir druk of aflaai. Matplotlib se
nie-interaktiewe Agg-agterkant werk sonder 'n vertoonskerm of grafiese
koppelvlak en is daarom bruikbaar in bediener- en Docker-omgewings.

Prent-uitleg
-------------
• Elke vloer kry sy eie paneel.
• Nodusse word by hul (pos_x, pos_y)-koördinate geplaas.
• Rande word as lyne tussen nodusse geteken.
• As 'n roetepad verskaf word, word die betrokke nodusse en rande in rooi uitgelig met 'n dikker lyndikte.
• Die y-as word omgekeer sodat "skerm-op" met die vloerplan se oriëntasie ooreenstem (pos_y = 0 is bo).
"""

import sqlite3
import matplotlib

# Kies die Agg-agterkant voordat matplotlib.pyplot ingevoer word.
# Geen Tk-venster of grafiese vertoonskerm word vir die PNG benodig nie.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# Handgeskrewe sorteeralgoritme, in plaas van SQL se ORDER BY.
from Sorteer import insertion_sort

# Kleurpalet vir nodustipes — ooreenstemmend met die webkoppelvlak se CSS-veranderlikes.
NODE_KLEURE = {
    "AANSLUITING":   "#8899a6",  # Grys  — gang-aansluitingspunte
    "HUISBAK_GROEP": "#e67e22",  # Oranje — hysbakke
    "TRAPHUIS":      "#e67e22",  # Oranje — trappe (selfde as hysbakke)
    "DEUR":          "#8899a6",  # Grys  — deure
    "INGANG":        "#27ae60",  # Groen — ingange / nooduitgange
    "LUGBRUG":       "#8e44ad",  # Pers  — lugbrûe
    "TONNEL":        "#8e44ad",  # Pers  — tonnels
    "DEPARTEMENT":   "#2980b9",  # Blou  — departemente en sale
}

# Kleurpalet vir randtipes.
RAND_KLEURE = {
    "GANG":    "#b0b8bf",  # Liggrys — gewone gange
    "HUISBAK": "#e67e22",  # Oranje  — hysbakverbindings
    "TRAPPE":  "#e67e22",  # Oranje  — trapverbindings
    "LUGBRUG": "#8e44ad",  # Pers    — lugbrûe
    "TONNEL":  "#8e44ad",  # Pers    — tonnels
}


def teken_vloer_plan(db_pad: str, uit_pad: str, verlig_pad: list[str] | None = None):
    """
    Genereer 'n PNG-vloerplan vir alle vloere en stoor dit by uit_pad.

    Parameters
    ----------
    db_pad      : Pad na die SQLite-databasis (hospitaal.db).
    uit_pad     : Uitvoerlêerpad vir die gegenereerde PNG-prent.
    verlig_pad  : Opsionele lys node-ID's (soos teruggegee deur astar()) wat
                  op die prent uitgelig moet word. Uitgeligte rande word in
                  rooi geteken en uitgeligte nodusse is groter.
    """
    # Laai alle vloere, nodusse en rande uit die databasis.
    conn = sqlite3.connect(db_pad)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT vloer_id, gebou_id, level_nommer, naam FROM vloere")
    # Invoegsortering op TWEE velde. Die tuple-sleutel gee presies dieselfde
    # volgorde as 'ORDER BY gebou_id, level_nommer': eers al die vloere van
    # die een gebou van onder na bo, dan die van die volgende gebou.
    vloere = insertion_sort(cur.fetchall(), sleutel=("gebou_id", "level_nommer"))

    cur.execute("SELECT node_id, vloer_id, tipe_kode, etiket, pos_x, pos_y, beperkte_groep FROM nodes")
    nodes = {r["node_id"]: dict(r) for r in cur.fetchall()}

    cur.execute("SELECT van_node, na_node, rand_tipe FROM rande")
    rande = cur.fetchall()
    conn.close()

    # Bou 'n stel van (van, na)-randpare op die pad vir vinnige naslaan.
    verlig_rande: set[tuple[str, str]] = set()
    if verlig_pad:
        for a, b in zip(verlig_pad, verlig_pad[1:]):
            verlig_rande.add((a, b))
            verlig_rande.add((b, a))  # Dieselfde getekende lyn verteenwoordig albei rigtings.

    # Skep een paneel per vloer, horisontaal gerangskik.
    n_vloere = len(vloere)
    fig, axes = plt.subplots(1, n_vloere, figsize=(6 * n_vloere, 6))
    if n_vloere == 1:
        axes = [axes]  # Verseker 'n itereerbare lys, ook wanneer daar net een vloer is.

    for ax, vloer in zip(axes, vloere):
        vloer_id = vloer["vloer_id"]
        # Filter nodusse en rande tot slegs hierdie vloer.
        vloer_nodes = {nid: n for nid, n in nodes.items() if n["vloer_id"] == vloer_id}

        # Teken eers rande (sodat nodusse bo-op verskyn).
        for e in rande:
            # Teken slegs rande waarvan BEIDE eindpunte op hierdie vloer is.
            # Vertikale rande (hysbakke, trappe) en gebou-tot-gebou rande
            # word hier oorgeslaan — dit word in die webkoppelvlak se oorsigmodus gewys.
            if e["van_node"] in vloer_nodes and e["na_node"] in vloer_nodes:
                a, b = nodes[e["van_node"]], nodes[e["na_node"]]
                is_hl = (e["van_node"], e["na_node"]) in verlig_rande
                ax.plot(
                    [a["pos_x"], b["pos_x"]], [a["pos_y"], b["pos_y"]],
                    color="#e74c3c" if is_hl else RAND_KLEURE.get(e["rand_tipe"], "#ccc"),
                    linewidth=3.5 if is_hl else 1.5,
                    zorder=2 if is_hl else 1,
                )

        # Teken nodusse as gekleurde punte bo-op die rande.
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
            # Voeg die nodus se etiket by, met die beperkte groep in hakies indien van toepassing.
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
        ax.invert_yaxis()  # Keer y-as om: pos_y=0 is bo, soos op 'n vloerplan.
        ax.axis("off")     # Verberg asse — die vloerplan het sy eie visuele konteks.

    # Bou 'n legende onderaan die figuur.
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=t,
               markerfacecolor=c, markersize=9)
        for t, c in NODE_KLEURE.items()
    ]
    fig.legend(handles=legend_elements, loc="lower center",
               ncol=len(legend_elements), fontsize=8, frameon=False)

    fig.suptitle("Hospitaal Navigasie — Topologiese Vloerplan Grafiek",
                 fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])  # Maak ruimte vir die legende onderaan.
    plt.savefig(uit_pad, dpi=150, bbox_inches="tight")
    plt.close()  # Sluit die figuur om geheue vry te stel (belangrik in 'n bedieneromgewing).
    # Geen print hier nie: hierdie funksie word per versoek deur /route/image
    # aangeroep, en die aanroeper besluit of 'n boodskap nodig is.


# ---------------------------------------------------------------------------
# Handmatige demonstrasie (voer uit as: python VloerPlan.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from HospitaalGrafiek import HospitaalGrafiek, bou_demo_db

    bou_demo_db("hospitaal.db", "Skema.sql", "SeedData.sql")
    g = HospitaalGrafiek("hospitaal.db")

    # Genereer 'n basiese diagram sonder 'n uitgeligte roete.
    teken_vloer_plan("hospitaal.db", "vloer_plan.png")
    print("Vloerplan gestoor: vloer_plan.png")

    # Genereer 'n diagram met die PUBLIEK-roete na Radiologie uitgelig.
    result = g.astar("MAIN-G-ENT", "SYGEBOU-1-RAD", gebruiker_tipe="PUBLIEK")
    if result:
        pad, _, _ = result
        teken_vloer_plan("hospitaal.db", "vloer_plan_met_roete.png", verlig_pad=pad)
        print("Vloerplan gestoor: vloer_plan_met_roete.png")
