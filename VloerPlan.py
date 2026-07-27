"""
Renders the topological graph as a floor-plan-style diagram - one panel
per floor, nodes plotted at their local (pos_x, pos_y) coordinates,
edges drawn between them. Vertical-circulation edges (elevator/stairs)
and building links (sky bridge/tunnel) are annotated since they don't
have a same-floor edge to draw.

Optionally highlights a path (list of node_ids) returned by
HospitalGraph.astar(), e.g. to illustrate a specific route.
"""

import sqlite3
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

NODE_COLORS = {
    "JUNCTION": "#8899a6",
    "ELEVATOR_LOBBY": "#e67e22",
    "STAIRWELL": "#e67e22",
    "DOORWAY": "#8899a6",
    "ENTRANCE": "#27ae60",
    "SKYBRIDGE": "#8e44ad",
    "TUNNEL": "#8e44ad",
    "DEPARTMENT": "#2980b9",
}

EDGE_COLORS = {
    "CORRIDOR": "#b0b8bf",
    "ELEVATOR": "#e67e22",
    "STAIRS": "#e67e22",
    "SKYBRIDGE": "#8e44ad",
    "TUNNEL": "#8e44ad",
}


def draw_floor_plan(db_path: str, out_path: str, highlight_path: list[str] | None = None):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT floor_id, building_id, level_number, name FROM floors ORDER BY building_id, level_number")
    floors = cur.fetchall()

    cur.execute("SELECT node_id, floor_id, type_code, label, pos_x, pos_y, restricted_group FROM nodes")
    nodes = {r["node_id"]: dict(r) for r in cur.fetchall()}

    cur.execute("SELECT from_node, to_node, edge_type FROM edges")
    edges = cur.fetchall()
    conn.close()

    highlight_edges = set()
    if highlight_path:
        for a, b in zip(highlight_path, highlight_path[1:]):
            highlight_edges.add((a, b))
            highlight_edges.add((b, a))

    n_floors = len(floors)
    fig, axes = plt.subplots(1, n_floors, figsize=(6 * n_floors, 6))
    if n_floors == 1:
        axes = [axes]

    for ax, floor in zip(axes, floors):
        floor_id = floor["floor_id"]
        floor_nodes = {nid: n for nid, n in nodes.items() if n["floor_id"] == floor_id}

        # same-floor edges only
        for e in edges:
            if e["from_node"] in floor_nodes and e["to_node"] in floor_nodes:
                a, b = nodes[e["from_node"]], nodes[e["to_node"]]
                is_hl = (e["from_node"], e["to_node"]) in highlight_edges
                ax.plot(
                    [a["pos_x"], b["pos_x"]], [a["pos_y"], b["pos_y"]],
                    color="#e74c3c" if is_hl else EDGE_COLORS.get(e["edge_type"], "#ccc"),
                    linewidth=3.5 if is_hl else 1.5,
                    zorder=2 if is_hl else 1,
                )

        for nid, n in floor_nodes.items():
            color = NODE_COLORS.get(n["type_code"], "#333")
            is_hl = highlight_path is not None and nid in highlight_path
            ax.scatter(
                n["pos_x"], n["pos_y"],
                s=180 if is_hl else 90,
                c=color,
                edgecolors="#e74c3c" if is_hl else "white",
                linewidths=2 if is_hl else 1,
                zorder=3,
            )
            label = n["label"]
            if n["restricted_group"]:
                label += f"\n[{n['restricted_group']}]"
            ax.annotate(
                label, (n["pos_x"], n["pos_y"]),
                textcoords="offset points", xytext=(6, 6),
                fontsize=7.5, color="#333",
            )

        ax.set_title(f"{floor['building_id']} — {floor['name']}", fontsize=12, fontweight="bold")
        ax.set_aspect("equal")
        ax.invert_yaxis()  # so 'up' on screen matches typical floor-plan north
        ax.axis("off")

    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label=t,
               markerfacecolor=c, markersize=9)
        for t, c in NODE_COLORS.items()
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=len(legend_elements), fontsize=8, frameon=False)

    fig.suptitle("Hospital Wayfinding — Topological Floor Plan Graph", fontsize=14, fontweight="bold")
    plt.tight_layout(rect=[0, 0.05, 1, 0.95])
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved diagram to {out_path}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from hospital_graph import HospitalGraph, build_demo_db

    build_demo_db("hospital.db", "schema.sql", "seed_data.sql")
    g = HospitalGraph("hospital.db")

    # base diagram, no highlighted route
    draw_floor_plan("hospital.db", "floor_plan.png")

    # diagram with a PUBLIC route highlighted
    result = g.astar("MAIN-G-ENT", "ANNEX-1-RAD", user_type="PUBLIC")
    if result:
        path, _ = result
        draw_floor_plan("hospital.db", "floor_plan_with_route.png", highlight_path=path)
