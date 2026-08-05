"""
Hospitaalpadvinder – grafieklaaier en A*-roetebepaling.

Laai die topologiese grafiek (nodes = keusepunte, rande = geweegde paaie) uit die SQLite-databasis en voer A* tussen twee nodes uit. Gebruikerstipe-toegangsbeperkings word eerbiedig; die publiek kan byvoorbeeld nie 'n roete deur die ICU of operasieteater volg nie.

Heuristiek: die reguitlyn- (Euklidiese) afstand tussen nodes se plaaslike vloerplankoördinate, plus 'n vaste strafwaarde vir elke vloeroorgang. Die strafwaarde bly konserwatief teenoor die goedkoopste werklike hysbak- of traptyd tussen aangrensende vloere.
"""

import sqlite3
import math
import heapq
from dataclasses import dataclass, field
from typing import Optional

VLOER_VERANDER_PENALTY_S = 20.0  # Konserwatiewe strafwaarde vir die heuristiek.


@dataclass
class Rand:
    na_node: str
    gewig_s: float          # basis_gewig_s + wag_penalty_s
    rand_tipe: str
    vloer_verander: int


class HospitaalGrafiek:
    def __init__(self, db_pad: str):
        self.db_pad = db_pad
        self.nodes: dict[str, dict] = {}      # node_id na {vloer_id, pos, beperkte_groep}
        self.adjacency: dict[str, list[Rand]] = {}
        self._load()

    def _load(self):
        conn = sqlite3.connect(self.db_pad)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT n.node_id, n.vloer_id, n.pos_x, n.pos_y,
                   n.beperkte_groep, f.level_nommer, f.gebou_id
            FROM nodes n JOIN vloere f ON n.vloer_id = f.vloer_id
        """)
        for row in cur.fetchall():
            self.nodes[row["node_id"]] = {
                "vloer_id": row["vloer_id"],
                "pos": (row["pos_x"], row["pos_y"]),
                "level": row["level_nommer"],
                "gebou_id": row["gebou_id"],
                "beperkte_groep": row["beperkte_groep"],
            }
            self.adjacency[row["node_id"]] = []

        cur.execute("""
            SELECT van_node, na_node, rand_tipe, afstand_m,
                   basis_gewig_s, wag_penalty_s, vloer_verander, bidirectional
            FROM rande
        """)
        for row in cur.fetchall():
            gewig = row["basis_gewig_s"] + row["wag_penalty_s"]
            e = Rand(row["na_node"], gewig, row["rand_tipe"], row["vloer_verander"])
            self.adjacency[row["van_node"]].append(e)
            if row["bidirectional"]:
                e_rev = Rand(row["van_node"], gewig, row["rand_tipe"], row["vloer_verander"])
                self.adjacency[row["na_node"]].append(e_rev)

        conn.close()

    def toegelate_groepe(self, gebruiker_tipe: str) -> set[str]:
        """Gee die stel beperkte groepe terug wat 'n gebruikerstipe mag betree."""
        conn = sqlite3.connect(self.db_pad)
        cur = conn.cursor()
        cur.execute(
            "SELECT beperkte_groep FROM toegang_toestemmings WHERE gebruiker_tipe = ?",
            (gebruiker_tipe,),
        )
        groepe = {r[0] for r in cur.fetchall()}
        conn.close()
        return groepe

    def soek_bestemmings(self, soekterm: str = "", limiet: int = 20) -> list[dict]:
        """Soek nodes volgens naam, ID, tipe, gebou of vloer."""
        term = f"%{soekterm.strip()}%"
        conn = sqlite3.connect(self.db_pad)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT n.node_id, n.etiket, n.tipe_kode, n.beperkte_groep,
                   f.vloer_id, f.naam AS vloer_naam,
                   g.gebou_id, g.naam AS gebou_naam
            FROM nodes n
            JOIN vloere f ON n.vloer_id = f.vloer_id
            JOIN geboue g ON f.gebou_id = g.gebou_id
            WHERE n.etiket LIKE ? COLLATE NOCASE
               OR n.node_id LIKE ? COLLATE NOCASE
               OR n.tipe_kode LIKE ? COLLATE NOCASE
               OR f.naam LIKE ? COLLATE NOCASE
               OR g.naam LIKE ? COLLATE NOCASE
            ORDER BY
                CASE WHEN n.etiket LIKE ? COLLATE NOCASE THEN 0 ELSE 1 END,
                n.etiket
            LIMIT ?
            """,
            (term, term, term, term, term, term, limiet),
        )
        bestemmings = [dict(ry) for ry in cur.fetchall()]
        conn.close()
        return bestemmings

    def _heuristic(self, a: str, b: str) -> float:
        ax, ay = self.nodes[a]["pos"]
        bx, by = self.nodes[b]["pos"]
        # Let wel: koördinate is net binne dieselfde vloer vergelykbaar. Die
        # vloerveranderingstraf hou die skatting vir roetes oor vloere relevant.

        planar = math.hypot(ax - bx, ay - by)
        vloer_delta = abs(self.nodes[a]["level"] - self.nodes[b]["level"])
        return planar + vloer_delta * VLOER_VERANDER_PENALTY_S

    def astar(
        self,
        begin: str,
        doel: str,
        gebruiker_tipe: str = "PUBLIEK",
    ) -> Optional[tuple[list[str], float]]:
        """
        Gee (pad_as_lys_van_node_ids, totale_koste_sekondes) terug, of None
        wanneer geen pad bestaan nie, byvoorbeeld weens toegangsbeperkings.
        """
        if begin not in self.nodes or doel not in self.nodes:
            raise ValueError("begin/doel node nie gevind in grafiek nie.")

        toegelaat = self.toegelate_groepe(gebruiker_tipe)

        def is_bruikbaar(node_id: str) -> bool:
            groep = self.nodes[node_id]["beperkte_groep"]
            return groep is None or groep in toegelaat

        if not is_bruikbaar(begin) or not is_bruikbaar(doel):
            return None

        open_set = [(self._heuristic(begin, doel), 0.0, begin)]  # (f-telling, g-telling, node-ID)
        kom_van: dict[str, str] = {}
        g_score = {begin: 0.0}
        besoek = set()

        while open_set:
            _, koste_so_ver, huidig = heapq.heappop(open_set)

            if huidig == doel:
                return self._reconstruct(kom_van, huidig), koste_so_ver

            if huidig in besoek:
                continue
            besoek.add(huidig)

            for rand in self.adjacency[huidig]:
                if not is_bruikbaar(rand.na_node):
                    continue  # Dinamies uitgesluit vir hierdie gebruikerstipe.
                tentatiewe_g = koste_so_ver + rand.gewig_s
                if tentatiewe_g < g_score.get(rand.na_node, math.inf):
                    g_score[rand.na_node] = tentatiewe_g
                    kom_van[rand.na_node] = huidig
                    f_score = tentatiewe_g + self._heuristic(rand.na_node, doel)
                    heapq.heappush(open_set, (f_score, tentatiewe_g, rand.na_node))

        return None  # Geen pad is gevind nie.

    @staticmethod
    def _reconstruct(kom_van: dict[str, str], huidig: str) -> list[str]:
        pad = [huidig]
        while huidig in kom_van:
            huidig = kom_van[huidig]
            pad.append(huidig)
        pad.reverse()
        return pad


def bou_demo_db(db_pad: str, skema_pad: str, seed_pad: str):
    """Hulpfunksie wat die SQLite-databasis uit Skema.sql en SeedData.sql herskep."""
    import os
    if os.path.exists(db_pad):
        os.remove(db_pad)
    conn = sqlite3.connect(db_pad)
    with open(skema_pad) as f:
        conn.executescript(f.read())
    with open(seed_pad) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


if __name__ == "__main__":
    bou_demo_db("hospitaal.db", "Skema.sql", "SeedData.sql")
    g = HospitaalGrafiek("hospitaal.db")

    print("=== PUBLIEK besoeker: Main Ingang -> Radiologie (Annex) ===")
    resultaat = g.astar("MAIN-G-ENT", "ANNEX-1-RAD", gebruiker_tipe="PUBLIEK")
    if resultaat:
        pad, koste = resultaat
        print(f"Path ({koste:.0f}s): " + " -> ".join(pad))
    else:
        print("Geen roete gevind nie.")

    print("\n=== PUBLIEK besoeker proebeer om by ICU uit te kom (moet geblokkeer word) ===")
    resultaat = g.astar("MAIN-G-ENT", "MAIN-2-ICU", gebruiker_tipe="PUBLIEK")
    print("Geblokeer soos verwag." if resultaat is None else f"Onverwagte roete: {resultaat}")

    print("\n=== STAFF: Hoof Ingang -> ICU ===")
    resultaat = g.astar("MAIN-G-ENT", "MAIN-2-ICU", gebruiker_tipe="STAFF")
    if resultaat:
        pad, koste = resultaat
        print(f"Pad ({koste:.0f}s): " + " -> ".join(pad))
