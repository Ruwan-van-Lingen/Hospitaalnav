"""
Hospital Wayfinding - Graph loader and A* pathfinding.

Loads the topological graph (nodes = decision points, edges = weighted
paths) from the SQLite database and runs A* between two nodes, honouring
per-user-type access restrictions (e.g. PUBLIC can't route through
ICU_ONLY or STAFF_ONLY nodes).

Heuristic: straight-line (Euclidean) distance between nodes' local
floor-plan coordinates, plus a fixed penalty per floor crossed. This
stays admissible as long as FLOOR_CHANGE_PENALTY_S is <= the cheapest
real elevator/stair time between adjacent floors.
"""

import sqlite3
import math
import heapq
from dataclasses import dataclass, field
from typing import Optional

FLOOR_CHANGE_PENALTY_S = 20.0  # conservative lower bound used in the heuristic


@dataclass
class Edge:
    to_node: str
    weight_s: float          # base_weight_s + wait_penalty_s
    edge_type: str           # teen aan muur kant 
    floor_change: int


class HospitalGraph:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.nodes: dict[str, dict] = {}      # node_id -> {floor_id, pos, level, restricted_group}
        self.adjacency: dict[str, list[Edge]] = {}
        self._load()

    def _load(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT n.node_id, n.floor_id, n.pos_x, n.pos_y,
                   n.restricted_group, f.level_number, f.building_id
            FROM nodes n JOIN floors f ON n.floor_id = f.floor_id
        """)
        for row in cur.fetchall():
            self.nodes[row["node_id"]] = {
                "floor_id": row["floor_id"],
                "pos": (row["pos_x"], row["pos_y"]),
                "level": row["level_number"],
                "building_id": row["building_id"],
                "restricted_group": row["restricted_group"],
            }
            self.adjacency[row["node_id"]] = []

        cur.execute("""
            SELECT from_node, to_node, edge_type, distance_m,
                   base_weight_s, wait_penalty_s, floor_change, bidirectional
            FROM edges
        """)
        for row in cur.fetchall():
            weight = row["base_weight_s"] + row["wait_penalty_s"]
            e = Edge(row["to_node"], weight, row["edge_type"], row["floor_change"])
            self.adjacency[row["from_node"]].append(e)
            if row["bidirectional"]:
                e_rev = Edge(row["from_node"], weight, row["edge_type"], row["floor_change"])
                self.adjacency[row["to_node"]].append(e_rev)

        conn.close()

    def allowed_groups(self, user_type: str) -> set[str]:
        """Returns the set of restricted_group values a user_type may enter."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT restricted_group FROM access_permissions WHERE user_type = ?",
            (user_type,),
        )
        groups = {r[0] for r in cur.fetchall()}
        conn.close()
        return groups

    def _heuristic(self, a: str, b: str) -> float:
        ax, ay = self.nodes[a]["pos"]
        bx, by = self.nodes[b]["pos"]
        # NOTE: this only compares in-floor coordinates; cross-floor
        # euclidean distance is not meaningful, so we rely on the
        # floor-change penalty term to keep the estimate admissible.
        planar = math.hypot(ax - bx, ay - by)
        floor_delta = abs(self.nodes[a]["level"] - self.nodes[b]["level"])
        return planar + floor_delta * FLOOR_CHANGE_PENALTY_S

    def astar(
        self,
        start: str,
        goal: str,
        user_type: str = "PUBLIC",
    ) -> Optional[tuple[list[str], float]]:
        """
        Returns (path_as_list_of_node_ids, total_cost_seconds) or None
        if no path exists (e.g. blocked entirely by restrictions).
        """
        if start not in self.nodes or goal not in self.nodes:
            raise ValueError("start/goal node not found in graph")

        allowed = self.allowed_groups(user_type)

        def is_usable(node_id: str) -> bool:
            group = self.nodes[node_id]["restricted_group"]
            return group is None or group in allowed

        if not is_usable(start) or not is_usable(goal):
            return None

        open_set = [(self._heuristic(start, goal), 0.0, start)]
        came_from: dict[str, str] = {}
        g_score = {start: 0.0}
        visited = set()

        while open_set:
            _, cost_so_far, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct(came_from, current), cost_so_far

            if current in visited:
                continue
            visited.add(current)

            for edge in self.adjacency[current]:
                if not is_usable(edge.to_node):
                    continue  # dynamically excluded for this user type
                tentative_g = cost_so_far + edge.weight_s
                if tentative_g < g_score.get(edge.to_node, math.inf):
                    g_score[edge.to_node] = tentative_g
                    came_from[edge.to_node] = current
                    f_score = tentative_g + self._heuristic(edge.to_node, goal)
                    heapq.heappush(open_set, (f_score, tentative_g, edge.to_node))

        return None  # no path found

    @staticmethod
    def _reconstruct(came_from: dict[str, str], current: str) -> list[str]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path


def build_demo_db(db_path: str, schema_path: str, seed_path: str):
    """Helper: (re)creates the SQLite DB from schema.sql + seed_data.sql."""
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())
    with open(seed_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    build_demo_db("hospital.db", "schema.sql", "seed_data.sql")
    g = HospitalGraph("hospital.db")

    print("=== PUBLIC visitor: Main Entrance -> Radiology (Annex) ===")
    result = g.astar("MAIN-G-ENT", "ANNEX-1-RAD", user_type="PUBLIC")
    if result:
        path, cost = result
        print(f"Path ({cost:.0f}s): " + " -> ".join(path))
    else:
        print("No route found.")

    print("\n=== PUBLIC visitor tries to reach ICU (should be blocked) ===")
    result = g.astar("MAIN-G-ENT", "MAIN-2-ICU", user_type="PUBLIC")
    print("Blocked as expected." if result is None else f"Unexpected route: {result}")

    print("\n=== STAFF: Main Entrance -> ICU ===")
    result = g.astar("MAIN-G-ENT", "MAIN-2-ICU", user_type="STAFF")
    if result:
        path, cost = result
        print(f"Path ({cost:.0f}s): " + " -> ".join(path))
